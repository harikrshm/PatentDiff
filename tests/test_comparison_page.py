# tests/test_comparison_page.py
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
    pairs = [_pair("baseline", 0.46, 0.55, p50=1100, p99=2100, ti=110, to=60),
             _pair("live", 0.33, 0.45, p50=900, p99=1800, ti=90, to=40)]
    fail_fig, lat_fig, tok_fig = eval_comparison.build_figures(pairs)

    # eval chart: PHOSITA / Citation series with correct y-values
    assert {t.name for t in fail_fig.data} == {"PHOSITA", "Citation"}
    phosita = next(t for t in fail_fig.data if t.name == "PHOSITA")
    citation = next(t for t in fail_fig.data if t.name == "Citation")
    assert list(phosita.x) == ["baseline", "live"]
    assert list(phosita.y) == [0.46, 0.33]
    assert list(citation.y) == [0.55, 0.45]

    # latency chart: P50 / P99
    assert {t.name for t in lat_fig.data} == {"P50", "P99"}
    assert list(next(t for t in lat_fig.data if t.name == "P50").y) == [1100, 900]
    assert list(next(t for t in lat_fig.data if t.name == "P99").y) == [2100, 1800]

    # tokens chart: Input / Output
    assert {t.name for t in tok_fig.data} == {"Input", "Output"}
    assert list(next(t for t in tok_fig.data if t.name == "Input").y) == [110, 90]
    assert list(next(t for t in tok_fig.data if t.name == "Output").y) == [60, 40]

    for fig in (fail_fig, lat_fig, tok_fig):
        assert fig.layout.barmode == "group"
