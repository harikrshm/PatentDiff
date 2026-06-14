# core/eval_history.py
"""Dated history of eval PASS-rates. Append-only JSONL; the eval ruler is frozen,
we only record the rates it produces (via core.eval_delta)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from core.eval_delta import _pass_rate, load_verdict_map
from core.phosita_eval import PROMPT_VERSION as _PHOSITA_PV
from core.workbench_data import list_trace_sets

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "traces" / "eval_history.jsonl"

# best-effort prompt version per eval kind (citation eval exposes none)
PROMPT_VERSIONS = {"phosita": _PHOSITA_PV, "citation": None}


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


def backfill_from_eval_files(traces_dir: Path, path: Path = HISTORY_PATH) -> int:
    """Seed history from existing eval files (timestamp = file mtime).

    Idempotent: dedup on (eval_kind, trace_set, timestamp). Returns count added.
    """
    existing = {(r.eval_kind, r.trace_set, r.timestamp) for r in load_history(path)}
    new: list[HistoryRecord] = []
    for ts in list_trace_sets(Path(traces_dir)):
        for kind, p in (("phosita", ts.phosita_path), ("citation", ts.citation_path)):
            if not p.exists():
                continue
            rate, _pass, scored = _pass_rate(
                load_verdict_map(p, prompt_version=PROMPT_VERSIONS.get(kind)))
            if scored == 0:
                continue
            stamp = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
            key = (kind, ts.name, stamp)
            if key in existing:
                continue
            existing.add(key)
            new.append(HistoryRecord(
                timestamp=stamp, eval_kind=kind, trace_set=ts.name,
                pass_rate=rate, scored=scored,
                prompt_version=PROMPT_VERSIONS.get(kind),
                run_id=f"backfill-{kind}-{ts.name}"))
    if new:
        append_run(new, path=path)
    return len(new)
