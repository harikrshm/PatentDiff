"""LLM-judge eval for the `absent_phosita_reasoning` failure mode.

See docs/superpowers/specs/2026-05-27-phosita-llm-judge-design.md for design.
"""
from __future__ import annotations

import json
import sys
from typing import Any

PROMPT_VERSION = "v1"
JUDGE_MODEL = "qwen/qwen3-32b"
JUDGE_TEMPERATURE = 0.2
JUDGE_MAX_TOKENS = 1024


def _has_novel_elements(element_mappings: list[dict]) -> bool:
    """True if at least one element is marked novelty='N'."""
    return any(em.get("novelty") == "N" for em in element_mappings)


_SYSTEM_PROMPT = """You are evaluating a patent obviousness analysis. The analysis was produced
by an AI tool that assesses whether a source patent's independent claim is
invalid given a target patent (prior art). For each claim element, the tool
records novelty (Y/N) and inventive_step (Y/N), with a reasoning comment.
The tool also writes an overall_opinion on the source patent's validity.

Your job: judge whether the analysis contains genuine obviousness reasoning
grounded in the person-of-ordinary-skill-in-the-art (PSA) standard.

A PASS analysis:
- The overall_opinion explicitly engages with WHY novel elements are
  obvious or non-obvious to a PSA - it doesn't just state a conclusion.
- The obviousness claims in the overall_opinion are supported by the
  per-element comments (the elements actually contain the reasoning the
  overall_opinion claims).

A FAIL analysis (either pattern triggers FAIL):
- The overall_opinion is silent on obviousness, or asserts non-obviousness
  by default without engaging PSA reasoning ("all novel elements are
  non-obvious", "the source patent is valid because elements are novel").
- The overall_opinion claims obviousness reasoning that the element
  comments don't actually support - hand-waving disconnected from the
  per-element analysis.

Focus only on elements where novelty=N (the obviousness question only
applies to novel elements). Elements with novelty=Y are out of scope -
they're already disclosed, so obviousness doesn't matter.

Return ONLY valid JSON:
{
  "verdict": "PASS" or "FAIL",
  "comment": "1-3 sentences explaining why. Cite specific elements or quote phrases from overall_opinion to justify."
}"""


def _build_judge_prompt(parsed_output: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the judge call."""
    mappings = parsed_output.get("element_mappings") or []
    overall = parsed_output.get("overall_opinion") or "(no overall opinion provided)"

    element_lines = []
    for em in mappings:
        element_lines.append(
            f"Element {em.get('element_number')}:\n"
            f"  novelty: {em.get('novelty')}\n"
            f"  inventive_step: {em.get('inventive_step')}\n"
            f"  verdict: {em.get('verdict')}\n"
            f"  comment: {em.get('comment')}"
        )
    elements_block = "\n\n".join(element_lines) if element_lines else "(no element mappings)"

    user_prompt = (
        "ANALYSIS TO JUDGE:\n\n"
        "Element mappings:\n"
        f"{elements_block}\n\n"
        "Overall opinion:\n"
        f"{overall}"
    )
    return _SYSTEM_PROMPT, user_prompt


def _call_judge(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Call the judge model and parse JSON. Returns (parsed_dict, raw_content).

    Raises ValueError if the response is not valid JSON.
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
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge returned non-JSON: {raw!r}") from e
    return parsed, raw


def evaluate_trace(trace: dict, client: Any) -> dict | None:
    """Evaluate a single trace. Returns the verdict dict, or None on operational error."""
    run_id = trace.get("run_id")
    parsed = trace.get("parsed_output")
    if not parsed:
        print(f"phosita_eval: skipping {run_id}: no parsed_output", file=sys.stderr)
        return None

    mappings = parsed.get("element_mappings") or []
    config = {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }

    if not mappings:
        return {
            "run_id": run_id,
            "eval_name": "absent_phosita_reasoning",
            "verdict": "PASS",
            "comment": "N/A: no elements analysed.",
            "judge_raw": "",
            "config": config,
        }

    if not _has_novel_elements(mappings):
        return {
            "run_id": run_id,
            "eval_name": "absent_phosita_reasoning",
            "verdict": "PASS",
            "comment": "N/A: no novel elements; obviousness reasoning not required.",
            "judge_raw": "",
            "config": config,
        }

    system, user = _build_judge_prompt(parsed)
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

    return {
        "run_id": run_id,
        "eval_name": "absent_phosita_reasoning",
        "verdict": verdict,
        "comment": comment,
        "judge_raw": raw,
        "config": config,
    }
