# core/eval_history.py
"""Dated history of eval PASS-rates. Append-only JSONL; the eval ruler is frozen,
we only record the rates it produces (via core.eval_delta)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "traces" / "eval_history.jsonl"


class HistoryRecord(BaseModel):
    timestamp: str            # ISO 8601
    eval_kind: str            # "phosita" | "citation"
    trace_set: str
    pass_rate: float          # 0..1
    scored: int               # PASS + FAIL count
    prompt_version: Optional[str] = None
    run_id: str


def append_run(records: list[HistoryRecord], path: Path = HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def load_history(path: Path = HISTORY_PATH) -> list[HistoryRecord]:
    if not Path(path).exists():
        return []
    out: list[HistoryRecord] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(HistoryRecord.model_validate(json.loads(line)))
            except Exception:
                continue   # skip corrupt lines (mirrors load_verdict_map)
    return out


def history_for(eval_kind: str, trace_set: Optional[str] = None,
                path: Path = HISTORY_PATH) -> list[HistoryRecord]:
    rows = [r for r in load_history(path) if r.eval_kind == eval_kind
            and (trace_set is None or r.trace_set == trace_set)]
    return sorted(rows, key=lambda r: r.timestamp)
