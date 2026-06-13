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

from core.kpi_targets import get_target, set_target
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


# ── Block 2 · Eval summary — radial FAIL-rate gauge for the selected eval ─────
# Severity needle from the data palette (--data-good / --data-mid / --data-bad),
# mirrored per theme since Plotly is server-rendered. Never the chrome indigo.
_GAUGE_SEVERITY = {
    "light": {"good": "#0E8A7D", "mid": "#C98A2B", "bad": "#C0392B"},
    "dark":  {"good": "#2BB3A3", "mid": "#E0A33E", "bad": "#E06A5C"},
}


def _severity_color(fail_pct: float, ceiling: float, dark: bool) -> str:
    """Green at/under the target ceiling, amber within +20pp, red beyond."""
    pal = _GAUGE_SEVERITY["dark" if dark else "light"]
    if fail_pct <= ceiling:
        return pal["good"]
    if fail_pct <= ceiling + 20:
        return pal["mid"]
    return pal["bad"]


def _gauge_figure(fail_pct: float, target_pct, theme: str) -> go.Figure:
    """Radial gauge (go.Indicator) of a FAIL-rate. Transparent so the card shows
    through; mono number; faint track; KPI-target marker when a target is set."""
    dark = theme == "dark"
    fg = "#E6EAEF" if dark else "#1A2027"
    muted = "#9AA5B1" if dark else "#586374"
    track = "rgba(255,255,255,0.07)" if dark else "rgba(17,21,27,0.06)"
    ceiling = target_pct if target_pct is not None else 15.0
    gauge = dict(
        axis=dict(range=[0, 100], tickvals=[0, 25, 50, 75, 100], ticksuffix="%",
                  tickwidth=1, tickcolor=muted,
                  tickfont=dict(color=muted, size=10,
                                family="'IBM Plex Mono','JetBrains Mono',monospace")),
        bar=dict(color=_severity_color(fail_pct, ceiling, dark), thickness=0.72),
        bgcolor="rgba(0,0,0,0)", borderwidth=0,
        steps=[dict(range=[0, 100], color=track)],
    )
    if target_pct is not None:
        gauge["threshold"] = dict(line=dict(color=fg, width=2),
                                  thickness=0.85, value=target_pct)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(fail_pct),
        number=dict(suffix="%", font=dict(
            color=fg, size=34,
            family="'IBM Plex Mono','JetBrains Mono',monospace")),
        gauge=gauge, domain=dict(x=[0, 1], y=[0, 1])))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=18, r=18, t=12, b=4), height=208,
        font=dict(color=fg, family="'IBM Plex Mono','JetBrains Mono',monospace"))
    return fig


@callback(
    Output("fr-gauge", "figure"),
    Output("fr-caption", "children"),
    Input("fr-eval", "value"),
    Input("corpus-selector", "value"),
    Input("data-version", "data"),
    Input("theme", "data"),
)
def render_failrate_gauge(eval_kind, active_name, _v, theme):
    kind = eval_kind or "phosita"
    set_name = active_name or "live"
    rate, scored = current_pass_rate(_TRACES_DIR, set_name, kind)
    fail = (1 - rate) * 100 if scored else 0.0
    target = get_target(kind)
    tgt = (1 - target.target_pass_rate) * 100 if target else None
    caption = (f"{_EVAL_LABELS[kind]} FAIL · set {set_name} · n={scored}"
               + (f" · target {tgt:.0f}%" if tgt is not None else " · no target"))
    return _gauge_figure(fail, tgt, theme or "light"), caption


# ── §2 Where — custom themed heatmap + relationship averages ─────────────────
_DIM_SOURCE_CAPTION = "Known dimensions only · cells with n<3 flagged ⚠ (low confidence)."


def _heatmap_empty_fig(msg: str, dark: bool) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False,
                       font=dict(color="#E6EAEF" if dark else "#1A2027", size=13))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=300, margin=dict(l=8, r=8, t=8, b=8))
    return fig


@callback(
    Output("heatmap", "figure"),
    Output("heatmap-avg", "children"),
    Input("corpus-selector", "value"),
    Input("eval-toggle", "value"),
    Input("heat-row", "value"),
    Input("heat-col", "value"),
    Input("theme", "data"),
    Input("data-version", "data"),
)
def render_heatmap(active_name, eval_name, row_dim, col_dim, theme=None, _v=None):
    dark = theme == "dark"
    if row_dim == col_dim:
        return _heatmap_empty_fig("Pick two different dimensions", dark), ""
    df = load(active_name)
    if df.empty:
        return (_heatmap_empty_fig("No eval results for this set", dark),
                html.P("Switch sets or run the eval above.", className="wb-caption"))

    piv = dim_pivot(df, eval_name, row_dim, col_dim)
    if all(c == 0 for c in piv.col_n.values()):
        return (_heatmap_empty_fig("No traces with known dimensions", dark),
                html.P("Pick other dimensions or another set.", className="wb-caption"))

    fig = dim_heatmap_figure(piv, dark=dark)
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
    return fig, [avg_chips, caption]


# ── Block 4 · Eval score vs KPI target ───────────────────────────────────────
_EVAL_LABELS = {"phosita": "PHOSITA", "citation": "Citation"}


def _target_row(label: str, rate: float, scored: int, target) -> html.Div:
    # Error dashboard: show the FAIL rate. `rate` is the stored PASS rate over the
    # scored set, so FAIL = 1 - PASS. The target is stored as a PASS rate too and
    # is shown as a max-acceptable FAIL ceiling — lower is better, so a positive
    # gap (error above the ceiling) is the bad direction.
    cur = (1 - rate) * 100
    head = html.Div(className="uw-kt__head", children=[
        html.Span(label, className="uw-kt__label"),
        html.Span(f"{cur:.0f}%", className="uw-kt__cur uw-num"),
        html.Span(f"FAIL · n={scored}", className="uw-kt__n"),
    ])
    if target is None:
        return html.Div(className="uw-kt", children=[
            head,
            html.Div(className="uw-kt__bar", children=html.Div(
                className="uw-kt__fill", style={"width": f"{min(cur, 100):.0f}%"})),
            html.Div("No target set", className="uw-kt__notarget"),
        ])
    tgt = (1 - target.target_pass_rate) * 100
    gap = cur - tgt                       # +ve => error above the ceiling => bad
    gap_cls = "uw-kt__gap--ok" if gap <= 0 else "uw-kt__gap--bad"
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


# ── Block 5 · Metric trajectory — baseline → current → expected over time ────
_TRAJ_COLORS = {"phosita": "#4F46E5", "citation": "#0E8A7D"}  # indigo, teal (chrome)


def _trajectory_figure(theme: str) -> go.Figure:
    dark = theme == "dark"
    fg = "#E6EAEF" if dark else "#1A2027"
    grid = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.07)"
    fig = go.Figure()
    any_pts = False
    for kind, label in (("phosita", "PHOSITA"), ("citation", "Citation")):
        tr = trajectory(kind)
        # FAIL rate over time (error dashboard): rates are stored PASS rates, so
        # plot 100 - PASS. A falling line is improvement.
        ax, ay = [], []
        for pt in (tr.baseline, tr.current):
            if pt:
                ax.append(pt.when[:10])
                ay.append((1 - pt.rate) * 100)
        if ax:
            any_pts = True
            fig.add_scatter(
                x=ax, y=ay, mode="lines+markers", name=label,
                line=dict(color=_TRAJ_COLORS[kind], width=2), marker=dict(size=8),
                hovertemplate=label + " %{x}<br>%{y:.0f}% FAIL<extra></extra>")
        if tr.current and tr.expected:        # dashed projection to the target
            fig.add_scatter(
                x=[tr.current.when[:10], tr.expected.when],
                y=[(1 - tr.current.rate) * 100, (1 - tr.expected.rate) * 100],
                mode="lines+markers", showlegend=False,
                line=dict(color=_TRAJ_COLORS[kind], width=2, dash="dot"),
                marker=dict(size=11, symbol="star"),
                hovertemplate=label + " target %{x}<br>%{y:.0f}% FAIL<extra></extra>")
    if not any_pts:
        fig.add_annotation(text="No eval history yet — run an eval",
                           showarrow=False, font=dict(color=fg, size=13))
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
    else:
        fig.update_xaxes(showgrid=True, gridcolor=grid, type="date")
        fig.update_yaxes(showgrid=True, gridcolor=grid, range=[0, 100], ticksuffix="%")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=fg, family="'IBM Plex Mono','JetBrains Mono',monospace", size=11),
        margin=dict(l=8, r=14, t=8, b=8), height=232, showlegend=any_pts,
        legend=dict(orientation="h", y=1.15, x=0, font=dict(size=11)),
    )
    return fig


@callback(
    Output("trajectory-chart", "figure"),
    Input("data-version", "data"),
    Input("kpi-version", "data"),
    Input("theme", "data"),
)
def render_trajectory(_v, _kv, theme):
    return _trajectory_figure(theme or "light")


# ── Block 6 · Set KPI target — prefill from the current target + history ─────
@callback(
    Output("kt-rate", "value"),
    Output("kt-date", "value"),
    Output("kt-baseline", "options"),
    Output("kt-baseline", "value"),
    Input("kt-eval", "value"),
    Input("kpi-version", "data"),
    Input("data-version", "data"),
)
def prefill_target(eval_kind, _kv, _v):
    eval_kind = eval_kind or "phosita"
    target = get_target(eval_kind)
    opts = [{"label": f"{r.timestamp[:16]} · {(1 - r.pass_rate) * 100:.0f}% FAIL (n={r.scored})",
             "value": r.run_id} for r in reversed(history_for(eval_kind))]
    # Prefill the input with the target as a max FAIL % (stored as a PASS rate).
    rate = round((1 - target.target_pass_rate) * 100) if target else None
    date = target.target_date if target else None
    baseline = target.baseline_run if target else None
    return rate, date, opts, baseline


@callback(
    Output("kt-status", "children"),
    Output("kpi-version", "data"),
    Input("kt-save", "n_clicks"),
    State("kt-eval", "value"),
    State("kt-rate", "value"),
    State("kt-date", "value"),
    State("kt-baseline", "value"),
    State("kpi-version", "data"),
    prevent_initial_call=True,
)
def save_target(n_clicks, eval_kind, rate, date, baseline, version):
    if not n_clicks:                     # only a real click saves (not a mount-fire)
        return no_update, no_update
    if rate is None or not date:
        return html.Span("Enter a target max FAIL % and date.",
                         className="uw-status--error"), no_update
    try:
        # Input is the max acceptable FAIL %; persist the equivalent PASS rate so
        # the stored target stays a true PASS rate (15% FAIL -> 0.85 PASS).
        set_target(eval_kind or "phosita", round(1 - float(rate) / 100.0, 4), str(date),
                   baseline_run=baseline)
    except ValueError as exc:
        return html.Span(f"Couldn't save: {exc}", className="uw-status--error"), no_update
    return (html.Span(f"Target saved · {eval_kind} max {float(rate):.0f}% FAIL by {date}.",
                      className="uw-status--ok"),
            (version or 0) + 1)


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
        out.append(html.Span(f"{(1 - rec.pass_rate) * 100:.0f}% FAIL · n={rec.scored}{pv}",
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
        rate, _pass, scored = _pass_rate(
            load_verdict_map(p, prompt_version=PROMPT_VERSIONS.get(kind)))
        recs.append(HistoryRecord(
            timestamp=now_iso, eval_kind=kind, trace_set=ts_set.name,
            pass_rate=rate, scored=scored,
            prompt_version=PROMPT_VERSIONS.get(kind), run_id=rid))
    append_run(recs)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    set_progress([f"Done · {stamp}"])
    return stamp, (version or 0) + 1
