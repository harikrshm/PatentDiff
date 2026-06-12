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
    if n <= 0:
        return []
    rows = sorted(load_experiments(path), key=lambda e: e.created)
    return rows[-n:]


def percentile(xs: list[float], p: float) -> float:
    """Linear-interpolated percentile, numpy-free. p in [0, 1]. Empty -> 0.0."""
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return float(s[int(k)])
    return float(s[f] * (c - k) + s[c] * (k - f))


def _measured_latency_tokens(trace_path: Path):
    """Read nonzero (latency_ms, tokens_input, tokens_output) from a trace JSONL.

    Zeros mean "not captured for that trace" and are excluded. Missing file or
    corrupt lines yield empty lists.
    """
    lat: list[float] = []
    tin: list[float] = []
    tout: list[float] = []
    if not Path(trace_path).exists():
        return lat, tin, tout
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lr = (json.loads(line).get("llm_response") or {})
            except Exception:
                continue
            if lr.get("latency_ms"):
                lat.append(lr["latency_ms"])
            if lr.get("tokens_input"):
                tin.append(lr["tokens_input"])
            if lr.get("tokens_output"):
                tout.append(lr["tokens_output"])
    return lat, tin, tout


class ExperimentMetrics(NamedTuple):
    phosita_fail: float           # 0..1
    citation_fail: float          # 0..1
    lat_p50: float                # ms
    lat_p99: float                # ms
    tok_in: float                 # tokens (median)
    tok_out: float                # tokens (median)


def _trace_path(traces_dir: Path, trace_set: str) -> Path:
    if trace_set == "live":
        return traces_dir / "traces.jsonl"
    return traces_dir / f"traces.{trace_set}.jsonl"


def _fail_rate(eval_path: Path, prompt_version: Optional[str]) -> float:
    """FAIL-rate = 1 - PASS-rate, reusing the frozen ruler math. 0.0 if unscored."""
    rate, _pass, scored = _pass_rate(load_verdict_map(eval_path, prompt_version=prompt_version))
    return (1.0 - rate) if scored else 0.0


def metrics_for(exp: Experiment, traces_dir: Path = TRACES_DIR) -> ExperimentMetrics:
    phosita_fail = _fail_rate(traces_dir / exp.phosita_eval_file, PHOSITA_PROMPT_VERSION)
    citation_fail = _fail_rate(traces_dir / exp.citation_eval_file, None)

    lat, tin, tout = _measured_latency_tokens(_trace_path(traces_dir, exp.trace_set))
    if len(lat) >= MIN_COVERAGE:
        lat_p50 = percentile(lat, 0.5)
        lat_p99 = percentile(lat, 0.99)
        tok_in = float(median(tin)) if tin else 0.0
        tok_out = float(median(tout)) if tout else 0.0
    elif exp.metrics_override:
        o = exp.metrics_override
        lat_p50 = float(o.get("lat_p50", 0))
        lat_p99 = float(o.get("lat_p99", 0))
        tok_in = float(o.get("tok_in", 0))
        tok_out = float(o.get("tok_out", 0))
    else:
        lat_p50 = lat_p99 = tok_in = tok_out = 0.0

    return ExperimentMetrics(phosita_fail, citation_fail,
                             lat_p50, lat_p99, tok_in, tok_out)


def kpi_target_fail(eval_kind: str, path: Path = TARGETS_PATH) -> Optional[float]:
    """Target FAIL-rate (1 - target_pass_rate) for an eval kind, or None if unset."""
    t = get_target(eval_kind, path=path)
    return round(1.0 - t.target_pass_rate, 10) if t else None
