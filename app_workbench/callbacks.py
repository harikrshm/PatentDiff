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


# ── §3 Why — machine HYPOTHESIS (shared eval toggle) + your-call (persisted) ──
@callback(
    Output("shape-read", "children"),
    Input("corpus-selector", "value"),
    Input("eval-toggle", "value"),
    Input("data-version", "data"),
)
def render_shape_read(active_name: str, eval_name: str, _v=None):
    if eval_name == "either":
        return html.Div(
            "Pick PHOSITA or Citation above to read a single failure shape — "
            "the gradient and dispersion are per-eval.",
            className="wb-shape-hint wb-caption",
        )
    df = load(active_name)
    if df.empty:
        return empty_state(
            "No eval results for this trace set",
            "No shape to read yet — switch sets or run the eval above.",
        )

    disp = dispersion_pp(df, eval_name)
    grad = relationship_gradient(df, eval_name)
    note = evidence_note(disp, grad)
    chain = " → ".join(f"{r} {grad.rates[r]:.0%}" for r in REL_ORDER if r in grad.rates)
    meta = f"dispersion {disp:.0f}pp · gradient {chain}" if chain else f"dispersion {disp:.0f}pp"
    return machine_note(note, meta=meta)


@callback(Output("why-conclusion", "value"), Input("corpus-selector", "value"))
def restore_why_conclusion(active_name: str):
    """Load this trace set's saved conclusion when the corpus changes."""
    return get_annotation("why", active_name or "")


@callback(
    Output("why-saved", "children"),
    Input("why-conclusion", "value"),
    State("corpus-selector", "value"),
    prevent_initial_call=True,
)
def save_why_conclusion(value: str, active_name: str):
    set_annotation("why", active_name or "", value or "")
    return "Saved ✓" if (value or "").strip() else ""


# ── §4 Priority — restore tiers per set, live F×I×E table, inversion rollup ───
@callback(
    Output({"type": "impact", "mode": ALL}, "value"),
    Output({"type": "exposure", "cell": ALL}, "value"),
    Input("corpus-selector", "value"),
)
def restore_priority_tiers(active_name: str):
    """Load this set's saved Impact/Exposure tiers (defaults where unset)."""
    saved = get_priority_inputs(active_name or "")
    impact_ids = ctx.outputs_list[0]
    exposure_ids = ctx.outputs_list[1]
    impact = [saved["impact"].get(o["id"]["mode"], "Med") for o in impact_ids]
    exposure = [saved["exposure"].get(o["id"]["cell"], "Med") for o in exposure_ids]
    return impact, exposure


def _impact_map(values, ids):
    return {i["mode"]: v for i, v in zip(ids, values)}


def _exposure_map(values, ids):
    out = {}
    for i, v in zip(ids, values):
        ct, rel = i["cell"].split(" × ")
        out[(ct, rel)] = v
    return out


@callback(
    Output("priority-table", "data"),
    Output("priority-rollup", "children"),
    Input("corpus-selector", "value"),
    Input({"type": "impact", "mode": ALL}, "value"),
    Input({"type": "exposure", "cell": ALL}, "value"),
    Input("data-version", "data"),
    State({"type": "impact", "mode": ALL}, "id"),
    State({"type": "exposure", "cell": ALL}, "id"),
)
def render_priority(active_name, impact_vals, exp_vals, _v, impact_ids, exp_ids):
    impact = _impact_map(impact_vals, impact_ids)
    exposure = _exposure_map(exp_vals, exp_ids)
    # Persist this set's tiers (idempotent on restore).
    update_priority_inputs(active_name or "",
                           {"impact": impact,
                            "exposure": {f"{c} × {r}": v for (c, r), v in exposure.items()}})

    df = load(active_name)
    table = priority_table(df, impact_tiers=impact, exposure_tiers=exposure)
    if table.empty:
        return [], empty_state(
            "No scored cells to rank",
            "This set has no scored traces with known dimensions yet. Run the eval "
            "or pick another set, then set Impact and Exposure here.",
        )

    table = table.copy()
    table["fail_pct"] = (table["fail_rate"] * 100).round(0).astype(int).astype(str) + "%"
    data = table[["failure_mode", "cell", "fail_pct", "n", "frequency_tier",
                  "impact_tier", "exposure_tier", "score"]].to_dict("records")
    return data, _inversion_rollup(df, impact)


def _inversion_rollup(df: pd.DataFrame, impact: dict) -> html.Div:
    """Step 1 — Frequency vs Frequency×Impact, surfacing the rank inversion."""
    from core.priority import MODE_VERDICT
    rows = []
    for mode, col in MODE_VERDICT.items():
        scored = df[df[col].isin(["PASS", "FAIL"])]
        scored = scored[(scored["claim_type"] != "Unknown")
                        & (scored["relationship"] != "Unknown")]
        rate = (scored[col] == "FAIL").mean() if not scored.empty else 0.0
        i_tier = TIER.get(impact.get(mode, "Med"), 2)
        rows.append({"mode": mode, "rate": float(rate),
                     "freq_tier": frequency_tier(rate),
                     "fi": frequency_tier(rate) * i_tier})
    by_freq = sorted(rows, key=lambda r: r["rate"], reverse=True)
    by_fi = sorted(rows, key=lambda r: r["fi"], reverse=True)
    inverted = by_freq[0]["mode"] != by_fi[0]["mode"]

    def _lens(title, leader, detail):
        return html.Div(className="wb-rollup__lens", children=[
            html.Span(title, className="wb-kicker"),
            html.Div(leader, className="wb-rollup__leader"),
            html.Div(detail, className="wb-caption"),
        ])

    note = (f"Inversion: frequency leads with {by_freq[0]['mode']}, but "
            f"Frequency×Impact leads with {by_fi[0]['mode']} — impact reorders the priority."
            if inverted else
            "Frequency and Frequency×Impact agree on the lead failure mode.")
    return html.Div(className="wb-rollup__inner", children=[
        html.Span("Step 1 — Frequency vs Frequency × Impact", className="wb-kicker"),
        html.Div(className="wb-rollup__lenses", children=[
            _lens("By frequency", by_freq[0]["mode"],
                  f"{by_freq[0]['rate']:.0%} overall FAIL"),
            _lens("By frequency × impact", by_fi[0]["mode"],
                  f"score {by_fi[0]['fi']} (freq {by_fi[0]['freq_tier']} × impact)"),
        ]),
        html.Div(note, className="wb-rollup__note"),
    ])


# ── §5 Decision — hypothesis echoes, layer call, ordered recommendation ──────
@callback(
    Output({"type": "layer-hypo", "mode": ALL}, "children"),
    Input("corpus-selector", "value"),
    Input("data-version", "data"),
)
def render_layer_hypotheses(active_name: str, _v=None):
    """Echo each failure mode's §3 HYPOTHESIS beside its layer control."""
    df = load(active_name)
    out = []
    for o in ctx.outputs_list:
        mode = o["id"]["mode"]
        if df.empty:
            out.append(html.Div("No data.", className="wb-caption"))
            continue
        eval_name = MODE_EVAL[mode]
        disp = dispersion_pp(df, eval_name)
        grad = relationship_gradient(df, eval_name)
        meta = f"dispersion {disp:.0f}pp"
        out.append(machine_note(evidence_note(disp, grad), meta=meta))
    return out


@callback(
    Output({"type": "layer", "mode": ALL}, "value"),
    Input("corpus-selector", "value"),
)
def restore_layers(active_name: str):
    saved = get_priority_inputs(active_name or "")["layers"]
    return [saved.get(o["id"]["mode"]) for o in ctx.outputs_list]


def _mode_top_scores(df: pd.DataFrame, active_name: str) -> dict:
    """Top (max) F×I×E score per failure mode, using the set's saved tiers."""
    inp = get_priority_inputs(active_name or "")
    impact = inp["impact"]
    exposure = {}
    for cell, v in inp["exposure"].items():
        ct, rel = cell.split(" × ")
        exposure[(ct, rel)] = v
    table = priority_table(df, impact_tiers=impact, exposure_tiers=exposure)
    if table.empty:
        return {}
    out = {}
    for mode, grp in table.groupby("failure_mode"):
        top = grp.sort_values("score", ascending=False).iloc[0]
        out[mode] = {"score": int(top["score"]), "cell": top["cell"],
                     "fail_pct": f"{top['fail_rate']:.0%}"}
    return out


@callback(
    Output("decision-recommendation", "children"),
    Input("corpus-selector", "value"),
    Input({"type": "layer", "mode": ALL}, "value"),
    Input("data-version", "data"),
    State({"type": "layer", "mode": ALL}, "id"),
)
def render_recommendation(active_name, layer_vals, _v, layer_ids):
    layers = {i["mode"]: v for i, v in zip(layer_ids, layer_vals)}
    update_priority_inputs(active_name or "", {"layers": layers})

    df = load(active_name)
    tops = _mode_top_scores(df, active_name)
    if not tops:
        return html.Div("Set tiers in Priority to assemble the recommendation.",
                        className="wb-caption")

    # Cheapest-layer-first, then by urgency (score desc). Unassigned sink last.
    def _key(mode):
        rank = LAYER_RANK.get(layers.get(mode) or "", 99)
        return (rank, -tops.get(mode, {}).get("score", 0))

    ordered = sorted(DECISION_MODES, key=_key)
    items = []
    for idx, mode in enumerate(ordered, 1):
        layer = layers.get(mode)
        top = tops.get(mode, {})
        layer_chip = (html.Span(LAYER_LABEL.get(layer, layer), className="wb-reco__layer")
                      if layer else
                      html.Span("layer not set", className="wb-reco__layer wb-reco__layer--unset"))
        items.append(html.Li(className="wb-reco__item", children=[
            html.Span(f"{idx}", className="wb-reco__rank wb-num"),
            html.Div(className="wb-reco__body", children=[
                html.Div([html.Span(mode, className="wb-reco__mode"), layer_chip]),
                html.Div(
                    (f"worst cell {top.get('cell','—')} · {top.get('fail_pct','—')} FAIL "
                     f"· score {top.get('score','—')}"),
                    className="wb-caption"),
            ]),
        ]))
    return [html.Span("Fix in this order — cheapest layer first", className="wb-kicker"),
            html.Ol(items, className="wb-reco__list")]


@callback(Output("decision-rationale", "value"), Input("corpus-selector", "value"))
def restore_rationale(active_name: str):
    return get_priority_inputs(active_name or "")["rationale"]


@callback(
    Output("decision-saved", "children"),
    Input("decision-rationale", "value"),
    State("corpus-selector", "value"),
    prevent_initial_call=True,
)
def save_rationale(value: str, active_name: str):
    update_priority_inputs(active_name or "", {"rationale": value or ""})
    return "Saved ✓" if (value or "").strip() else "Rationale required to finalize"


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
