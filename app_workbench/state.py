"""App-facing wrappers over core.workbench_state.

PM inputs persist keyed by the active trace set, so each set keeps its own
decision state (annotations, priority inputs). Single-user, file-based.
"""
from __future__ import annotations

from app_workbench.data import STATE_DIR
from core.workbench_state import load_state, save_state


# ── §3 conclusions / per-section free-text comments ──────────────────────────
def get_annotation(section: str, active_set: str, default: str = "") -> str:
    data = load_state(STATE_DIR, "annotations")
    return (data.get(section) or {}).get(active_set, default)


def set_annotation(section: str, active_set: str, value: str) -> None:
    data = load_state(STATE_DIR, "annotations")
    data.setdefault(section, {})[active_set] = value or ""
    save_state(STATE_DIR, "annotations", data)


# ── §4/§5 priority inputs (impact, exposure, layers, rationale) per set ───────
def _priority_defaults() -> dict:
    return {"impact": {}, "exposure": {}, "layers": {}, "rationale": ""}


def get_priority_inputs(active_set: str) -> dict:
    data = load_state(STATE_DIR, "priority_inputs")
    saved = data.get(active_set) or {}
    return {**_priority_defaults(), **saved}


def update_priority_inputs(active_set: str, patch: dict) -> None:
    """Merge `patch` into the active set's priority inputs and persist."""
    data = load_state(STATE_DIR, "priority_inputs")
    cur = {**_priority_defaults(), **(data.get(active_set) or {})}
    cur.update(patch)
    data[active_set] = cur
    save_state(STATE_DIR, "priority_inputs", data)
