# app_unified/pages/eval_comparison.py
"""Comparison — experiment tracker. The last 4 experiments as three grouped-bar
charts (eval FAIL-rate, latency, tokens) plus a history table with run-to-run
deltas and a KPI-target column. Reads core/experiments.py (manifest + on-read
aggregation)."""
from __future__ import annotations

from typing import List, Tuple

import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from app_unified.components import page_header
from core.experiments import (Experiment, ExperimentMetrics, kpi_target_fail,
                              last_n, metrics_for)

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

Pair = Tuple[Experiment, ExperimentMetrics]

# Plotly renders server-side and can't read CSS vars, so the chart palette is
# mirrored here from workbench.css. These are the NEUTRAL categorical DATA series
# (slate-blue / amber) — never the chrome indigo, never the good/bad valence
# colors. Keyed by theme; tuple is (series-A, series-B).
_DATA_CAT = {"light": ("#3B6EA5", "#C98A2B"), "dark": ("#6FA8DC", "#E0B25C")}
# Axis/legend text (~ --color-text-secondary) and a faint gridline, per theme.
_AXIS = {"light": "#586374", "dark": "#9AA5B1"}
_GRID = {"light": "rgba(17,21,27,0.08)", "dark": "rgba(255,255,255,0.10)"}
_FONT_MONO = "IBM Plex Mono, JetBrains Mono, ui-monospace, monospace"


def _opacity_ramp(n: int) -> list:
    """Newest-experiment emphasis: older groups recede (0.70), newest is full (1.0)."""
    if n <= 1:
        return [1.0] * n
    return [round(0.70 + 0.30 * i / (n - 1), 3) for i in range(n)]


def experiments_with_metrics() -> List[Pair]:
    """Last 4 experiments (oldest->newest) paired with their computed metrics."""
    return [(e, metrics_for(e)) for e in last_n(4)]


def _grouped_bars(x, a_name, a_vals, b_name, b_vals, *, y_title, dark) -> go.Figure:
    key = "dark" if dark else "light"
    cat1, cat2 = _DATA_CAT[key]
    axis, grid = _AXIS[key], _GRID[key]
    opacity = _opacity_ramp(len(x))   # x is oldest->newest; ramp lands full on newest
    fig = go.Figure()
    fig.add_bar(name=a_name, x=x, y=a_vals, marker=dict(color=cat1, opacity=opacity))
    fig.add_bar(name=b_name, x=x, y=b_vals, marker=dict(color=cat2, opacity=opacity))
    fig.update_layout(
        barmode="group", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=48, r=12, t=8, b=32), height=232,
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11, color=axis)),
        font=dict(family=_FONT_MONO, size=11, color=axis))
    fig.update_yaxes(title_text=y_title, gridcolor=grid, zerolinecolor=grid, color=axis)
    fig.update_xaxes(showgrid=False, color=axis)
    return fig


def build_figures(pairs: List[Pair], dark: bool = False):
    """Three grouped-bar figures (eval FAIL-rate, latency, tokens), themed for
    light/dark. x is oldest->newest so the opacity ramp lands full on the newest."""
    x = [e.name for e, _ in pairs]
    fail_fig = _grouped_bars(
        x, "PHOSITA", [m.phosita_fail for _, m in pairs],
        "Citation", [m.citation_fail for _, m in pairs], y_title="FAIL rate", dark=dark)
    lat_fig = _grouped_bars(
        x, "P50", [m.lat_p50 for _, m in pairs],
        "P99", [m.lat_p99 for _, m in pairs], y_title="latency (ms)", dark=dark)
    tok_fig = _grouped_bars(
        x, "Input", [m.tok_in for _, m in pairs],
        "Output", [m.tok_out for _, m in pairs], y_title="tokens", dark=dark)
    return fail_fig, lat_fig, tok_fig


def _chart_block(kicker: str, title: str, figure) -> html.Section:
    return html.Section(className="uw-compare__chart", children=[
        html.Div(className="uw-compare__chart-head", children=[
            html.Span(kicker, className="wb-kicker"),
            html.H2(title, className="uw-compare__chart-title"),
        ]),
        dcc.Graph(figure=figure,
                  config={"displayModeBar": False, "responsive": True},
                  style={"height": "232px"}),
    ])


_TABLE_COLUMNS = [
    {"name": "Experiment", "id": "experiment"},
    {"name": "Splits", "id": "splits"},
    {"name": "Reps", "id": "repetitions"},
    {"name": "PHOSITA FAIL", "id": "phosita"},
    {"name": "Citation FAIL", "id": "citation"},
    {"name": "Gap to KPI", "id": "target"},
]


def _fail_cell(cur: float, prev) -> tuple[str, str]:
    """Display string ('0.40  ▼ -10pp') + direction ('down'|'up'|'flat'|'')."""
    if prev is None:
        return f"{cur:.2f}", ""
    delta_pp = (cur - prev) * 100.0
    if abs(delta_pp) < 0.05:
        return f"{cur:.2f}  – 0pp", "flat"
    arrow = "▼" if delta_pp < 0 else "▲"          # FAIL fell = improvement = down
    direction = "down" if delta_pp < 0 else "up"
    return f"{cur:.2f}  {arrow} {delta_pp:+.0f}pp", direction


def _gap_seg(label: str, fail: float, prev_fail, target) -> tuple[str, str]:
    """One eval's distance-to-target as pp + a run-to-run arrow. Gap = current
    FAIL − target FAIL (positive = above the ceiling). ▼/'down' = gap closing
    toward the KPI (improvement); ▲/'up' = widening. No target -> ('L —', '')."""
    if target is None:
        return f"{label} —", ""
    gap = (fail - target) * 100.0
    seg = f"{label} {gap:+.0f}pp"
    if prev_fail is None:
        return seg, ""
    delta = gap - (prev_fail - target) * 100.0
    if abs(delta) < 0.05:
        return f"{seg} –", "flat"
    return (f"{seg} ▼", "down") if delta < 0 else (f"{seg} ▲", "up")


def _target_cell(m: ExperimentMetrics, prev, pt, ct) -> tuple[str, str]:
    """KPI-gap column: per-eval distance-to-target (pp) with run-to-run arrows.
    Cell coloring follows PHOSITA (the primary target)."""
    p_seg, p_dir = _gap_seg("P", m.phosita_fail, prev.phosita_fail if prev else None, pt)
    c_seg, _ = _gap_seg("C", m.citation_fail, prev.citation_fail if prev else None, ct)
    return f"{p_seg} · {c_seg}", p_dir


def build_table_rows(pairs: List[Pair]) -> list[dict]:
    """Rows newest-first; each fail cell carries a run-to-run delta vs the
    chronologically previous experiment. `*_dir` columns drive cell coloring."""
    pt = kpi_target_fail("phosita")
    ct = kpi_target_fail("citation")
    rows = []
    for i, (e, m) in enumerate(pairs):
        prev = pairs[i - 1][1] if i > 0 else None
        ph_txt, ph_dir = _fail_cell(m.phosita_fail, prev.phosita_fail if prev else None)
        ct_txt, ct_dir = _fail_cell(m.citation_fail, prev.citation_fail if prev else None)
        tgt_txt, tgt_dir = _target_cell(m, prev, pt, ct)
        rows.append({
            "experiment": e.name,
            "splits": f"{len(e.splits)} · {', '.join(e.splits)}",
            "repetitions": e.repetitions,
            "phosita": ph_txt, "phosita_dir": ph_dir,
            "citation": ct_txt, "citation_dir": ct_dir,
            "target": tgt_txt, "target_dir": tgt_dir,
            "is_newest": "",
        })
    rows.reverse()   # newest first
    if rows:
        rows[0]["is_newest"] = "1"   # hidden marker -> newest-row emphasis (styling)
    return rows


_TABLE_STYLE = dict(
    style_as_list_view=True,
    style_table={"overflowX": "auto"},
    style_header={
        "backgroundColor": "transparent",
        "color": "var(--color-text-secondary)",
        "fontFamily": "var(--font-family-mono)",
        "fontSize": "11px", "textTransform": "uppercase",
        "letterSpacing": "0.06em", "fontWeight": "600",
        "border": "none", "borderBottom": "1px solid var(--color-border-primary)",
        "padding": "8px 12px", "textAlign": "right",
    },
    style_cell={
        "fontFamily": "var(--font-family-mono)", "fontVariantNumeric": "tabular-nums",
        "fontSize": "13px", "color": "var(--color-text-primary)",
        "backgroundColor": "transparent", "border": "none",
        "borderBottom": "1px solid var(--color-border-secondary)",
        "padding": "8px 12px", "textAlign": "right",
    },
    style_cell_conditional=[{"if": {"column_id": "experiment"},
                             "textAlign": "left",
                             "color": "var(--color-text-primary)"}],
    style_data_conditional=[
        # Newest experiment brought forward: faint indigo wash + a left selection
        # rail (indigo as selection chrome here, never a data color).
        {"if": {"filter_query": '{is_newest} = "1"'},
         "backgroundColor": "var(--color-accent-subtle)"},
        {"if": {"filter_query": '{is_newest} = "1"', "column_id": "experiment"},
         "borderLeft": "3px solid var(--color-accent-primary)"},
        {"if": {"filter_query": '{phosita_dir} = "down"', "column_id": "phosita"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{phosita_dir} = "up"', "column_id": "phosita"},
         "color": "var(--color-status-error)"},
        {"if": {"filter_query": '{citation_dir} = "down"', "column_id": "citation"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{citation_dir} = "up"', "column_id": "citation"},
         "color": "var(--color-status-error)"},
        {"if": {"filter_query": '{target_dir} = "down"', "column_id": "target"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{target_dir} = "up"', "column_id": "target"},
         "color": "var(--color-status-error)"},
    ],
)


def _chart_blocks(pairs: List[Pair], dark: bool) -> list:
    fail_fig, lat_fig, tok_fig = build_figures(pairs, dark=dark)
    return [
        _chart_block("01 · EVAL", "FAIL-rate", fail_fig),
        _chart_block("02 · LATENCY", "P50 · P99", lat_fig),
        _chart_block("03 · TOKENS", "Input · Output", tok_fig),
    ]


def _empty_state() -> html.Div:
    """Calm full-width readout when the manifest is empty/missing — beats three
    blank chart boxes and a header-only table."""
    return html.Div(
        className="uw-compare__empty", style={"gridColumn": "1 / -1"},
        children=[
            html.P("No experiments recorded yet.", className="uw-compare__empty-title"),
            html.P("Run scripts/seed_experiments.py (or an experiment) to populate "
                   "this view.", className="uw-compare__empty-hint"),
        ],
    )


def _charts_or_empty(pairs: List[Pair], dark: bool) -> list:
    return _chart_blocks(pairs, dark) if pairs else [_empty_state()]


@callback(Output("cmp-charts", "children"), Input("theme", "data"))
def _render_charts(theme):
    """Rebuild the three figures on theme toggle. Plotly is server-rendered and
    can't follow the CSS [data-theme] switch the way the table does, so the charts
    are recolored here in lock-step with the shell's theme store."""
    return _charts_or_empty(experiments_with_metrics(), dark=(theme == "dark"))


def _build_layout() -> html.Div:
    pairs = experiments_with_metrics()
    # Charts pre-rendered light so first paint isn't empty; the callback recolors
    # to the active theme on load and on every toggle.
    children = [
        page_header("Comparison",
                    "How have eval scores moved across the last experiments?"),
        html.Div(id="cmp-charts", className="uw-compare__charts",
                 children=_charts_or_empty(pairs, dark=False)),
    ]
    if pairs:   # no header-only table on an empty manifest
        children += [
            html.H2("Experiment history", className="uw-compare__h2"),
            dash_table.DataTable(
                data=build_table_rows(pairs),
                columns=_TABLE_COLUMNS,
                **_TABLE_STYLE,
            ),
        ]
    return html.Div(className="uw-page uw-page--instrument uw-compare",
                    children=children)


layout = _build_layout()
