"""LLM-judge eval for the `absent_phosita_reasoning` failure mode.

See docs/superpowers/specs/2026-05-30-phosita-judge-v2-design.md for design.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from typing import Any

PROMPT_VERSION = "v3"
JUDGE_MODEL = "qwen/qwen3-32b"
JUDGE_TEMPERATURE = 0.2
JUDGE_MAX_TOKENS = 1024


def _has_novel_elements(element_mappings: list[dict]) -> bool:
    """True if at least one element is marked novelty='N'."""
    return any(em.get("novelty") == "N" for em in element_mappings)


def needs_judge_call(trace: dict) -> bool:
    """True when this trace requires a judge API call to evaluate.

    Returns False for traces that short-circuit: no parsed_output, no
    element_mappings, or all elements have novelty='Y'.
    """
    parsed = trace.get("parsed_output")
    if not parsed:
        return False
    mappings = parsed.get("element_mappings") or []
    return bool(mappings) and _has_novel_elements(mappings)


_SYSTEM_PROMPT = """You are evaluating a patent obviousness analysis produced by an AI tool.
The tool writes an overall_opinion on whether a source patent is valid
given a target patent (prior art).

Your job: judge whether the overall_opinion contains genuine reasoning
that a person of ordinary skill in the art (PSA) would find the novel
elements non-obvious. This is NOT about whether the conclusion is correct
— it is about whether the opinion provides reasoning beyond a bare assertion.

THE KEY QUESTION:
Does the opinion articulate WHY the specific inventive contribution would
be non-trivial for a PSA, or does it merely assert that conclusion?

PASS — the opinion satisfies at least one:

A. CONCEPTUAL GAP: The opinion contrasts what the prior art teaches (even
   generically) against the specific multi-component invention, making
   clear the prior art lacks the conceptual building blocks — not just
   that it fails to name the exact implementation.

B. DOMAIN GAP / NO OVERLAP: The prior art teaches a fundamentally different
   type of system with zero overlapping elements, so no combination path
   to the invention exists. If the opinion states that none of the claim
   elements have any counterpart in the prior art, the obviousness question
   is vacuous.

C. EXPLICIT PSA ARGUMENT: The opinion explains what a PSA would know or
   lack, what they would naturally try, and why the specific step is
   non-trivial.

FAIL — either pattern triggers FAIL:

1. BARE ASSERTION: The opinion describes what is absent and concludes
   "novel and non-obvious" or "would not be obvious to a person of
   ordinary skill" without articulating the conceptual gap — why the
   combination is non-trivial, not just that it is absent.

2. GENERIC CONCEPT APPLIED: The invention applies or extends a well-known
   general principle (feedback loops, context-aware selection, attention
   mechanisms, joint optimization) to a new setting, but the opinion does
   not explain why a PSA would not naturally apply that principle here.

NOTE: PSA vocabulary ("non-obvious", "would not be obvious to a PSA") does
not make a PASS on its own. These phrases must accompany criterion A, B, or
C above. When attached to a bare assertion of absence, they are conclusions,
not reasoning.

---

EXAMPLES:

### PASS — Criterion A (specific contrast between generic prior art and specific invention)

Overall opinion:
"The core technical advancement of Patent A lies in elements 2-4: (i)
acquisition of speaker-layout data, (ii) a specific amplitude-panning
rendering that uses virtual-speaker geometry and speaker locations, and
(iii) metadata that includes both precise object coordinates and
zone-constraint information. The prior art (Patent B) only anticipates
the generic notion of audio objects with metadata (element 1). It does not
disclose speaker-layout data, the amplitude-panning algorithm,
virtual-speaker concepts, or zone-constraint metadata. Consequently, the
key inventive features of Patent A are novel and non-obvious over Patent B."

Verdict: PASS
Reasoning: The opinion contrasts the prior art's generic capability ("audio
objects with metadata") against four specific domain components of the
invention. This contrast demonstrates that the prior art lacks the
conceptual building blocks — not just the label, but the architectural
specificity. Criterion A satisfied.

---

### PASS — Criterion A (prior art capability explicitly named and bounded)

Overall opinion:
"The core technical advancements of the source patent—namely the use of a
secondary camera with a higher exposure time and optionally a different
field-of-view, and the subsequent fusion of the primary and secondary preview
frames into an enhanced output frame—are not disclosed in the prior-art patent
and would not be obvious to a person of ordinary skill. While the low-light
detection step is anticipated, the novel multi-camera capture and frame-fusion
steps provide a meaningful inventive contribution."

Verdict: PASS
Reasoning: The opinion identifies what the prior art DID anticipate (low-light
detection) versus what it did NOT (multi-camera capture + frame fusion). That
contrast makes the conceptual gap explicit — the specific inventive mechanism
is named and distinguished from the prior art's actual capability, not merely
stated as absent. Criterion A satisfied.

---

### FAIL — Criteria 1 and 2 (feedback loop: well-known principle, bare assertion)

Overall opinion:
"The core technical contribution of the source patent—iteratively detecting
hallucinations in a first LLM response, regenerating a second response using
the original natural-language input, re-evaluating the second response, and
only rendering it when it is deemed hallucination-free—is not disclosed in the
prior art. While the prior art anticipates basic LLM response generation and a
single-pass hallucination scoring, it does not teach the feedback loop of
regeneration based on hallucination detection nor the conditional rendering step.
Consequently, the key advancement elements (4-6) are novel and non-obvious."

Verdict: FAIL
Reasoning: The opinion identifies what the prior art lacks (feedback loop,
conditional rendering) but does not explain why a PSA in LLM systems would not
apply the well-known concept of iterative refinement/feedback correction to this
problem. Concluding "novel and non-obvious" from a description of absence is a
bare assertion. Criteria 1 and 2.

---

### FAIL — Criterion 1 (specific criteria listed but conceptual gap not argued)

Overall opinion:
"The core technical advancement of the source patent lies in elements 3 and 4,
which introduce context-aware selection criteria (location, proximity, calendar
event count, time until next event, and cross-application data) to dynamically
determine which application's information is displayed in a platter. The prior
art (Patent B) only teaches a customizable UI where the user manually changes
size, placement, or data source of static interface regions; it does not disclose
any automatic, context-driven selection mechanism. Because these key elements are
both novel and non-obvious over the target patent, the source patent retains
substantive inventive merit."

Verdict: FAIL
Reasoning: The opinion names five context criteria and contrasts them with the
prior art's manual UI, but does not explain why a PSA designing a UI system would
not naturally add contextual automation to a manual configuration interface.
Naming the absent criteria and concluding "novel and non-obvious" is a bare
assertion — the conceptual gap is not articulated. Criterion 1.

---

Return ONLY valid JSON in this exact shape:
{
  "opinion_check": {
    "uses_psa_vocabulary": true or false,
    "has_psa_argument": true or false,
    "note": "which criterion (A/B/C for PASS, or 1/2 for FAIL) and one sentence why"
  },
  "verdict": "PASS" or "FAIL",
  "comment": "2-3 sentences. Quote a specific phrase from the overall_opinion. State which criterion applies."
}

verdict must be FAIL if has_psa_argument is false.
verdict must be PASS if has_psa_argument is true."""


def _build_judge_prompt(parsed_output: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the judge call."""
    overall = parsed_output.get("overall_opinion") or "(no overall opinion provided)"
    user_prompt = f"Overall opinion:\n{overall}"
    return _SYSTEM_PROMPT, user_prompt


def _parse_judge_response(raw: str) -> dict:
    """Parse and validate a raw judge response string. Raises ValueError on bad JSON
    or missing opinion_check.has_psa_argument."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge returned non-JSON: {raw!r}") from e
    opinion_check = parsed.get("opinion_check")
    if not isinstance(opinion_check, dict) or not isinstance(
        opinion_check.get("has_psa_argument"), bool
    ):
        raise ValueError(f"Judge response missing opinion_check.has_psa_argument: {raw!r}")
    return parsed


def _call_judge(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Call the judge model and parse JSON. Returns (parsed_dict, raw_content).

    Raises ValueError if the response is not valid JSON or opinion_check is missing.
    """
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    return _parse_judge_response(raw), raw


_RETRY_ATTEMPTS = 5


async def _call_judge_async(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Async version of _call_judge for use with AsyncGroq.

    Retries up to _RETRY_ATTEMPTS times on 429 rate-limit errors, waiting the
    duration Groq suggests in the error message before each retry.
    """
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            response = await client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            return _parse_judge_response(raw), raw
        except Exception as e:
            is_rate_limit = "429" in str(e) or "rate_limit_exceeded" in str(e)
            if is_rate_limit and attempt < _RETRY_ATTEMPTS - 1:
                match = re.search(r"try again in (\d+(?:\.\d+)?)s", str(e))
                wait = float(match.group(1)) + 1.0 if match else 15.0
                print(
                    f"phosita_eval: 429 rate limit — retrying in {wait:.1f}s "
                    f"(attempt {attempt + 1}/{_RETRY_ATTEMPTS})",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait)
                continue
            raise


def _short_circuit_result(run_id: str, comment: str) -> dict:
    return {
        "run_id": run_id,
        "eval_name": "absent_phosita_reasoning",
        "verdict": "PASS",
        "comment": comment,
        "judge_raw": "",
        "config": {
            "judge_model": JUDGE_MODEL,
            "prompt_version": PROMPT_VERSION,
            "temperature": JUDGE_TEMPERATURE,
        },
    }


def _build_result(run_id: str, verdict: str, comment: str, raw: str, parsed_judge: dict) -> dict:
    config = {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }
    has_psa = parsed_judge.get("opinion_check", {}).get("has_psa_argument")
    if (has_psa is False and verdict == "PASS") or (has_psa is True and verdict == "FAIL"):
        print(
            f"phosita_eval: {run_id}: warning: has_psa_argument={has_psa} "
            f"inconsistent with verdict={verdict!r}; trusting verdict",
            file=sys.stderr,
        )
    return {
        "run_id": run_id,
        "eval_name": "absent_phosita_reasoning",
        "verdict": verdict,
        "comment": comment,
        "judge_raw": raw,
        "config": config,
    }


def _prepare_trace(trace: dict) -> dict | tuple[str, str, str] | None:
    """Shared preamble for evaluate_trace and evaluate_trace_async.

    Returns:
    - None: trace should be skipped (already logged to stderr)
    - dict: short-circuit PASS result (return directly, no judge call needed)
    - (run_id, system, user): ready for judge call
    """
    run_id = trace.get("run_id")
    parsed = trace.get("parsed_output")
    if not parsed:
        print(f"phosita_eval: skipping {run_id}: no parsed_output", file=sys.stderr)
        return None

    mappings = parsed.get("element_mappings") or []

    if not mappings:
        return _short_circuit_result(run_id, "N/A: no elements analysed.")

    if not _has_novel_elements(mappings):
        return _short_circuit_result(run_id, "N/A: no novel elements; obviousness reasoning not required.")

    system, user = _build_judge_prompt(parsed)
    return run_id, system, user


def evaluate_trace(trace: dict, client: Any) -> dict | None:
    """Evaluate a single trace. Returns the verdict dict, or None on operational error."""
    prep = _prepare_trace(trace)
    if prep is None:
        return None
    if isinstance(prep, dict):
        return prep
    run_id, system, user = prep

    try:
        parsed_judge, raw = _call_judge(client, system, user)
    except ValueError as e:
        print(f"phosita_eval: skipping {run_id}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"phosita_eval: skipping {run_id}: judge call failed: {e}", file=sys.stderr)
        return None

    verdict = parsed_judge.get("verdict")
    comment = parsed_judge.get("comment", "")
    if verdict not in ("PASS", "FAIL"):
        print(
            f"phosita_eval: skipping {run_id}: judge returned invalid verdict {verdict!r}",
            file=sys.stderr,
        )
        return None

    return _build_result(run_id, verdict, comment, raw, parsed_judge)


async def evaluate_trace_async(trace: dict, client: Any) -> dict | None:
    """Async version of evaluate_trace for concurrent runner use."""
    prep = _prepare_trace(trace)
    if prep is None:
        return None
    if isinstance(prep, dict):
        return prep
    run_id, system, user = prep

    try:
        parsed_judge, raw = await _call_judge_async(client, system, user)
    except ValueError as e:
        print(f"phosita_eval: skipping {run_id}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"phosita_eval: skipping {run_id}: judge call failed: {e}", file=sys.stderr)
        return None

    verdict = parsed_judge.get("verdict")
    comment = parsed_judge.get("comment", "")
    if verdict not in ("PASS", "FAIL"):
        print(
            f"phosita_eval: skipping {run_id}: judge returned invalid verdict {verdict!r}",
            file=sys.stderr,
        )
        return None

    return _build_result(run_id, verdict, comment, raw, parsed_judge)
