"""Traces — annotation tool. Port of app_annotation.py.

Trace browser (left) + read-only trace view (centre) + failure-mode coder
(right). Persists to traces/traces_annotations.jsonl via core.annotation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import dash
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from app_unified.components import page_header
from core.annotation import (AnnotationRecord, detect_phase, load_annotations,
                             load_taxonomy, save_annotations)
from core.trace_loader import load_traces

dash.register_page(__name__, path="/eval/traces", name="Traces")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_FILE = REPO_ROOT / "traces" / "traces.jsonl"
ANNOTATIONS_FILE = REPO_ROOT / "traces" / "traces_annotations.jsonl"
TAXONOMY_FILE = REPO_ROOT / "failure_taxonomy.json"


# ── Pure logic (unit-tested) ──────────────────────────────────────────────────
def validate_annotation(verdict: str, failure_modes: List[str], comment: str) -> List[str]:
    """Mirror app_annotation.save_annotation validation. Returns error strings."""
    errors: List[str] = []
    if not comment:
        errors.append("Comment is required")
    if verdict == "PASS" and failure_modes:
        errors.append("PASS verdict cannot have failure modes selected")
    if verdict == "FAIL" and not failure_modes:
        errors.append("FAIL verdict requires at least one failure mode")
    return errors


def build_record(run_id: str, phase: int, verdict: str, failure_modes_ids: List[str],
                 comment: str, reviewed: bool,
                 dimensions: Optional[Dict[str, str]]) -> AnnotationRecord:
    """Build an AnnotationRecord exactly as app_annotation.save_annotation does."""
    modes = failure_modes_ids if verdict == "FAIL" else []
    if phase == 1:
        return AnnotationRecord(
            run_id=run_id, phase=1, open_coded_failure_modes=modes,
            verdict=verdict, comment=comment, reviewed=reviewed, dimensions=dimensions,
        )
    return AnnotationRecord(
        run_id=run_id, phase=3, failure_modes=modes,
        verdict=verdict, comment=comment, reviewed=reviewed, dimensions=dimensions,
    )


def persist_record(path: Path, annotations: Dict[str, AnnotationRecord]) -> None:
    save_annotations(path, annotations)


# ── Data access ───────────────────────────────────────────────────────────────
def _load_traces() -> dict:
    return {t.run_id: t for t in load_traces(TRACES_FILE)}


# v1 scope: phase-1 free-text failure-mode entry from the original Streamlit tool is
# intentionally dropped — this port uses the phase-3 taxonomy dropdown only. Deleting or
# renaming failure_taxonomy.json makes detect_phase return 1 and empties the dropdown,
# which would make FAIL annotation impossible, so the taxonomy file must exist.
def _taxonomy_options() -> List[dict]:
    tax = load_taxonomy(TAXONOMY_FILE)
    return [{"label": c["name"], "value": c["id"]}
            for c in tax.get("failure_categories", [])]


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div(
    className="uw-page uw-page--memo uw-traces",
    children=[
        page_header("Traces — Error Analysis", "Browse traces and code failure modes."),
        dcc.Store(id="traces-phase", data=detect_phase(TAXONOMY_FILE)),
        dcc.Store(id="selected-trace"),         # run_id of the selected trace
        dcc.Store(id="ann-version", data=0),     # bumped on save → refresh nav
        html.Div(
            className="uw-traces__grid",
            children=[
                html.Aside(
                    className="uw-traces__nav",
                    children=[
                        html.Span("Contents", className="uw-kicker"),
                        html.Div(id="traces-coverage", className="uw-traces__coverage"),
                        dcc.RadioItems(
                            id="traces-filter",
                            options=[{"label": "All", "value": "all"},
                                     {"label": "To review", "value": "todo"},
                                     {"label": "Reviewed", "value": "done"}],
                            value="all",
                            className="uw-segmented__items wb-segmented__items uw-traces__filter"),
                        dcc.Loading(
                            html.Div(id="traces-list", className="uw-traces__list"),
                            type="dot"),
                    ],
                ),
                dcc.Loading(
                    html.Section(
                        id="traces-detail", className="uw-traces__detail",
                        children=html.P("Select a trace to read.",
                                        className="uw-traces__empty"),
                    ),
                    type="dot"),
                html.Section(
                    className="uw-traces__form uw-field--human",
                    children=[
                        html.H2("Annotation", className="uw-traces__h2"),
                        html.Label("Verdict", className="uw-label"),
                        dcc.RadioItems(id="ann-verdict",
                                       options=[{"label": "PASS", "value": "PASS"},
                                                {"label": "FAIL", "value": "FAIL"}],
                                       value="PASS",
                                       className="uw-segmented__items wb-segmented__items"),
                        html.Label("Failure modes", className="uw-label"),
                        dcc.Dropdown(id="ann-modes", options=_taxonomy_options(),
                                     multi=True, placeholder="Tag failure modes…",
                                     className="uw-dropdown wb-dropdown"),
                        html.Label("Comment", className="uw-label"),
                        dcc.Textarea(id="ann-comment",
                                     className="uw-input--area uw-traces__well",
                                     style={"height": "150px"}),
                        dcc.Checklist(id="ann-reviewed",
                                      options=[{"label": "Reviewed", "value": "yes"}],
                                      value=[], className="uw-traces__reviewed"),
                        html.Button("Save", id="ann-save", n_clicks=0,
                                    className="uw-btn uw-btn--primary"),
                        html.Div(id="ann-status", className="uw-status",
                                 role="status", **{"aria-live": "polite"}),
                    ],
                ),
            ],
        ),
    ],
)


# ── Callbacks ─────────────────────────────────────────────────────────────────
def _meta_chip(label: str, value: str) -> html.Span:
    return html.Span(className="uw-traces__chip", children=[
        html.Span(f"{label} ", className="uw-traces__chip-label"),
        html.Span(value, className="uw-num"),
    ])


def _patent_block(kicker: str, label: str, claim: str) -> list:
    return [
        html.H3(kicker, className="uw-traces__h3"),
        html.P(label or "N/A", className="uw-traces__patentid uw-num"),
        html.Div(claim or "—", className="uw-prose uw-traces__read"),
    ]


def _verdict_block(parsed, status: str) -> html.Div:
    """PatentDiff's output up front: 'Mapped X of N' + per-element Mapped Y/N.
    Mapped = novelty (the element is found in the prior art). When there's no
    parsed output (e.g. status=error) show a calm note, not silence."""
    if parsed is None:
        return html.Div(className="uw-traces__verdict uw-traces__verdict--empty",
                        children=[
            html.Span("Tool verdict", className="uw-kicker"),
            html.P(f"No tool output — status: {status}.", className="uw-traces__empty"),
        ])
    ems = parsed.element_mappings
    mapped = sum(1 for em in ems if em.novelty)
    chips = [
        html.Span(
            className="uw-traces__vchip" + (" is-mapped" if em.novelty else ""),
            children=[
                html.Span(f"{em.element_number}", className="uw-traces__vnum uw-num"),
                html.Span("Mapped Y" if em.novelty else "Mapped N",
                          className="uw-traces__vlabel"),
            ],
        ) for em in ems
    ]
    return html.Div(className="uw-traces__verdict", children=[
        html.Div(className="uw-traces__verdict-head", children=[
            html.Span("Tool verdict", className="uw-kicker"),
            html.Span(f"Mapped {mapped} of {len(ems)}",
                      className="uw-traces__vsummary uw-num"),
        ]),
        html.Div(className="uw-traces__vchips", children=chips),
    ])


def _render_trace_detail(trace) -> html.Div:
    dims = trace.dimensions or {}
    src = trace.inputs.get("source_patent", {})
    tgt = trace.inputs.get("target_patent", {})
    children = [
        html.Span("Trace", className="uw-kicker"),
        html.Div(className="uw-traces__meta", children=[
            _meta_chip("ID", f"{trace.run_id[:12]}…"),
            _meta_chip("Status", trace.status),
            _meta_chip("Claim", dims.get("claim_type", "N/A")),
            _meta_chip("Length", dims.get("claim_length", "N/A")),
            _meta_chip("Relationship", dims.get("relationship", "N/A")),
        ]),
        # Decision first: the tool's verdict + opinion, then the claims for context.
        _verdict_block(trace.parsed_output, trace.status),
    ]
    if trace.parsed_output and trace.parsed_output.overall_opinion:
        children.append(html.H3("Overall Opinion", className="uw-traces__h3"))
        children.append(html.Div(trace.parsed_output.overall_opinion,
                                 className="uw-prose uw-traces__read"))
    children += _patent_block("Source Patent (A)", src.get("label", "N/A"),
                              src.get("independent_claim", ""))
    children += _patent_block("Target Patent (B)", tgt.get("label", "N/A"),
                              tgt.get("independent_claim", ""))
    return html.Div(className="uw-traces__reader", children=children)


# ── Trace navigator — coverage header + filterable status list ───────────────
def trace_coverage(traces: dict, annotations: dict) -> dict:
    """Coverage over the loaded traces (unit-tested)."""
    reviewed_ids = {rid for rid, a in annotations.items() if a.reviewed}
    total = len(traces)
    reviewed = sum(1 for rid in traces if rid in reviewed_ids)
    return {"total": total, "reviewed": reviewed, "reviewed_ids": reviewed_ids}


def _trace_row(run_id: str, trace, is_reviewed: bool, selected) -> html.Button:
    label = trace.inputs.get("source_patent", {}).get("label", "?")
    cls = "uw-traces__row"
    if run_id == selected:
        cls += " is-active"
    if is_reviewed:
        cls += " is-reviewed"
    return html.Button(
        id={"type": "trace-row", "run_id": run_id}, n_clicks=0, className=cls,
        children=[
            html.Span("✓" if is_reviewed else "○", className="uw-traces__row-dot",
                      **{"aria-hidden": "true"}),
            html.Span(label[:22], className="uw-traces__row-label"),
            html.Span(run_id[:8], className="uw-traces__row-id uw-num"),
        ])


@callback(
    Output("traces-coverage", "children"),
    Output("traces-list", "children"),
    Input("traces-filter", "value"),
    Input("ann-version", "data"),
    Input("selected-trace", "data"),
)
def render_nav(filt, _ver, selected):
    traces = _load_traces()
    cov = trace_coverage(traces, load_annotations(ANNOTATIONS_FILE))
    total, reviewed, reviewed_ids = cov["total"], cov["reviewed"], cov["reviewed_ids"]
    pct = (reviewed / total * 100) if total else 0
    coverage = [
        html.Div(className="uw-traces__cov-head", children=[
            html.Span(f"{reviewed} of {total} reviewed",
                      className="uw-traces__cov-text uw-num"),
            html.Span(f"{pct:.0f}%", className="uw-traces__cov-pct uw-num"),
        ]),
        html.Div(className="uw-kt__bar", children=html.Div(
            className="uw-kt__fill", style={"width": f"{pct:.0f}%"})),
    ]
    rows = []
    for run_id, t in traces.items():
        is_rev = run_id in reviewed_ids
        if filt == "todo" and is_rev:
            continue
        if filt == "done" and not is_rev:
            continue
        rows.append(_trace_row(run_id, t, is_rev, selected))
    if not rows:
        rows = [html.P("No traces in this filter.", className="uw-traces__empty")]
    return coverage, rows


@callback(
    Output("selected-trace", "data"),
    Input({"type": "trace-row", "run_id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def pick_trace(_clicks):
    # Ignore the mount/re-render fire (n_clicks=0); act only on a real click.
    if not ctx.triggered_id or not (ctx.triggered and ctx.triggered[0].get("value")):
        return no_update
    return ctx.triggered_id["run_id"]


@callback(
    Output("traces-detail", "children"),
    Output("ann-verdict", "value"),
    Output("ann-modes", "value"),
    Output("ann-comment", "value"),
    Output("ann-reviewed", "value"),
    Input("selected-trace", "data"),
    State("traces-phase", "data"),
    prevent_initial_call=True,
)
def _select_trace(run_id, phase):
    if not run_id:
        return no_update, no_update, no_update, no_update, no_update
    traces = _load_traces()
    trace = traces.get(run_id)
    if trace is None:
        return (html.P("Trace not found.", className="uw-traces__empty"),
                "PASS", [], "", [])
    prev = load_annotations(ANNOTATIONS_FILE).get(run_id)
    if prev is None:
        return _render_trace_detail(trace), "PASS", [], "", []
    modes = (prev.failure_modes if phase == 3 else prev.open_coded_failure_modes) or []
    return (_render_trace_detail(trace), prev.verdict, modes, prev.comment or "",
            (["yes"] if prev.reviewed else []))


@callback(
    Output("ann-status", "children"),
    Output("ann-version", "data"),
    Input("ann-save", "n_clicks"),
    State("selected-trace", "data"),
    State("ann-verdict", "value"),
    State("ann-modes", "value"),
    State("ann-comment", "value"),
    State("ann-reviewed", "value"),
    State("traces-phase", "data"),
    State("ann-version", "data"),
    prevent_initial_call=True,
)
def _save(_n, run_id, verdict, modes, comment, reviewed, phase, ann_version):
    if not run_id:
        return "Select a trace first.", no_update
    modes = modes or []
    errors = validate_annotation(verdict, modes, comment or "")
    if errors:
        return (html.Span("Couldn't save: " + "; ".join(errors),
                          className="uw-status--error"), no_update)
    traces = _load_traces()
    trace = traces.get(run_id)
    dimensions = trace.dimensions if trace else None
    annotations = load_annotations(ANNOTATIONS_FILE)
    annotations[run_id] = build_record(
        run_id=run_id, phase=phase, verdict=verdict, failure_modes_ids=modes,
        comment=comment, reviewed=bool(reviewed), dimensions=dimensions,
    )
    persist_record(ANNOTATIONS_FILE, annotations)
    return (html.Span("Annotation saved.", className="uw-status--ok"),
            (ann_version or 0) + 1)
