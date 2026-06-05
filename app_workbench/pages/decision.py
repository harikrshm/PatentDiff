"""Surface 2 — Decision (Steps 1 + 1b + the decision)."""
from __future__ import annotations

from pathlib import Path

import dash
from dash import Input, Output, callback, dash_table, dcc, html

from app_workbench.components import assumed_badge
from core.priority import priority_table
from core.workbench_data import list_trace_sets, load_merged

dash.register_page(__name__, path="/decision", name="Decision")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"
ANNOTATIONS_PATH = TRACES_DIR / "traces_annotations.jsonl"
TIERS = [{"label": t, "value": t} for t in ("High", "Med", "Low")]


def _load(active_name: str):
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    ts = sets.get(active_name) or next(iter(sets.values()))
    return load_merged(ts, ANNOTATIONS_PATH)


CELLS = [(ct, rel) for ct in ("Method", "System")
         for rel in ("Anticipation", "Implicit", "Novel")]


def _impact_control(mode: str, default: str):
    return html.Div(
        [html.Label([f"Impact — {mode} ", assumed_badge()]),
         dcc.Dropdown(id={"type": "impact", "mode": mode}, options=TIERS,
                      value=default, clearable=False, style={"width": "160px"})],
    )


def _exposure_control(ctype: str, rel: str):
    return html.Div(
        [html.Label([f"{ctype} × {rel} ", assumed_badge()],
                    style={"fontSize": "0.75rem"}),
         dcc.Dropdown(id={"type": "exposure", "cell": f"{ctype} × {rel}"},
                      options=TIERS, value="Med", clearable=False,
                      style={"width": "140px"})],
    )


layout = html.Div(
    [
        html.Div(
            [html.Label("Active trace set:"),
             dcc.Dropdown(id="decision-corpus", value="live", clearable=False,
                          options=[{"label": s.name, "value": s.name}
                                   for s in list_trace_sets(TRACES_DIR)],
                          style={"width": "240px"})],
            style={"display": "flex", "gap": "0.6rem", "alignItems": "center"},
        ),
        html.H3("Step 1 — Impact per failure mode (domain judgment)"),
        html.Div(
            [_impact_control("Absent PHOSITA", "High"),
             _impact_control("Citation Text", "Low")],
            style={"display": "flex", "gap": "1.2rem"},
        ),
        html.H3(["Step 1b — Priority = Frequency × Impact × Exposure ", assumed_badge()]),
        html.P("Set Exposure per cell (production query mix) — every value is a "
               "placeholder until the live query distribution is instrumented.",
               style={"fontSize": "0.8rem", "color": "#555"}),
        html.Div([_exposure_control(ct, rel) for ct, rel in CELLS],
                 style={"display": "flex", "gap": "0.8rem", "flexWrap": "wrap"}),
        dash_table.DataTable(
            id="priority-table",
            columns=[
                {"name": "Failure mode", "id": "failure_mode"},
                {"name": "Cell", "id": "cell"},
                {"name": "FAIL%", "id": "fail_pct"},
                {"name": "n", "id": "n"},
                {"name": "Freq", "id": "frequency_tier"},
                {"name": "Impact", "id": "impact_tier"},
                {"name": "Exposure", "id": "exposure_tier"},
                {"name": "Score", "id": "score"},
            ],
            sort_action="native",
            style_data_conditional=[
                {"if": {"filter_query": "{score} >= 12"},
                 "backgroundColor": "#ffebee"},
            ],
        ),
        html.H3("Step 2 — Assign the architecture layer (you decide)"),
        html.Div(
            [
                html.Div([
                    html.Label(f"{mode} → layer"),
                    dcc.RadioItems(
                        id={"type": "layer", "mode": mode},
                        options=[{"label": l, "value": l}
                                 for l in ("L1", "L2", "L3")],
                        inline=True,
                    ),
                ]) for mode in ("Absent PHOSITA", "Citation Text")
            ],
            style={"display": "flex", "gap": "2rem"},
        ),
        html.H3("Decision — why we fix in this order (your rationale)"),
        dcc.Textarea(
            id="decision-rationale",
            placeholder="e.g. Citation is uniform → L1 verbatim instruction, "
                        "nearly free, do first; PHOSITA Novel cluster likely L3, "
                        "gate behind the prompt fix and re-measure.",
            style={"width": "100%", "height": "120px"},
        ),
        html.Div(id="decision-saved-flag", style={"color": "#2e7d32"}),
    ]
)


@callback(
    Output("priority-table", "data"),
    Input("decision-corpus", "value"),
    Input({"type": "impact", "mode": dash.ALL}, "value"),
    Input({"type": "impact", "mode": dash.ALL}, "id"),
    Input({"type": "exposure", "cell": dash.ALL}, "value"),
    Input({"type": "exposure", "cell": dash.ALL}, "id"),
)
def _render_priority(active_name, impact_values, impact_ids, exp_values, exp_ids):
    df = _load(active_name)
    impact = {i["mode"]: v for i, v in zip(impact_ids, impact_values)}
    exposure: dict[tuple[str, str], str] = {}
    for i, v in zip(exp_ids, exp_values):
        ct, rel = i["cell"].split(" × ")
        exposure[(ct, rel)] = v
    table = priority_table(df, impact_tiers=impact, exposure_tiers=exposure)
    if table.empty:
        return []
    table["fail_pct"] = (table["fail_rate"] * 100).round(0).astype(int)
    return table[["failure_mode", "cell", "fail_pct", "n", "frequency_tier",
                  "impact_tier", "exposure_tier", "score"]].to_dict("records")
