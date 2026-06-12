# tests/test_experiments.py
import json

from core.experiments import Experiment, last_n, load_experiments


def _exp_line(exp_id, name, created, trace_set="live"):
    return json.dumps({
        "exp_id": exp_id, "name": name, "created": created,
        "splits": ["all"], "repetitions": 1, "trace_set": trace_set,
        "phosita_eval_file": "phosita_eval_full.jsonl",
        "citation_eval_file": "citation_text_eval_full.jsonl",
    }) + "\n"


def test_load_skips_corrupt_lines(tmp_path):
    p = tmp_path / "experiments.jsonl"
    p.write_text(_exp_line("e1", "baseline", "2026-06-01T00:00:00")
                 + "{not valid json\n"
                 + _exp_line("e2", "live", "2026-06-02T00:00:00"))
    exps = load_experiments(p)
    assert [e.exp_id for e in exps] == ["e1", "e2"]
    assert exps[0].splits == ["all"] and exps[0].repetitions == 1


def test_load_missing_is_empty(tmp_path):
    assert load_experiments(tmp_path / "nope.jsonl") == []


def test_last_n_orders_by_created_and_tails(tmp_path):
    p = tmp_path / "experiments.jsonl"
    p.write_text(_exp_line("e2", "b", "2026-06-02T00:00:00")
                 + _exp_line("e1", "a", "2026-06-01T00:00:00")
                 + _exp_line("e4", "d", "2026-06-04T00:00:00")
                 + _exp_line("e3", "c", "2026-06-03T00:00:00"))
    got = last_n(3, path=p)
    assert [e.exp_id for e in got] == ["e2", "e3", "e4"]  # oldest->newest, tail 3


def test_last_n_zero_returns_empty(tmp_path):
    p = tmp_path / "experiments.jsonl"
    p.write_text(_exp_line("e1", "a", "2026-06-01T00:00:00"))
    assert last_n(0, path=p) == []
