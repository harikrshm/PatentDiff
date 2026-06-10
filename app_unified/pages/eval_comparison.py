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
    if eval_kind not in _EVAL_STEM:
        raise ValueError(f"unknown eval_kind {eval_kind!r}; expected one of {list(_EVAL_STEM)}")
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


_SET_OPTIONS = _set_options()  # scan trace sets once at import

layout = html.Div(
    className="uw-page uw-page--instrument uw-compare",
    children=[
        page_header("Comparison", "How did eval scores change after a prompt change?"),
        html.Div(
            className="uw-compare__controls",
            children=[
                html.Div([html.Label("Before (baseline)", className="uw-label"),
                          dcc.Dropdown(id="cmp-before", options=_SET_OPTIONS,
                                       value="baseline",
                                       className="uw-dropdown wb-dropdown")]),
                html.Div([html.Label("After (experiment)", className="uw-label"),
                          dcc.Dropdown(id="cmp-after", options=_SET_OPTIONS,
                                       value="live",
                                       className="uw-dropdown wb-dropdown")]),
                html.Div([html.Label("Eval", className="uw-label"),
                          dcc.RadioItems(id="cmp-eval",
                                         options=[{"label": "PHOSITA", "value": "phosita"},
                                                  {"label": "Citation", "value": "citation"}],
                                         value="phosita",
                                         className="uw-segmented__items wb-segmented__items")]),
            ],
        ),
        html.Div(id="cmp-kpis", className="uw-compare__kpis wb-kpi-row"),
        html.H2("Verdict transitions", className="uw-compare__h2"),
        html.Div(id="cmp-matrix", className="uw-compare__matrix"),
        html.H2("Flipped traces", className="uw-compare__h2"),
        html.Div(id="cmp-flipped"),
    ],
)


# Matrix theming — instrument readout: mono numerals, hairline list-view, the two
# meaningful flips tinted (regressed = FAIL fill alarm; fixed = quiet teal text).
# var() resolves per theme; white-on-red holds in both, success text is readable
# on both card backgrounds.
_MATRIX_STYLE = dict(
    style_as_list_view=True,
    style_table={"overflowX": "auto", "maxWidth": "44rem"},
    style_header={
        "backgroundColor": "transparent",
        "color": "var(--color-text-secondary)",
        "fontFamily": "var(--font-family-mono)",
        "fontSize": "11px",
        "textTransform": "uppercase",
        "letterSpacing": "0.06em",
        "fontWeight": "600",
        "border": "none",
        "borderBottom": "1px solid var(--color-border-primary)",
        "padding": "8px 12px",
        "textAlign": "right",
    },
    style_cell={
        "fontFamily": "var(--font-family-mono)",
        "fontVariantNumeric": "tabular-nums",
        "fontSize": "13px",
        "color": "var(--color-text-primary)",
        "backgroundColor": "transparent",
        "border": "none",
        "borderBottom": "1px solid var(--color-border-secondary)",
        "padding": "8px 12px",
        "textAlign": "right",
    },
    style_cell_conditional=[{
        "if": {"column_id": "before"},
        "textAlign": "left",
        "color": "var(--color-text-secondary)",
    }],
    style_data_conditional=[
        {"if": {"filter_query": '{before} = "PASS"', "column_id": "FAIL"},
         "backgroundColor": "var(--data-fail-100)", "color": "#FFFFFF",
         "fontWeight": "600"},
        {"if": {"filter_query": '{before} = "FAIL"', "column_id": "PASS"},
         "color": "var(--color-status-success)", "fontWeight": "600"},
    ],
)


def _kpi(label: str, value: str, sub: str = "", valence: str = "") -> html.Div:
    style = {}
    if valence == "up":
        style["borderLeftColor"] = "var(--color-status-success)"
    elif valence == "down":
        style["borderLeftColor"] = "var(--color-status-error)"
    children = [
        html.Span(label, className="wb-kpi__label"),
        html.Span(value, className="wb-kpi__value uw-num"),
    ]
    if sub:
        children.append(html.Span(sub, className="wb-kpi__sub uw-num"))
    return html.Div(className="wb-kpi uw-compare__kpi", style=style,
                    children=children)


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
        return html.P("Pick two trace sets.", className="uw-compare__empty"), None, None
    r = build_comparison(TRACES_DIR, before_set, after_set, eval_kind)
    delta = r["delta_pp"]
    valence = "up" if delta > 0 else "down" if delta < 0 else ""
    kpis = [
        _kpi("Before PASS", f"{100*r['before_rate']:.1f}%", f"n={r['before_scored']}"),
        _kpi("After PASS", f"{100*r['after_rate']:.1f}%", f"n={r['after_scored']}"),
        _kpi("Delta", f"{delta:+.1f} pp", "PASS rate", valence=valence),
    ]
    matrix_rows = [{"before": b, **{a: r["matrix"].get((b, a), 0) for a in VERDICTS}}
                   for b in VERDICTS]
    matrix = dash_table.DataTable(
        data=matrix_rows,
        columns=[{"name": "before \\ after", "id": "before"}]
                + [{"name": a, "id": a} for a in VERDICTS],
        **_MATRIX_STYLE,
    )
    fixed = r["buckets"].get(("FAIL", "PASS"), [])
    regressed = r["buckets"].get(("PASS", "FAIL"), [])
    flipped = html.Div(className="uw-compare__flips", children=[
        _flip_list("Fixed", "FAIL → PASS", "ok", fixed),
        _flip_list("Regressed", "PASS → FAIL", "bad", regressed),
    ])
    return kpis, matrix, flipped


def _flip_list(title: str, arrow: str, valence: str, ids: list) -> html.Div:
    return html.Div(className=f"uw-compare__flip uw-compare__flip--{valence}", children=[
        html.Div(className="uw-compare__flip-head", children=[
            html.Span(title, className="uw-compare__flip-title"),
            html.Span(arrow, className="uw-compare__flip-arrow uw-num"),
            html.Span(str(len(ids)), className="uw-compare__flip-count uw-num"),
        ]),
        html.Div(
            className="uw-compare__flip-ids uw-num",
            children=" ".join(x[:8] for x in ids[:20]) or "—",
        ),
    ])
