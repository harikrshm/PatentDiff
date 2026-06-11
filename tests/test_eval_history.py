# tests/test_eval_history.py
from core.eval_history import HistoryRecord, append_run, load_history, history_for


def _rec(ts, kind, rate, run_id, trace_set="live"):
    return HistoryRecord(timestamp=ts, eval_kind=kind, trace_set=trace_set,
                         pass_rate=rate, scored=10, prompt_version=None, run_id=run_id)


def test_append_and_load_round_trip(tmp_path):
    p = tmp_path / "hist.jsonl"
    append_run([_rec("2026-06-01T10:00:00", "phosita", 0.5, "a"),
                _rec("2026-06-01T10:00:00", "citation", 0.6, "a")], path=p)
    rows = load_history(p)
    assert len(rows) == 2
    assert rows[0].eval_kind == "phosita" and rows[0].pass_rate == 0.5


def test_load_missing_is_empty(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == []


def test_history_for_filters_and_sorts(tmp_path):
    p = tmp_path / "hist.jsonl"
    append_run([_rec("2026-06-03T10:00:00", "phosita", 0.7, "c")], path=p)
    append_run([_rec("2026-06-01T10:00:00", "phosita", 0.5, "a"),
                _rec("2026-06-02T10:00:00", "citation", 0.6, "b")], path=p)
    ph = history_for("phosita", path=p)
    assert [r.run_id for r in ph] == ["a", "c"]   # sorted by timestamp asc
    assert all(r.eval_kind == "phosita" for r in ph)
