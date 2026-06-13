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


def test_build_figures_uses_data_palette_and_themes():
    # Series use the neutral categorical DATA palette (slate-blue/amber), not the
    # chrome indigo, and recolor between light and dark.
    pairs = [_pair("baseline", 0.46, 0.55), _pair("live", 0.33, 0.45)]
    light_fail = eval_comparison.build_figures(pairs, dark=False)[0]
    dark_fail = eval_comparison.build_figures(pairs, dark=True)[0]
    lp = next(t for t in light_fail.data if t.name == "PHOSITA")
    dp = next(t for t in dark_fail.data if t.name == "PHOSITA")
    lc = next(t for t in light_fail.data if t.name == "Citation")
    assert lp.marker.color == "#3B6EA5"          # --data-cat-1 (light)
    assert lc.marker.color == "#C98A2B"          # --data-cat-2 (light)
    assert dp.marker.color == "#6FA8DC"          # --data-cat-1 (dark)
    assert lp.marker.color != dp.marker.color    # themes differ
    assert "4F46E5" not in lp.marker.color.upper()   # never the chrome indigo


def test_build_figures_newest_experiment_emphasis():
    # opacity ramps oldest->newest; the newest group is full, older recede.
    pairs = [_pair("e1", 0.5, 0.5), _pair("e2", 0.4, 0.5),
             _pair("e3", 0.3, 0.5), _pair("e4", 0.2, 0.5)]
    fail = eval_comparison.build_figures(pairs)[0]
    phosita = next(t for t in fail.data if t.name == "PHOSITA")
    op = tuple(phosita.marker.opacity)
    assert op[-1] == 1.0 and op[0] == 0.7        # newest full, oldest receded
    assert list(op) == sorted(op)                # monotonic oldest->newest


def test_build_table_rows_newest_first_with_run_to_run_delta(monkeypatch):
    # oldest->newest fail: 0.50 -> 0.40 (phosita). Table is newest-first; the
    # newest row's delta is vs the previous experiment (0.40 - 0.50 = -10pp).
    pairs = [_pair("baseline", 0.50, 0.60), _pair("live", 0.40, 0.60)]
    monkeypatch.setattr(eval_comparison, "kpi_target_fail",
                        lambda kind: 0.15 if kind == "phosita" else None)
    rows = eval_comparison.build_table_rows(pairs)
    assert [r["experiment"] for r in rows] == ["live", "baseline"]  # newest first
    newest = rows[0]
    assert "0.40" in newest["phosita"]
    assert "-10" in newest["phosita"] and "pp" in newest["phosita"]
    assert newest["phosita_dir"] == "down"            # fail fell -> improvement
    assert newest["citation_dir"] == "flat"           # 0.60 -> 0.60
    assert rows[1]["phosita_dir"] == ""               # oldest row: no previous
    assert newest["splits"] == "1 · all"
    assert newest["repetitions"] == 1
    assert "15%" in newest["target"]                  # phosita target shown


def test_build_table_rows_marks_only_newest_row():
    # The newest (top) row carries the hidden emphasis marker; older rows don't.
    pairs = [_pair("e1", 0.5, 0.5), _pair("e2", 0.4, 0.5), _pair("e3", 0.3, 0.5)]
    rows = eval_comparison.build_table_rows(pairs)
    assert rows[0]["is_newest"] == "1"
    assert all(r["is_newest"] == "" for r in rows[1:])
    # the marker is hidden — not a displayed column
    assert "is_newest" not in {c["id"] for c in eval_comparison._TABLE_COLUMNS}


def test_layout_has_chart_and_table_containers():
    # layout is a module-level Dash component tree; smoke-check it builds.
    assert eval_comparison.layout is not None


def test_empty_state_when_no_experiments(monkeypatch):
    monkeypatch.setattr(eval_comparison, "experiments_with_metrics", lambda: [])
    # the theme callback renders one calm empty card, no charts
    children = eval_comparison._render_charts("light")
    assert len(children) == 1
    s = str(children)
    assert "uw-compare__empty" in s
    assert "Graph" not in s          # no chart figures emitted
    # and the layout omits the history table entirely
    lay = str(eval_comparison._build_layout())
    assert "uw-compare__empty" in lay
    assert "DataTable" not in lay and "Experiment history" not in lay
