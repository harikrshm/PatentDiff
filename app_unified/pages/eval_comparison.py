# app_unified/pages/eval_comparison.py
"""Comparison (v1) — before/after eval delta for two trace sets."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import dash
from dash import Input, Output, callback, dash_table, dcc, html

from app_unified.components import page_header
from core.eval_delta import VERDICTS, compute_delta, load_verdict_map
from core.workbench_data import list_trace_sets

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"

_EVAL_STEM = {"phosita": "phosita_eval_full", "citation": "citation_text_eval_full"}


def eval_path(base: Path, trace_set: str, eval_kind: str) -> Path:
    """Map (trace set, eval kind) → eval JSONL path (suffix convention)."""
    stem = _EVAL_STEM[eval_kind]
    if trace_set == "live":
        return base / f"{stem}.jsonl"
    return base / f"{stem}.{trace_set}.jsonl"


def _set_options() -> list[dict]:
    try:
        names = [s.name for s in list_trace_sets(TRACES_DIR)]
    except Exception:
        names = []
    if "live" not in names:
        names = ["live", *names]
    return [{"label": n, "value": n} for n in names]


def build_comparison(base: Path, before_set: str, after_set: str,
                     eval_kind: str) -> Dict:
    before = load_verdict_map(eval_path(base, before_set, eval_kind))
    after = load_verdict_map(eval_path(base, after_set, eval_kind))
    d = compute_delta(before, after)
    return {
        "matrix": d.matrix, "buckets": d.buckets,
        "before_rate": d.before_rate, "after_rate": d.after_rate,
        "delta_pp": d.delta_pp,
        "before_scored": d.before_scored, "after_scored": d.after_scored,
    }


layout = html.Div(
    className="uw-page uw-compare",
    children=[
        page_header("Comparison", "How did eval scores change after a prompt change?"),
        html.Div(
            className="uw-compare__controls",
            children=[
                html.Div([html.Label("Before (baseline)", className="uw-label"),
                          dcc.Dropdown(id="cmp-before", options=_set_options(),
                                       value="baseline", className="uw-dropdown")]),
                html.Div([html.Label("After (experiment)", className="uw-label"),
                          dcc.Dropdown(id="cmp-after", options=_set_options(),
                                       value="live", className="uw-dropdown")]),
                html.Div([html.Label("Eval", className="uw-label"),
                          dcc.RadioItems(id="cmp-eval",
                                         options=[{"label": "PHOSITA", "value": "phosita"},
                                                  {"label": "Citation", "value": "citation"}],
                                         value="phosita",
                                         className="uw-segmented__items")]),
            ],
        ),
        html.Div(id="cmp-kpis", className="uw-compare__kpis"),
        html.H2("Verdict transitions", className="uw-compare__h2"),
        html.Div(id="cmp-matrix"),
        html.H2("Flipped traces", className="uw-compare__h2"),
        html.Div(id="cmp-flipped"),
    ],
)


def _kpi(label: str, value: str) -> html.Div:
    return html.Div(className="uw-kpi", children=[
        html.Span(label, className="uw-kpi__label"),
        html.Span(value, className="uw-kpi__value uw-num"),
    ])


@callback(
    Output("cmp-kpis", "children"),
    Output("cmp-matrix", "children"),
    Output("cmp-flipped", "children"),
    Input("cmp-before", "value"),
    Input("cmp-after", "value"),
    Input("cmp-eval", "value"),
)
def _render(before_set, after_set, eval_kind):
    if not (before_set and after_set and eval_kind):
        return html.P("Pick two trace sets."), None, None
    r = build_comparison(TRACES_DIR, before_set, after_set, eval_kind)
    kpis = [
        _kpi("Before PASS", f"{100*r['before_rate']:.1f}%  (n={r['before_scored']})"),
        _kpi("After PASS", f"{100*r['after_rate']:.1f}%  (n={r['after_scored']})"),
        _kpi("Delta", f"{r['delta_pp']:+.1f} pp"),
    ]
    matrix_rows = [{"before": b, **{a: r["matrix"].get((b, a), 0) for a in VERDICTS}}
                   for b in VERDICTS]
    matrix = dash_table.DataTable(
        data=matrix_rows,
        columns=[{"name": "before \\ after", "id": "before"}]
                + [{"name": a, "id": a} for a in VERDICTS],
        style_cell={"textAlign": "right"},
        style_cell_conditional=[{"if": {"column_id": "before"}, "textAlign": "left"}],
    )
    fixed = r["buckets"].get(("FAIL", "PASS"), [])
    regressed = r["buckets"].get(("PASS", "FAIL"), [])
    flipped = html.Div([
        html.P(f"Fixed (FAIL→PASS): {len(fixed)}"),
        html.Code(" ".join(x[:8] for x in fixed[:20]) or "—"),
        html.P(f"Regressed (PASS→FAIL): {len(regressed)}"),
        html.Code(" ".join(x[:8] for x in regressed[:20]) or "—"),
    ])
    return kpis, matrix, flipped
