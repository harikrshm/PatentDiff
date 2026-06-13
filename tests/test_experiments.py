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


from core.experiments import MIN_COVERAGE, percentile, _measured_latency_tokens


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


from core.experiments import ExperimentMetrics, kpi_target_fail, metrics_for
from core.phosita_eval import PROMPT_VERSION as _PV


def _phosita_eval_line(run_id, verdict):
    return json.dumps({"run_id": run_id, "verdict": verdict,
                       "config": {"prompt_version": _PV}}) + "\n"


def _citation_eval_line(run_id, verdict):
    return json.dumps({"run_id": run_id, "verdict": verdict}) + "\n"


def _make_exp(trace_set="live", override=None):
    return Experiment(
        exp_id="e1", name="t", created="2026-06-01T00:00:00",
        splits=["all"], repetitions=1, trace_set=trace_set,
        phosita_eval_file="phosita_eval_full.jsonl",
        citation_eval_file="citation_text_eval_full.jsonl",
        metrics_override=override)


def test_metrics_for_measured_when_coverage_ok(tmp_path):
    # phosita: 1 PASS of 2 -> pass 0.5 -> fail 0.5; citation: 0 PASS of 2 -> fail 1.0
    (tmp_path / "phosita_eval_full.jsonl").write_text(
        _phosita_eval_line("r1", "PASS") + _phosita_eval_line("r2", "FAIL"))
    (tmp_path / "citation_text_eval_full.jsonl").write_text(
        _citation_eval_line("r1", "FAIL") + _citation_eval_line("r2", "FAIL"))
    # MIN_COVERAGE nonzero latency samples -> measured wins over override
    lat_vals = [100 * (i + 1) for i in range(MIN_COVERAGE)]
    lines = "".join(_trace_line(f"r{i}", v, 10, 5) for i, v in enumerate(lat_vals))
    (tmp_path / "traces.jsonl").write_text(lines)
    m = metrics_for(_make_exp(override={"lat_p50": 1, "lat_p99": 2,
                                        "tok_in": 3, "tok_out": 4}),
                    traces_dir=tmp_path)
    assert isinstance(m, ExperimentMetrics)
    assert m.phosita_fail == 0.5
    assert m.citation_fail == 1.0
    assert m.lat_p50 == percentile(lat_vals, 0.5)
    assert m.tok_in == 10 and m.tok_out == 5      # not the override


def test_metrics_for_uses_override_when_coverage_thin(tmp_path):
    (tmp_path / "phosita_eval_full.jsonl").write_text(_phosita_eval_line("r1", "PASS"))
    (tmp_path / "citation_text_eval_full.jsonl").write_text(_citation_eval_line("r1", "PASS"))
    # only 2 nonzero latency samples (< MIN_COVERAGE) -> override is used
    (tmp_path / "traces.jsonl").write_text(
        _trace_line("r1", 100, 10, 5) + _trace_line("r2", 200, 20, 10))
    m = metrics_for(_make_exp(override={"lat_p50": 4400, "lat_p99": 24000,
                                        "tok_in": 3900, "tok_out": 2300}),
                    traces_dir=tmp_path)
    assert m.lat_p50 == 4400 and m.lat_p99 == 24000
    assert m.tok_in == 3900 and m.tok_out == 2300


def test_kpi_target_fail(tmp_path):
    p = tmp_path / "kpi_targets.json"
    p.write_text(json.dumps({"phosita": {"target_pass_rate": 0.85,
                                         "target_date": "2026-09-01",
                                         "baseline_run": None}}))
    assert kpi_target_fail("phosita", path=p) == 0.15  # 1 - 0.85
    assert kpi_target_fail("citation", path=p) is None


def test_metrics_for_thin_coverage_no_override_is_zero(tmp_path):
    # < MIN_COVERAGE nonzero latency samples AND no override -> latency/tokens 0.0
    (tmp_path / "phosita_eval_full.jsonl").write_text(_phosita_eval_line("r1", "PASS"))
    (tmp_path / "citation_text_eval_full.jsonl").write_text(_citation_eval_line("r1", "PASS"))
    (tmp_path / "traces.jsonl").write_text(_trace_line("r1", 100, 10, 5))  # only 1 sample
    m = metrics_for(_make_exp(override=None), traces_dir=tmp_path)
    assert m.lat_p50 == 0.0 and m.lat_p99 == 0.0
    assert m.tok_in == 0.0 and m.tok_out == 0.0
    # eval fail-rates still computed: 1 PASS -> fail 0.0
    assert m.phosita_fail == 0.0 and m.citation_fail == 0.0


def test_metrics_for_missing_eval_files_give_zero_fail(tmp_path):
    # no eval files at all -> nothing scored -> fail-rate 0.0 (not a crash)
    (tmp_path / "traces.jsonl").write_text(_trace_line("r1", 100, 10, 5))
    m = metrics_for(_make_exp(override=None), traces_dir=tmp_path)
    assert m.phosita_fail == 0.0 and m.citation_fail == 0.0
