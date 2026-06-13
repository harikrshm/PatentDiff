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


# Stub — Task 6 replaces this with the full history-table layout.
layout = html.Div(className="uw-page uw-compare", children=[
    page_header("Comparison", "Experiment tracker — coming soon."),
])
