"""Shared constants for §4/§5 (imported by both app.py layout and callbacks)."""
from __future__ import annotations

# Failure modes ↔ the eval whose shape read informs the layer call.
DECISION_MODES = ["Absent PHOSITA", "Citation Text"]
MODE_EVAL = {"Absent PHOSITA": "phosita", "Citation Text": "citation"}

# Architecture layers — L1 cheapest (instruction), L2/L3 capability work.
LAYER_OPTIONS = [
    {"label": "L1 · instruction", "value": "L1"},
    {"label": "L2 · capability", "value": "L2"},
    {"label": "L3 · capability", "value": "L3"},
]
LAYER_RANK = {"L1": 1, "L2": 2, "L3": 3}
LAYER_LABEL = {o["value"]: o["label"] for o in LAYER_OPTIONS}
