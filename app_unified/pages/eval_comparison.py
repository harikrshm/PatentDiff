# app_unified/pages/eval_comparison.py
"""Comparison — experiment tracker. The last 4 experiments as three grouped-bar
charts (eval FAIL-rate, latency, tokens) plus a history table with run-to-run
deltas and a KPI-target column. Reads core/experiments.py (manifest + on-read
aggregation)."""
from __future__ import annotations

from typing import List, Tuple

import dash
import plotly.graph_objects as go
from dash import dash_table, dcc, html

from app_unified.components import page_header
from core.experiments import (Experiment, ExperimentMetrics, kpi_target_fail,
                              last_n, metrics_for)

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

Pair = Tuple[Experiment, ExperimentMetrics]

# Two-series palette, readable in both themes (indigo / teal).
_COLOR_A = "#4F46E5"
_COLOR_B = "#2EA091"

# Plotly renders server-side and cannot read CSS vars; use a literal mono stack.
_FONT_MONO = "IBM Plex Mono, JetBrains Mono, ui-monospace, monospace"

_FIG_LAYOUT = dict(
    barmode="group",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=48, r=12, t=8, b=32),
    height=232,
    legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)),
    font=dict(family=_FONT_MONO, size=11),
)


def experiments_with_metrics() -> List[Pair]:
    """Last 4 experiments (oldest->newest) paired with their computed metrics."""
    return [(e, metrics_for(e)) for e in last_n(4)]


def _grouped_bars(x, a_name, a_vals, b_name, b_vals, *, y_title) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(name=a_name, x=x, y=a_vals, marker_color=_COLOR_A)
    fig.add_bar(name=b_name, x=x, y=b_vals, marker_color=_COLOR_B)
    fig.update_layout(**_FIG_LAYOUT)
    fig.update_yaxes(title_text=y_title, gridcolor="rgba(128,128,128,0.18)")
    fig.update_xaxes(showgrid=False)
    return fig


def build_figures(pairs: List[Pair]):
    """Three grouped-bar figures: eval FAIL-rate, latency, tokens."""
    x = [e.name for e, _ in pairs]
    fail_fig = _grouped_bars(
        x, "PHOSITA", [m.phosita_fail for _, m in pairs],
        "Citation", [m.citation_fail for _, m in pairs], y_title="FAIL rate")
    lat_fig = _grouped_bars(
        x, "P50", [m.lat_p50 for _, m in pairs],
        "P99", [m.lat_p99 for _, m in pairs], y_title="latency (ms)")
    tok_fig = _grouped_bars(
        x, "Input", [m.tok_in for _, m in pairs],
        "Output", [m.tok_out for _, m in pairs], y_title="tokens")
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
    {"name": "KPI Target", "id": "target"},
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


def _target_cell() -> str:
    pt = kpi_target_fail("phosita")
    ct = kpi_target_fail("citation")
    parts = []
    parts.append(f"P {pt * 100:.0f}%" if pt is not None else "P —")
    parts.append(f"C {ct * 100:.0f}%" if ct is not None else "C —")
    return " · ".join(parts)


def build_table_rows(pairs: List[Pair]) -> list[dict]:
    """Rows newest-first; each fail cell carries a run-to-run delta vs the
    chronologically previous experiment. `*_dir` columns drive cell coloring."""
    target = _target_cell()
    rows = []
    for i, (e, m) in enumerate(pairs):
        prev = pairs[i - 1][1] if i > 0 else None
        ph_txt, ph_dir = _fail_cell(m.phosita_fail, prev.phosita_fail if prev else None)
        ct_txt, ct_dir = _fail_cell(m.citation_fail, prev.citation_fail if prev else None)
        rows.append({
            "experiment": e.name,
            "splits": f"{len(e.splits)} · {', '.join(e.splits)}",
            "repetitions": e.repetitions,
            "phosita": ph_txt, "phosita_dir": ph_dir,
            "citation": ct_txt, "citation_dir": ct_dir,
            "target": target,
        })
    rows.reverse()   # newest first
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
        {"if": {"filter_query": '{phosita_dir} = "down"', "column_id": "phosita"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{phosita_dir} = "up"', "column_id": "phosita"},
         "color": "var(--color-status-error)"},
        {"if": {"filter_query": '{citation_dir} = "down"', "column_id": "citation"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{citation_dir} = "up"', "column_id": "citation"},
         "color": "var(--color-status-error)"},
    ],
)


def _build_layout() -> html.Div:
    pairs = experiments_with_metrics()
    fail_fig, lat_fig, tok_fig = build_figures(pairs)
    return html.Div(
        className="uw-page uw-page--instrument uw-compare",
        children=[
            page_header("Comparison",
                        "How have eval scores moved across the last experiments?"),
            html.Div(className="uw-compare__charts", children=[
                _chart_block("01 · EVAL", "FAIL-rate", fail_fig),
                _chart_block("02 · LATENCY", "P50 · P99", lat_fig),
                _chart_block("03 · TOKENS", "Input · Output", tok_fig),
            ]),
            html.H2("Experiment history", className="uw-compare__h2"),
            dash_table.DataTable(
                data=build_table_rows(pairs),
                columns=_TABLE_COLUMNS,
                **_TABLE_STYLE,
            ),
        ],
    )


layout = _build_layout()
