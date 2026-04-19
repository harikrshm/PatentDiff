import uuid
from datetime import datetime, timezone

from core.models import AnalysisReport, PatentInput


def build_trace_record(
    source_patent: PatentInput,
    target_patent: PatentInput,
    system_prompt: str,
    user_prompt: str,
    llm_response: dict,
    parsed_output: AnalysisReport | None,
    status: str,
    error: str | None,
) -> dict:
    return {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "source_patent": {
                "label": source_patent.label,
                "claim": source_patent.independent_claim,
                "specification": source_patent.specification,
            },
            "target_patent": {
                "label": target_patent.label,
                "claim": target_patent.independent_claim,
                "specification": target_patent.specification,
            },
        },
        "prompt": {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        },
        "llm_response": llm_response,
        "parsed_output": parsed_output.model_dump() if parsed_output else None,
        "status": status,
        "error": error,
    }
