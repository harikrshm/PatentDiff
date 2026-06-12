# core/experiments.py
"""Experiment manifest + on-read aggregation for the Comparison experiment
tracker. Append-only JSONL manifest (traces/experiments.jsonl); aggregates are
computed when read from the referenced trace/eval files. Core-only (no
app_unified import), mirroring core/kpi_view.py."""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import NamedTuple, Optional

from pydantic import BaseModel

from core.eval_delta import _pass_rate, load_verdict_map
from core.kpi_targets import TARGETS_PATH, get_target
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACES_DIR = REPO_ROOT / "traces"
MANIFEST_PATH = TRACES_DIR / "experiments.jsonl"

# Below this many measured (nonzero) latency samples, fall back to the manifest's
# metrics_override rather than reporting misleadingly sparse percentiles.
MIN_COVERAGE = 5


class Experiment(BaseModel):
    exp_id: str
    name: str
    created: str                  # ISO 8601; ordering key
    splits: list[str]
    repetitions: int
    trace_set: str                # resolves to traces.<set>.jsonl (live -> traces.jsonl)
    phosita_eval_file: str        # filename under traces/
    citation_eval_file: str
    metrics_override: Optional[dict] = None


def load_experiments(path: Path = MANIFEST_PATH) -> list[Experiment]:
    if not Path(path).exists():
        return []
    out: list[Experiment] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Experiment.model_validate(json.loads(line)))
            except Exception:
                continue   # skip corrupt lines (mirrors core/eval_history.load_history)
    return out


def last_n(n: int = 4, path: Path = MANIFEST_PATH) -> list[Experiment]:
    """The n most recent experiments, oldest->newest, by `created`."""
    rows = sorted(load_experiments(path), key=lambda e: e.created)
    return rows[-n:]
