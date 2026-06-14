# core/kpi_view.py
"""Assembly layer the Dashboard KPI blocks read: current rate, time series, and
the baseline/current/expected trajectory. Combines eval_history + kpi_targets +
the live eval files. core-only (no app_unified dependency)."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

from core.eval_delta import _pass_rate, load_verdict_map
from core.eval_history import HISTORY_PATH, history_for
from core.kpi_targets import TARGETS_PATH, get_target
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION
from core.workbench_data import list_trace_sets


class Point(NamedTuple):
    when: str       # ISO timestamp (history) or ISO date (expected)
    rate: float


class Trajectory(NamedTuple):
    baseline: Optional[Point]
    current: Optional[Point]
    expected: Optional[Point]


def current_pass_rate(traces_dir: Path, trace_set: str, eval_kind: str
                      ) -> tuple[float, int]:
    sets = {s.name: s for s in list_trace_sets(Path(traces_dir))}
    ts = sets.get(trace_set)
    if ts is None:
        return 0.0, 0
    path = ts.phosita_path if eval_kind == "phosita" else ts.citation_path
    pv = PHOSITA_PROMPT_VERSION if eval_kind == "phosita" else None
    rate, _pass, scored = _pass_rate(load_verdict_map(path, prompt_version=pv))
    return rate, scored


def series(eval_kind: str, trace_set: Optional[str] = None,
           history_path: Path = HISTORY_PATH) -> list[tuple[str, float]]:
    return [(r.timestamp, r.pass_rate)
            for r in history_for(eval_kind, trace_set, path=history_path)]


def trajectory(eval_kind: str, history_path: Path = HISTORY_PATH,
               targets_path: Path = TARGETS_PATH) -> Trajectory:
    hist = history_for(eval_kind, path=history_path)
    target = get_target(eval_kind, path=targets_path)

    current = Point(hist[-1].timestamp, hist[-1].pass_rate) if hist else None

    baseline = None
    if hist:
        chosen = None
        if target and target.baseline_run:
            chosen = next((r for r in hist if r.run_id == target.baseline_run), None)
        chosen = chosen or hist[0]
        baseline = Point(chosen.timestamp, chosen.pass_rate)

    expected = Point(target.target_date, target.target_pass_rate) if target else None
    return Trajectory(baseline=baseline, current=current, expected=expected)
