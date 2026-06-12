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


from core.experiments import percentile, _measured_latency_tokens


def test_percentile_interpolates():
    xs = [10, 20, 30, 40]
    assert percentile(xs, 0.0) == 10.0
    assert percentile(xs, 1.0) == 40.0
    assert percentile(xs, 0.5) == 25.0   # midpoint of 20 and 30
    assert percentile([], 0.5) == 0.0
    assert percentile([7], 0.9) == 7.0


def _trace_line(run_id, lat, ti, to):
    return json.dumps({"run_id": run_id,
                       "llm_response": {"latency_ms": lat,
                                        "tokens_input": ti, "tokens_output": to}}) + "\n"


def test_measured_latency_tokens_filters_zeros(tmp_path):
    p = tmp_path / "traces.jsonl"
    p.write_text(_trace_line("r1", 100, 10, 5)
                 + _trace_line("r2", 0, 0, 0)        # not captured -> excluded
                 + _trace_line("r3", 300, 30, 15))
    lat, ti, to = _measured_latency_tokens(p)
    assert lat == [100, 300]
    assert ti == [10, 30]
    assert to == [5, 15]


def test_measured_latency_tokens_missing_file(tmp_path):
    lat, ti, to = _measured_latency_tokens(tmp_path / "nope.jsonl")
    assert lat == [] and ti == [] and to == []
