"""Shared data-access helpers for the workbench callbacks.

Thin layer over core.workbench_data so every section loads the active trace set
the same way. Read-only; all reads happen at callback time.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.workbench_data import TraceSet, list_trace_sets, load_merged

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACES_DIR = REPO_ROOT / "traces"
ANNOTATIONS_PATH = TRACES_DIR / "traces_annotations.jsonl"
STATE_DIR = TRACES_DIR / "workbench_state"


def trace_set_options() -> list[dict]:
    try:
        return [{"label": s.name, "value": s.name} for s in list_trace_sets(TRACES_DIR)]
    except Exception:
        return []


def resolve_set(active_name: str | None) -> TraceSet | None:
    """Lenient: falls back to the first set if the name is unknown (for display)."""
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    if not sets:
        return None
    return sets.get(active_name) or next(iter(sets.values()))


def resolve_set_strict(active_name: str | None) -> TraceSet | None:
    """Exact match only — no fallback. Use before side-effecting actions (run eval)."""
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    return sets.get(active_name)


def load(active_name: str | None) -> pd.DataFrame:
    """Merged frame for the active trace set (empty frame if none found)."""
    ts = resolve_set(active_name)
    if ts is None:
        return pd.DataFrame(columns=[
            "run_id", "claim_type", "claim_length", "relationship",
            "dim_source", "phosita_verdict", "citation_verdict",
        ])
    return load_merged(ts, ANNOTATIONS_PATH)
