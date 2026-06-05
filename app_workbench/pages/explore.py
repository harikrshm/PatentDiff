"""Surface 1 — Explore / Eval Workbench."""
from __future__ import annotations

from pathlib import Path

import dash
from dash import Input, Output, callback, dcc, html

from app_workbench.components import kpi_tile
from core.workbench_data import list_trace_sets, load_merged

dash.register_page(__name__, path="/", name="Explore")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"
ANNOTATIONS_PATH = TRACES_DIR / "traces_annotations.jsonl"


def _trace_set_options():
    return [{"label": s.name, "value": s.name} for s in list_trace_sets(TRACES_DIR)]


def _load(active_name: str):
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    ts = sets.get(active_name) or next(iter(sets.values()))
    return load_merged(ts, ANNOTATIONS_PATH)


layout = html.Div(
    [
        html.Div(
            [
                html.Label("Active trace set:"),
                dcc.Dropdown(
                    id="corpus-selector",
                    options=_trace_set_options(),
                    value="live",
                    clearable=False,
                    style={"width": "240px"},
                ),
            ],
            style={"display": "flex", "gap": "0.6rem", "alignItems": "center"},
        ),
        html.H3("How bad is it?"),
        html.Div(id="kpi-row", style={"display": "flex", "gap": "0.8rem", "flexWrap": "wrap"}),
    ]
)


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
