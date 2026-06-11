"""Section callbacks for the single-page console.

Imported once by app.py (after the app is created) so `@callback` registers
against the global registry. One block per funnel section.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import parse_qs

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from core.failure_modes import UNTAGGED_LABEL, failure_mode_breakdown
from core.kpi_targets import get_target
from core.kpi_view import current_pass_rate, series, trajectory

_TRACES_DIR = Path(__file__).resolve().parents[1] / "traces"

from app_workbench.components import (empty_state, human_field, kpi_tile,
                                       machine_note, valence_var)
from app_workbench.constants import (DECISION_MODES, LAYER_LABEL, LAYER_RANK,
                                     MODE_EVAL)
from app_workbench.data import load, resolve_set_strict, trace_set_options
from core.eval_delta import _pass_rate, load_verdict_map
from core.eval_history import (PROMPT_VERSIONS, HistoryRecord, append_run,
                               history_for)
from core.eval_runner import run_evals
from app_workbench.heatmap import DIM_LABELS, dim_heatmap_figure, dim_pivot
from app_workbench.state import (get_annotation, get_priority_inputs,
                                 set_annotation, update_priority_inputs)
from core.diagnostics import dispersion_pp, evidence_note, relationship_gradient
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION
from core.priority import TIER, frequency_tier, priority_table

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def _rate(series: pd.Series, fail_value: str = "FAIL") -> float:
    return (series == fail_value).mean() if not series.empty else 0.0


# ── Block 2 · Eval summary — failure-mode share of FAILs (whole set) ─────────
_FM_RED = "rgba(192, 57, 43, 0.55)"        # FAIL valence (counts of failures)
_FM_GRAY = "rgba(127, 135, 148, 0.45)"     # untagged — neutral, not on the data axis


def _fm_figure(rows: list, theme: str) -> go.Figure:
    """Horizontal bar chart of failure-mode share of FAILs. Transparent bg so the
    card surface shows through in both themes; mono font; FAIL-tinted bars."""
    dark = theme == "dark"
    fg = "#E6EAEF" if dark else "#1A2027"
    grid = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.07)"
    fig = go.Figure()
    if not rows:
        fig.add_annotation(text="No FAILs to break down for this set",
                           showarrow=False, font=dict(color=fg, size=13))
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
    else:
        labels = [r[0] for r in rows][::-1]   # largest on top
        vals = [r[1] for r in rows][::-1]
        colors = [_FM_GRAY if l == UNTAGGED_LABEL else _FM_RED for l in labels]
        fig.add_bar(x=vals, y=labels, orientation="h", marker_color=colors,
                    text=vals, textposition="outside",
                    hovertemplate="%{y}: %{x}<extra></extra>")
        hi = max(vals)
        fig.update_xaxes(showgrid=True, gridcolor=grid, zeroline=False,
                         range=[0, hi * 1.15])   # headroom for outside labels
        fig.update_yaxes(showgrid=False, automargin=True)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=fg, family="'IBM Plex Mono','JetBrains Mono',monospace",
                  size=12),
        margin=dict(l=8, r=36, t=8, b=8), height=232, showlegend=False, bargap=0.4,
    )
    return fig


@callback(
    Output("fm-chart", "figure"),
    Output("fm-caption", "children"),
    Input("corpus-selector", "value"),
    Input("data-version", "data"),
    Input("theme", "data"),
)
def render_fm_chart(active_name: str, _v, theme):
    set_name = active_name or "live"
    rows = failure_mode_breakdown(_TRACES_DIR, set_name)
    total = sum(c for _, c in rows)
    caption = (f"share of FAILs · set {set_name} · {total} FAILs" if rows
               else f"set {set_name} — no FAILs")
    return _fm_figure(rows, theme or "light"), caption


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
    Input("heat-row", "value"),
    Input("heat-col", "value"),
    Input("theme", "data"),
    Input("data-version", "data"),
)
def render_heatmap(active_name, eval_name, row_dim, col_dim, theme=None, _v=None):
    if row_dim == col_dim:
        return empty_state("Pick two different dimensions",
                           "Rows and columns must differ to build a heatmap.")
    df = load(active_name)
    if df.empty:
        return empty_state(
            "No eval results for this trace set",
            "Nothing to chart yet — switch sets or run the eval above.",
        )

    piv = dim_pivot(df, eval_name, row_dim, col_dim)
    if all(c == 0 for c in piv.col_n.values()):
        return empty_state(
            "No traces with known dimensions",
            "Every scored trace here is Unknown on the chosen dimensions. "
            "Pick other dimensions or another set.",
        )

    dark = theme == "dark"
    graph = dcc.Graph(id="heatmap", figure=dim_heatmap_figure(piv, dark=dark),
                      config=_GRAPH_CONFIG)

    col_label = DIM_LABELS.get(col_dim, col_dim).lower()
    avg_chips = html.Div(
        className="wb-avg-strip",
        children=[html.Span(f"Avg by {col_label}", className="wb-kicker")] + [
            html.Div(
                className="wb-avg-chip",
                children=[
                    html.Span(className="wb-avg-chip__dot",
                              style={"background": valence_var(piv.col_avg[cv])}),
                    html.Span(cv, className="wb-avg-chip__label"),
                    html.Span(f"{piv.col_avg[cv]:.0%}", className="wb-avg-chip__val wb-num"),
                    html.Span(f"n={piv.col_n[cv]}", className="wb-avg-chip__n wb-num"),
                ],
            )
            for cv in piv.cols
        ],
    )

    caption = html.P(_DIM_SOURCE_CAPTION, className="wb-caption")
    return [graph, avg_chips, caption]


# ── Block 4 · Eval score vs KPI target ───────────────────────────────────────
_EVAL_LABELS = {"phosita": "PHOSITA", "citation": "Citation"}


def _target_row(label: str, rate: float, scored: int, target) -> html.Div:
    cur = rate * 100
    head = html.Div(className="uw-kt__head", children=[
        html.Span(label, className="uw-kt__label"),
        html.Span(f"{cur:.0f}%", className="uw-kt__cur uw-num"),
        html.Span(f"PASS · n={scored}", className="uw-kt__n"),
    ])
    if target is None:
        return html.Div(className="uw-kt", children=[
            head,
            html.Div(className="uw-kt__bar", children=html.Div(
                className="uw-kt__fill", style={"width": f"{min(cur, 100):.0f}%"})),
            html.Div("No target set", className="uw-kt__notarget"),
        ])
    tgt = target.target_pass_rate * 100
    gap = cur - tgt
    gap_cls = "uw-kt__gap--ok" if gap >= 0 else "uw-kt__gap--bad"
    return html.Div(className="uw-kt", children=[
        head,
        html.Div(className="uw-kt__bar", children=[
            html.Div(className="uw-kt__fill", style={"width": f"{min(cur, 100):.0f}%"}),
            html.Div(className="uw-kt__marker", title=f"target {tgt:.0f}%",
                     style={"left": f"{min(tgt, 100):.0f}%"}),
        ]),
        html.Div(className="uw-kt__sub", children=[
            html.Span(f"target {tgt:.0f}%", className="uw-kt__target uw-num"),
            html.Span(f"{gap:+.0f} pp", className=f"uw-kt__gap {gap_cls} uw-num"),
        ]),
    ])


@callback(
    Output("kpi-target-readout", "children"),
    Input("corpus-selector", "value"),
    Input("data-version", "data"),
    Input("kpi-version", "data"),
)
def render_kpi_vs_target(active_name, _v, _kv):
    set_name = active_name or "live"
    return [
        _target_row(_EVAL_LABELS[kind], *current_pass_rate(_TRACES_DIR, set_name, kind),
                    get_target(kind))
        for kind in ("phosita", "citation")
    ]


# ── T9 · Deep-link reader — apply ?set= / ?eval= on load (idempotent) ────────
_VALID_EVALS = {"phosita", "citation", "either"}


@callback(
    Output("corpus-selector", "value"),
    Output("eval-toggle", "value"),
    Input("url", "search"),
)
def apply_deep_link(search: str):
    """Restore a shared link's trace set + eval view, else fall back to the
    defaults. url.search is the only input and never changes when the controls
    do, so this can't loop. Returning concrete values (not no_update) on load is
    deliberate: corpus-selector.value is the input every block reads, so it must
    be *set* on load to trigger them (an unchanged input never fires its
    dependents)."""
    params = parse_qs((search or "").lstrip("?"))
    want_set = (params.get("set") or [None])[0]
    want_eval = (params.get("eval") or [None])[0]
    names = {o["value"] for o in trace_set_options()}
    out_set = want_set if want_set in names else "live"
    out_eval = want_eval if want_eval in _VALID_EVALS else "phosita"
    return out_set, out_eval


# ── Block 1 · Trace properties — per-eval run metadata from history ──────────
@callback(
    Output("trace-meta", "children"),
    Input("corpus-selector", "value"),
    Input("data-version", "data"),
)
def render_trace_meta(active_name: str, _v=None):
    """Latest recorded PASS-rate, n, and prompt version per eval kind for the
    active set (from core.eval_history). No eval runs here — display only."""
    set_name = active_name or "live"
    rows = []
    for kind in ("phosita", "citation"):
        h = history_for(kind, trace_set=set_name)
        if h:
            rows.append((kind, h[-1]))
    if not rows:
        return html.Span("No eval runs recorded for this set yet.",
                         className="wb-caption")
    out = []
    for kind, rec in rows:
        pv = f" · {rec.prompt_version}" if rec.prompt_version else ""
        out.append(html.Span(kind.capitalize(), className="uw-dash__meta-k"))
        out.append(html.Span(f"{rec.pass_rate * 100:.0f}% PASS · n={rec.scored}{pv}",
                             className="uw-num"))
    return out


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
