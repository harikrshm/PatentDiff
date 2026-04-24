from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import json
from pathlib import Path

class ElementJudgment(BaseModel):
    element_number: int
    tool_novelty: bool
    tool_inventive_step: bool
    your_verdict: str  # "PASS" or "FAIL"
    critique: str

class OverallOpinionJudgment(BaseModel):
    tool_verdict: str
    your_verdict: str  # "PASS" or "FAIL"
    critique: str

class AnnotationRecord(BaseModel):
    run_id: str
    phase: int  # 1 or 3
    element_judgments: List[ElementJudgment]
    overall_opinion_judgment: OverallOpinionJudgment
    open_coded_failure_modes: Optional[List[str]] = None
    failure_modes: Optional[List[str]] = None
    annotation: str
    reviewed: bool
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "element_judgments": [e.dict() for e in self.element_judgments],
            "overall_opinion_judgment": self.overall_opinion_judgment.dict(),
            "open_coded_failure_modes": self.open_coded_failure_modes,
            "failure_modes": self.failure_modes,
            "annotation": self.annotation,
            "reviewed": self.reviewed,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AnnotationRecord":
        """Create from dictionary (JSON deserialization)."""
        return AnnotationRecord(
            run_id=data["run_id"],
            phase=data["phase"],
            element_judgments=[
                ElementJudgment(**e) for e in data.get("element_judgments", [])
            ],
            overall_opinion_judgment=OverallOpinionJudgment(**data["overall_opinion_judgment"]),
            open_coded_failure_modes=data.get("open_coded_failure_modes"),
            failure_modes=data.get("failure_modes"),
            annotation=data["annotation"],
            reviewed=data["reviewed"],
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )

def load_annotations(filepath: Path) -> Dict[str, AnnotationRecord]:
    """Load annotations from JSONL file. Returns empty dict if file doesn't exist."""
    annotations = {}
    if not filepath.exists():
        return annotations

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                record = AnnotationRecord.from_dict(data)
                annotations[record.run_id] = record
            except Exception as e:
                print(f"Warning: Failed to parse line: {e}")
    return annotations

def save_annotations(filepath: Path, annotations: Dict[str, AnnotationRecord]) -> None:
    """Save annotations to JSONL file (overwrites)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for record in annotations.values():
            f.write(json.dumps(record.to_dict()) + "\n")

def detect_phase(taxonomy_path: Path = None) -> int:
    """Detect which phase to use based on whether taxonomy exists."""
    if taxonomy_path is None:
        taxonomy_path = Path("traces/failure_taxonomy.json")
    return 3 if taxonomy_path.exists() else 1

def load_taxonomy(taxonomy_path: Path) -> Dict[str, str]:
    """Load failure taxonomy. Returns empty dict if file doesn't exist."""
    if not taxonomy_path.exists():
        return {}
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_failure_modes(text: str, delimiter: str = "|") -> List[str]:
    """Parse delimited failure modes from text input."""
    if not text:
        return []
    modes = [mode.strip() for mode in text.split(delimiter)]
    return [m for m in modes if m]
