# core/kpi_targets.py
"""PM-set KPI targets per eval kind. Stored as a small JSON dict the dashboard
block 6 edits."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = REPO_ROOT / "traces" / "kpi_targets.json"


class Target(BaseModel):
    target_pass_rate: float       # 0..1
    target_date: str              # ISO date "YYYY-MM-DD"
    baseline_run: Optional[str] = None


def load_targets(path: Path = TARGETS_PATH) -> dict[str, Target]:
    if not Path(path).exists():
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
    return {k: Target.model_validate(v) for k, v in raw.items()}


def get_target(eval_kind: str, path: Path = TARGETS_PATH) -> Optional[Target]:
    return load_targets(path).get(eval_kind)


def set_target(eval_kind: str, target_pass_rate: float, target_date: str,
               baseline_run: Optional[str] = None, path: Path = TARGETS_PATH) -> None:
    if not 0.0 <= target_pass_rate <= 1.0:
        raise ValueError("target_pass_rate must be between 0 and 1")
    date.fromisoformat(target_date)  # raises ValueError on a bad date
    targets = load_targets(path)
    targets[eval_kind] = Target(target_pass_rate=target_pass_rate,
                                target_date=target_date, baseline_run=baseline_run)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps({k: v.model_dump() for k, v in targets.items()}, indent=2),
        encoding="utf-8")
