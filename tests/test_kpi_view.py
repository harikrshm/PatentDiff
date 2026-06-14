# tests/test_kpi_view.py
import json

from core.eval_history import HistoryRecord, append_run
from core.kpi_targets import set_target
from core.kpi_view import Point, current_pass_rate, series, trajectory


def _rec(ts, rate, run_id, kind="phosita"):
    return HistoryRecord(timestamp=ts, eval_kind=kind, trace_set="live",
                         pass_rate=rate, scored=10, prompt_version=None, run_id=run_id)


def test_current_pass_rate_reads_live_eval_file(tmp_path):
    from core.phosita_eval import PROMPT_VERSION
    cfg = {"prompt_version": PROMPT_VERSION}
    with open(tmp_path / "phosita_eval_full.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"run_id": "r0", "verdict": "PASS", "config": cfg}) + "\n")
        f.write(json.dumps({"run_id": "r1", "verdict": "FAIL", "config": cfg}) + "\n")
        # Stale prior-version line for r1 appended AFTER its current-version row —
        # must be ignored, not override the current verdict (the PHOSITA bug).
        f.write(json.dumps({"run_id": "r1", "verdict": "PASS",
                            "config": {"prompt_version": "v2"}}) + "\n")
    rate, scored = current_pass_rate(tmp_path, "live", "phosita")
    assert rate == 0.5 and scored == 2


def test_series_returns_time_ordered_points(tmp_path):
    h = tmp_path / "hist.jsonl"
    append_run([_rec("2026-06-02T10:00:00", 0.6, "b"),
                _rec("2026-06-01T10:00:00", 0.5, "a")], path=h)
    assert series("phosita", history_path=h) == [
        ("2026-06-01T10:00:00", 0.5), ("2026-06-02T10:00:00", 0.6)]


def test_trajectory_assembles_baseline_current_expected(tmp_path):
    h = tmp_path / "hist.jsonl"
    t = tmp_path / "kpi.json"
    append_run([_rec("2026-06-01T10:00:00", 0.5, "a"),
                _rec("2026-06-05T10:00:00", 0.7, "c")], path=h)
    set_target("phosita", 0.9, "2026-09-01", path=t)
    tr = trajectory("phosita", history_path=h, targets_path=t)
    assert tr.baseline == Point("2026-06-01T10:00:00", 0.5)   # earliest
    assert tr.current == Point("2026-06-05T10:00:00", 0.7)    # latest
    assert tr.expected == Point("2026-09-01", 0.9)            # target


def test_trajectory_empty_history_is_all_none(tmp_path):
    tr = trajectory("phosita", history_path=tmp_path / "h.jsonl",
                    targets_path=tmp_path / "t.json")
    assert tr.baseline is None and tr.current is None and tr.expected is None
