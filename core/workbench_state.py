"""File-based JSON persistence for the Eval Workbench (single-user).

State files live under a state dir: layout.json, annotations.json,
priority_inputs.json. Each holds one JSON object; missing files read as {}.
"""
from __future__ import annotations

import json
from pathlib import Path

VALID_NAMES = {"layout", "annotations", "priority_inputs"}


def _path(state_dir: Path, name: str) -> Path:
    if name not in VALID_NAMES:
        raise ValueError(f"unknown state name: {name!r} (expected one of {VALID_NAMES})")
    return Path(state_dir) / f"{name}.json"


def load_state(state_dir: Path, name: str) -> dict:
    path = _path(state_dir, name)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state_dir: Path, name: str, data: dict) -> None:
    path = _path(state_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
