"""Single-trace regeneration: re-run the model under test for one trace dict
with a given system prompt. Extracted from scripts/regenerate_traces so the
Experiment Agent runner and the CLI share one implementation."""
from __future__ import annotations

from datetime import datetime, timezone

from core.llm import build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response


def regenerate_one(trace: dict, system_prompt: str) -> dict:
    inputs = trace["inputs"]
    source = PatentInput(**inputs["source_patent"])
    target = PatentInput(**inputs["target_patent"])
    user_prompt, truncation_warnings = build_user_prompt(source, target)

    parsed_dump = None
    status = "ok"
    error = None
    llm_response = {"raw_output": "", "model": "", "tokens_input": 0,
                    "tokens_output": 0, "latency_ms": 0}
    try:
        llm_response = call_groq(system_prompt, user_prompt)
        try:
            parsed = parse_llm_response(llm_response["raw_output"])
            parsed_dump = parsed.model_dump()
        except ValueError as parse_err:
            status = "parse_error"
            error = str(parse_err)
    except Exception as api_err:
        status = "api_error"
        error = str(api_err)

    return {
        "run_id": trace["run_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "prompt": {"system_prompt": system_prompt, "user_prompt": user_prompt},
        "llm_response": llm_response,
        "parsed_output": parsed_dump,
        "status": status,
        "error": error,
        "truncation_warnings": truncation_warnings,
    }
