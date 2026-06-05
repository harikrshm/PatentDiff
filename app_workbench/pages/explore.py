"""Surface 1 — Explore / Eval Workbench."""
from __future__ import annotations

from pathlib import Path

import dash
import dash_draggable
import dash_pivottable
from dash import Input, Output, callback, dcc, html

from app_workbench.components import kpi_tile, evidence_note
from core.diagnostics import dispersion_pp, relationship_gradient, evidence_note as build_note
from core.eval_runner import eval_for_set
from core.workbench_data import list_trace_sets, load_merged
from core.workbench_state import load_state, save_state

dash.register_page(__name__, path="/", name="Explore")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"
ANNOTATIONS_PATH = TRACES_DIR / "traces_annotations.jsonl"
STATE_DIR = TRACES_DIR / "workbench_state"


def _trace_set_options():
    return [{"label": s.name, "value": s.name} for s in list_trace_sets(TRACES_DIR)]


def _load(active_name: str):
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    ts = sets.get(active_name) or next(iter(sets.values()))
    return load_merged(ts, ANNOTATIONS_PATH)


layout = html.Div([
    html.Div(
        [
            html.Label("Active trace set:"),
            dcc.Dropdown(id="corpus-selector", options=_trace_set_options(),
                         value="live", clearable=False, style={"width": "240px"}),
            html.Button("Run eval", id="run-eval-btn", n_clicks=0),
            html.Span(id="run-eval-status", style={"fontSize": "0.8rem", "color": "#555"}),
        ],
        style={"display": "flex", "gap": "0.6rem", "alignItems": "center"},
    ),
    dash_draggable.ResponsiveGridLayout(
        id="explore-grid",
        children=[
            html.Div([html.H3("How bad is it?"),
                      html.Div(id="kpi-row",
                               style={"display": "flex", "gap": "0.8rem",
                                      "flexWrap": "wrap"})],
                     id="w-kpis"),
            html.Div([html.H3("Where does it fail? (drag dims onto Rows/Cols/Filters)"),
                      dcc.RadioItems(id="pivot-eval",
                                     options=[{"label": "PHOSITA", "value": "phosita"},
                                              {"label": "Citation", "value": "citation"},
                                              {"label": "Either", "value": "either"}],
                                     value="phosita", inline=True),
                      html.Div(id="pivot-container")],
                     id="w-pivot"),
            html.Div([html.H3("Shape read (hypothesis only — you assign the layer)"),
                      html.Div(id="shape-read")],
                     id="w-shape"),
        ],
    ),
    html.Div(id="layout-save-status", style={"display": "none"}),
])


@callback(Output("kpi-row", "children"), Input("corpus-selector", "value"))
def _render_kpis(active_name: str):
    df = _load(active_name)
    ph = df[df["phosita_verdict"].isin(["PASS", "FAIL"])]
    ct = df[df["citation_verdict"].isin(["PASS", "FAIL"])]
    both = df[df["phosita_verdict"].isin(["PASS", "FAIL"])
              & df["citation_verdict"].isin(["PASS", "FAIL"])]

    ph_rate = (ph["phosita_verdict"] == "FAIL").mean() if not ph.empty else 0.0
    ct_rate = (ct["citation_verdict"] == "FAIL").mean() if not ct.empty else 0.0
    either = (((both["phosita_verdict"] == "FAIL") | (both["citation_verdict"] == "FAIL")).mean()
              if not both.empty else 0.0)
    clean = (((both["phosita_verdict"] == "PASS") & (both["citation_verdict"] == "PASS")).mean()
             if not both.empty else 0.0)

    return [
        kpi_tile("PHOSITA Reasoning FAIL", f"{ph_rate:.0%}", f"n={len(ph)}"),
        kpi_tile("Citation Text FAIL", f"{ct_rate:.0%}", f"n={len(ct)}"),
        kpi_tile("Either fails", f"{either:.0%}", f"n={len(both)}"),
        kpi_tile("Fully clean", f"{clean:.0%}", f"n={len(both)}"),
    ]


def _fail_frame(df, eval_name: str):
    """Long frame with one 'fail' label column per scored trace, for the pivot."""
    work = df.copy()
    if eval_name == "phosita":
        scored = work[work["phosita_verdict"].isin(["PASS", "FAIL"])].copy()
        scored["result"] = scored["phosita_verdict"]
    elif eval_name == "citation":
        scored = work[work["citation_verdict"].isin(["PASS", "FAIL"])].copy()
        scored["result"] = scored["citation_verdict"]
    else:
        mask = (work["phosita_verdict"].isin(["PASS", "FAIL"])
                | work["citation_verdict"].isin(["PASS", "FAIL"]))
        scored = work[mask].copy()
        scored["result"] = (
            ((scored["phosita_verdict"] == "FAIL")
             | (scored["citation_verdict"] == "FAIL"))
            .map({True: "FAIL", False: "PASS"})
        )
    return scored[["claim_type", "claim_length", "relationship", "result"]]


@callback(
    Output("pivot-container", "children"),
    Input("corpus-selector", "value"),
    Input("pivot-eval", "value"),
)
def _render_pivot(active_name: str, eval_name: str):
    df = _load(active_name)
    scored = _fail_frame(df, eval_name)
    scored = scored[(scored["claim_type"] != "Unknown")
                    & (scored["relationship"] != "Unknown")]
    data = [scored.columns.tolist()] + scored.values.tolist()
    return dash_pivottable.PivotTable(
        id="pivot-table",
        data=data,
        rows=["claim_type", "claim_length"],
        cols=["relationship"],
        vals=["result"],
        aggregatorName="Count as Fraction of Rows",
        rendererName="Heatmap",
    )


@callback(
    Output("shape-read", "children"),
    Input("corpus-selector", "value"),
    Input("pivot-eval", "value"),
)
def _render_shape_read(active_name: str, eval_name: str):
    if eval_name == "either":
        return html.Div("Select PHOSITA or Citation to read the failure shape.",
                        style={"color": "#888"})
    df = _load(active_name)
    disp = dispersion_pp(df, eval_name)
    grad = relationship_gradient(df, eval_name)
    return html.Div([
        evidence_note(build_note(disp, grad)),
        html.Div(
            f"Dispersion {disp:.0f}pp · gradient "
            + " → ".join(f"{r} {grad.rates[r]:.0%}" for r in grad.rates),
            style={"fontSize": "0.8rem", "color": "#555"},
        ),
    ])


@callback(
    Output("explore-grid", "layouts"),
    Input("corpus-selector", "value"),  # fires on initial load
)
def _restore_layout(_):
    saved = load_state(STATE_DIR, "layout")
    return saved or dash.no_update


@callback(
    Output("layout-save-status", "children"),
    Input("explore-grid", "layouts"),
    prevent_initial_call=True,
)
def _save_layout(layouts):
    if layouts:
        save_state(STATE_DIR, "layout", layouts)
    return ""


@callback(
    Output("run-eval-status", "children"),
    Input("run-eval-btn", "n_clicks"),
    dash.State("corpus-selector", "value"),
    background=True,
    running=[(Output("run-eval-btn", "disabled"), True, False)],
    prevent_initial_call=True,
)
def _run_eval(_n, active_name):
    summary = eval_for_set(active_name, TRACES_DIR)
    if summary == "No such trace set.":
        return summary
    return f"Done. {summary}"
