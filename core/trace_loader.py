import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class PatentInput(BaseModel):
    label: str
    independent_claim: str
    specification: str

class ElementMapping(BaseModel):
    element_number: int
    element_text: str
    corresponding_text: str
    novelty: bool
    inventive_step: bool
    verdict: str
    comment: str

class ParsedOutput(BaseModel):
    element_mappings: List[ElementMapping]
    overall_opinion: str

class LLMResponse(BaseModel):
    raw_output: str
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: int

class Trace(BaseModel):
    run_id: str
    timestamp: str
    inputs: Dict[str, Any]  # source_patent, target_patent
    llm_response: LLMResponse
    parsed_output: Optional[ParsedOutput]
    status: str
    error: Optional[str]
    truncation_warnings: Optional[List[str]] = None

    class Config:
        extra = "allow"  # Allow extra fields from JSON

def load_traces(filepath: Path) -> List[Trace]:
    """Load traces from JSONL file."""
    traces = []
    if not filepath.exists():
        return traces

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Parse nested objects carefully
                if "llm_response" in data and data["llm_response"]:
                    data["llm_response"] = LLMResponse(**data["llm_response"])
                if "parsed_output" in data and data["parsed_output"]:
                    parsed = data["parsed_output"]
                    if "element_mappings" in parsed:
                        parsed["element_mappings"] = [
                            ElementMapping(**em) for em in parsed["element_mappings"]
                        ]
                    data["parsed_output"] = ParsedOutput(**parsed)

                trace = Trace(**data)
                traces.append(trace)
            except Exception as e:
                print(f"Warning: Failed to parse trace at line {i}: {e}")

    return traces
