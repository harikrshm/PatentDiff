"""Section callbacks for the single-page console.

Imported once by app.py (after the app is created) so `@callback` registers
against the global registry. One block per funnel section.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import parse_qs

import pandas as pd
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from app_workbench.components import (empty_state, human_field, kpi_tile,
                                       machine_note, valence_var)
from app_workbench.constants import (DECISION_MODES, LAYER_LABEL, LAYER_RANK,
                                     MODE_EVAL)
from app_workbench.data import load, resolve_set_strict, trace_set_options
from core.eval_delta import _pass_rate, load_verdict_map
from core.eval_history import PROMPT_VERSIONS, HistoryRecord, append_run
from core.eval_runner import run_evals
from app_workbench.heatmap import REL_ORDER, fail_pivot, heatmap_figure
from app_workbench.state import (get_annotation, get_priority_inputs,
                                 set_annotation, update_priority_inputs)
from core.diagnostics import dispersion_pp, evidence_note, relationship_gradient
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION
from core.priority import TIER, frequency_tier, priority_table

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def _rate(series: pd.Series, fail_value: str = "FAIL") -> float:
    return (series == fail_value).mean() if not series.empty else 0.0


# ── §1 How bad — KPI tiles + attribution ─────────────────────────────────────
@callback(
    Output("kpi-row", "children"),
    Input("corpus-selector", "value"),
    Input("data-version", "data"),
)
def render_kpis(active_name: str, _v=None):
    df = load(active_name)
    if df.empty:
        return empty_state(
            "No eval results for this trace set",
            "This set has no PHOSITA or citation verdicts yet. Switch sets, "
            "or run the eval from the control bar above.",
        )

    ph = df[df["phosita_verdict"].isin(["PASS", "FAIL"])]
    ct = df[df["citation_verdict"].isin(["PASS", "FAIL"])]
    both = df[df["phosita_verdict"].isin(["PASS", "FAIL"])
              & df["citation_verdict"].isin(["PASS", "FAIL"])]

    ph_rate = _rate(ph["phosita_verdict"])
    ct_rate = _rate(ct["citation_verdict"])
    either = (((both["phosita_verdict"] == "FAIL")
               | (both["citation_verdict"] == "FAIL")).mean()
              if not both.empty else 0.0)
    clean = (((both["phosita_verdict"] == "PASS")
              & (both["citation_verdict"] == "PASS")).mean()
             if not both.empty else 0.0)

    tiles = html.Div(
        className="wb-kpi-row",
        children=[
            kpi_tile("PHOSITA reasoning FAIL", f"{ph_rate:.0%}", f"n={len(ph)}", rate=ph_rate),
            kpi_tile("Citation text FAIL", f"{ct_rate:.0%}", f"n={len(ct)}", rate=ct_rate),
            kpi_tile("Either fails", f"{either:.0%}", f"n={len(both)}", rate=either),
            # Neutral rule: "clean" is the one good metric — keep the red/amber
            # valence strictly on the failure tiles so red always = more failure.
            kpi_tile("Fully clean", f"{clean:.0%}", f"n={len(both)}"),
        ],
    )

    n_human = int((df["dim_source"] == "human").sum())
    attribution = html.Div(
        className="wb-attribution",
        children=[
            "Trace set ",
            html.Span(active_name, className="wb-num"),
            " · PHOSITA ",
            html.Span(PHOSITA_PROMPT_VERSION, className="wb-num"),
            " · ",
            html.Span(str(len(df)), className="wb-num"),
            " traces with ≥1 eval result · ",
            html.Span(str(n_human), className="wb-num"),
            " human-verified dimensions",
        ],
    )
    return [tiles, attribution]


# ── §2 Where — custom themed heatmap + relationship averages ─────────────────
_DIM_SOURCE_CAPTION = (
    "Known dimensions only (Unknown excluded). Human-verified dimensions override "
    "inferred ones; inferred accuracy ≈ claim_type 100% · claim_length 89% · "
    "relationship 61%. Cells with n<3 flagged ⚠ (low confidence)."
)


@callback(
    Output("heatmap-container", "children"),
    Input("corpus-selector", "value"),
    Input("eval-toggle", "value"),
    Input("theme", "data"),
    Input("data-version", "data"),
)
def render_heatmap(active_name: str, eval_name: str, theme=None, _v=None):
    df = load(active_name)
    if df.empty:
        return empty_state(
            "No eval results for this trace set",
            "Nothing to chart yet — switch sets or run the eval above.",
        )

    piv = fail_pivot(df, eval_name)
    if all(c == 0 for c in piv.col_n.values()):
        return empty_state(
            "No traces with known dimensions",
            "Every scored trace here is Unknown on claim type or relationship, "
            "so the grid can't be built. Tag dimensions or pick another set.",
        )

    dark = theme == "dark"
    graph = dcc.Graph(id="heatmap", figure=heatmap_figure(piv, dark=dark),
                      config=_GRAPH_CONFIG)

    avg_chips = html.Div(
        className="wb-avg-strip",
        children=[html.Span("Avg by relationship", className="wb-kicker")] + [
            html.Div(
                className="wb-avg-chip",
                children=[
                    html.Span(className="wb-avg-chip__dot",
                              style={"background": valence_var(piv.col_avg[rel])}),
                    html.Span(rel, className="wb-avg-chip__label"),
                    html.Span(f"{piv.col_avg[rel]:.0%}", className="wb-avg-chip__val wb-num"),
                    html.Span(f"n={piv.col_n[rel]}", className="wb-avg-chip__n wb-num"),
                ],
            )
            for rel in REL_ORDER
        ],
    )

    caption = html.P(_DIM_SOURCE_CAPTION, className="wb-caption")
    return [graph, avg_chips, caption]


# ── T9 · Deep-link reader — apply ?set= / ?eval= on load (idempotent) ────────
_VALID_EVALS = {"phosita", "citation", "either"}


@callback(
    Output("corpus-selector", "value"),
    Output("eval-toggle", "value"),
    Input("url", "search"),
)
def apply_deep_link(search: str):
    """Restore a shared link's trace set + eval view. Guarded so it never loops:
    invalid/missing params return no_update, leaving the control untouched."""
    params = parse_qs((search or "").lstrip("?"))
    want_set = (params.get("set") or [None])[0]
    want_eval = (params.get("eval") or [None])[0]
    names = {o["value"] for o in trace_set_options()}
    out_set = want_set if want_set in names else no_update
    out_eval = want_eval if want_eval in _VALID_EVALS else no_update
    return out_set, out_eval


# ── T10 · Run eval — background job, live status, refresh on completion ───────
@callback(
    Output("last-run", "children"),
    Output("data-version", "data"),
    Input("run-eval-btn", "n_clicks"),
    State("corpus-selector", "value"),
    State("data-version", "data"),
    background=True,
    running=[
        (Output("run-eval-btn", "disabled"), True, False),
        (Output("run-eval-btn", "children"), "Running…", "Run eval"),
    ],
    progress=[Output("run-eval-status", "children")],
    prevent_initial_call=True,
)
def run_eval(set_progress, _n_clicks, active_name, version):
    """Run citation+phosita evals on the active set as a subprocess job.

    Streams short status via `progress`; on completion stamps last-run and bumps
    data-version, which the section callbacks watch to refresh their displays.
    The eval scripts are idempotent-cached, so re-running is safe.
    """
    if not _n_clicks:
        # Multi-page navigation re-inserts run-eval-btn with n_clicks=0, which
        # fires this callback even under prevent_initial_call (that only suppresses
        # the app's first load, not later dynamic re-insertions). Only a real
        # click (n_clicks >= 1) should ever run the evals.
        return no_update, no_update
    set_progress(["Queued…"])
    ts_set = resolve_set_strict(active_name)  # strict: never run on a fallback set
    if ts_set is None:
        set_progress(["⚠ No such trace set."])
        return no_update, no_update
    try:
        run_evals(ts_set, set_status=lambda m: set_progress([m]))
    except Exception as exc:  # surface failure without crashing the UI
        set_progress([f"⚠ Eval failed: {exc}"])
        return no_update, no_update

    # Record this real run's PASS-rates to the dated history (ruler unchanged).
    rid = uuid.uuid4().hex[:8]
    now_iso = datetime.now().isoformat(timespec="seconds")
    recs = []
    for kind, p in (("phosita", ts_set.phosita_path),
                    ("citation", ts_set.citation_path)):
        rate, _pass, scored = _pass_rate(load_verdict_map(p))
        recs.append(HistoryRecord(
            timestamp=now_iso, eval_kind=kind, trace_set=ts_set.name,
            pass_rate=rate, scored=scored,
            prompt_version=PROMPT_VERSIONS.get(kind), run_id=rid))
    append_run(recs)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    set_progress([f"Done · {stamp}"])
    return stamp, (version or 0) + 1
