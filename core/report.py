import json
import re

from core.models import AnalysisReport


def parse_llm_response(raw_output: str) -> AnalysisReport:
    """Parse the raw LLM output string into an AnalysisReport.

    Handles both plain JSON and JSON wrapped in markdown code fences.
    Raises ValueError if parsing fails.
    """
    text = raw_output.strip()

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

    try:
        return AnalysisReport.model_validate(data)
    except Exception as e:
        raise ValueError(f"Failed to validate LLM response against schema: {e}") from e
