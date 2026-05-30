"""LLM-judge eval for the `absent_phosita_reasoning` failure mode.

See docs/superpowers/specs/2026-05-30-phosita-judge-v2-design.md for design.
"""
from __future__ import annotations

import json
import sys
from typing import Any

PROMPT_VERSION = "v2"
JUDGE_MODEL = "qwen/qwen3-32b"
JUDGE_TEMPERATURE = 0.2
JUDGE_MAX_TOKENS = 1024


def _has_novel_elements(element_mappings: list[dict]) -> bool:
    """True if at least one element is marked novelty='N'."""
    return any(em.get("novelty") == "N" for em in element_mappings)


_SYSTEM_PROMPT = """You are evaluating a patent obviousness analysis produced by an AI tool.
The tool writes an overall_opinion on whether a source patent is valid
given a target patent (prior art).

Your job: judge whether the overall_opinion contains genuine
person-of-ordinary-skill-in-the-art (PSA) obviousness reasoning.

Rules:

1. CONCLUSION TEST — PSA vocabulary is not reasoning.
   Phrases like "non-obvious", "novel and non-obvious", "would not be
   obvious to a person of ordinary skill" are legal conclusions.
   Their presence alone does NOT make a PASS. You must find an
   argument, not just a label.

2. WHAT COUNTS AS REASONING — the opinion must engage with WHY.
   Reasoning explains: what background knowledge or capability a PSA
   has, what prior-art components a PSA would naturally combine, or
   why the specific step or combination is non-trivial given what a
   PSA knows. A one-sentence explanation grounded in the technology
   is sufficient.

3. COMPLETE-ABSENCE IMPLICIT ARGUMENT.
   When the opinion documents that specific named technical mechanisms
   are entirely absent from prior art — not merely unmatched by label,
   but architecturally foreign — that absence is itself an implicit
   PSA argument (a PSA cannot combine what does not exist). In this
   case mark has_psa_argument=true even without explicit PSA language.

4. ALL-NOVEL SHORTCUT.
   If the opinion states that every claim element is novel (no prior
   art overlap at all), obviousness is vacuous. Mark verdict PASS.

Return ONLY valid JSON in this exact shape:
{
  "opinion_check": {
    "uses_psa_vocabulary": true or false,
    "has_psa_argument": true or false,
    "note": "one sentence explaining your classification"
  },
  "verdict": "PASS" or "FAIL",
  "comment": "1-3 sentences explaining the verdict. Quote specific phrases from the overall_opinion to justify."
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


async def _call_judge_async(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Async version of _call_judge for use with AsyncGroq."""
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
