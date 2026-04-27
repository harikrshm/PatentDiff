from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import json
from pathlib import Path

class AnnotationRecord(BaseModel):
    run_id: str
    phase: int  # 1 or 3
    open_coded_failure_modes: Optional[List[str]] = None  # Phase 1: free-form failure modes
    failure_modes: Optional[List[str]] = None  # Phase 3: taxonomy-based failure mode IDs
    verdict: str  # "PASS" or "FAIL"
    comment: str
    reviewed: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dimensions: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "open_coded_failure_modes": self.open_coded_failure_modes,
            "failure_modes": self.failure_modes,
            "verdict": self.verdict,
            "comment": self.comment,
            "reviewed": self.reviewed,
            "timestamp": self.timestamp,
            "dimensions": self.dimensions,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AnnotationRecord":
        """Create from dictionary (JSON deserialization)."""
        return AnnotationRecord(
            run_id=data["run_id"],
            phase=data["phase"],
            open_coded_failure_modes=data.get("open_coded_failure_modes"),
            failure_modes=data.get("failure_modes"),
            verdict=data["verdict"],
            comment=data["comment"],
            reviewed=data.get("reviewed", False),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            dimensions=data.get("dimensions"),
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
        taxonomy_path = Path("failure_taxonomy.json")
    return 3 if taxonomy_path.exists() else 1

def load_taxonomy(taxonomy_path: Path) -> Dict[str, str]:
    """Load failure taxonomy. Returns empty dict if file doesn't exist or is invalid JSON."""
    if not taxonomy_path.exists():
        return {}
    try:
        with open(taxonomy_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def parse_failure_modes(text: str, delimiter: str = "|") -> List[str]:
    """Parse delimited failure modes from text input."""
    if not text:
        return []
    modes = [mode.strip() for mode in text.split(delimiter)]
    return [m for m in modes if m]
