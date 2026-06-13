# tests/test_comparison_page.py
import json

from app_unified.pages import eval_comparison
from core.experiments import Experiment, ExperimentMetrics


def _pair(name, ph_fail, ct_fail, p50=1000, p99=2000, ti=100, to=50):
    e = Experiment(exp_id=name, name=name, created="2026-06-01T00:00:00",
                   splits=["all"], repetitions=1, trace_set="live",
                   phosita_eval_file="phosita_eval_full.jsonl",
                   citation_eval_file="citation_text_eval_full.jsonl")
    m = ExperimentMetrics(ph_fail, ct_fail, p50, p99, ti, to)
    return (e, m)


def test_build_figures_three_grouped_bar_charts():
    pairs = [_pair("baseline", 0.46, 0.55), _pair("live", 0.33, 0.45)]
    fail_fig, lat_fig, tok_fig = eval_comparison.build_figures(pairs)
    # eval chart: two series PHOSITA / Citation over both experiments
    names = {t.name for t in fail_fig.data}
    assert names == {"PHOSITA", "Citation"}
    phosita_trace = next(t for t in fail_fig.data if t.name == "PHOSITA")
    assert list(phosita_trace.x) == ["baseline", "live"]
    assert list(phosita_trace.y) == [0.46, 0.33]
    assert {t.name for t in lat_fig.data} == {"P50", "P99"}
    assert {t.name for t in tok_fig.data} == {"Input", "Output"}
    for fig in (fail_fig, lat_fig, tok_fig):
        assert fig.layout.barmode == "group"
