"""Traces — annotation tool. Port of app_annotation.py.

Trace browser (left) + read-only trace view (centre) + failure-mode coder
(right). Persists to traces/traces_annotations.jsonl via core.annotation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import dash
from dash import Input, Output, State, callback, dcc, html, no_update

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
def _trace_options() -> List[dict]:
    opts = []
    for run_id, t in _load_traces().items():
        label = t.inputs.get("source_patent", {}).get("label", "?")
        opts.append({"label": f"{label[:24]}  ·  {run_id[:8]}", "value": run_id})
    return opts


layout = html.Div(
    className="uw-page uw-page--memo uw-traces",
    children=[
        page_header("Traces — Error Analysis", "Browse traces and code failure modes."),
        dcc.Store(id="traces-phase", data=detect_phase(TAXONOMY_FILE)),
        html.Div(
            className="uw-traces__grid",
            children=[
                html.Aside(
                    className="uw-traces__nav",
                    children=[
                        html.Span("Contents", className="uw-kicker"),
                        html.Label("Trace", className="uw-label"),
                        dcc.Dropdown(id="traces-select", options=_trace_options(),
                                     placeholder="Select a trace…",
                                     className="uw-dropdown wb-dropdown"),
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
                        html.Span("Your reading", className="uw-field__voice"),
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
        *_patent_block("Source Patent (A)", src.get("label", "N/A"),
                       src.get("independent_claim", "")),
        *_patent_block("Target Patent (B)", tgt.get("label", "N/A"),
                       tgt.get("independent_claim", "")),
    ]
    if trace.parsed_output:
        children.append(html.H3("Overall Opinion", className="uw-traces__h3"))
        children.append(html.Div(trace.parsed_output.overall_opinion,
                                 className="uw-prose uw-traces__read"))
    return html.Div(className="uw-traces__reader", children=children)


@callback(
    Output("traces-detail", "children"),
    Output("ann-verdict", "value"),
    Output("ann-modes", "value"),
    Output("ann-comment", "value"),
    Output("ann-reviewed", "value"),
    Input("traces-select", "value"),
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
    Input("ann-save", "n_clicks"),
    State("traces-select", "value"),
    State("ann-verdict", "value"),
    State("ann-modes", "value"),
    State("ann-comment", "value"),
    State("ann-reviewed", "value"),
    State("traces-phase", "data"),
    prevent_initial_call=True,
)
def _save(_n, run_id, verdict, modes, comment, reviewed, phase):
    if not run_id:
        return "Select a trace first."
    modes = modes or []
    errors = validate_annotation(verdict, modes, comment or "")
    if errors:
        return html.Span("Couldn't save: " + "; ".join(errors),
                         className="uw-status--error")
    traces = _load_traces()
    trace = traces.get(run_id)
    dimensions = trace.dimensions if trace else None
    annotations = load_annotations(ANNOTATIONS_FILE)
    annotations[run_id] = build_record(
        run_id=run_id, phase=phase, verdict=verdict, failure_modes_ids=modes,
        comment=comment, reviewed=bool(reviewed), dimensions=dimensions,
    )
    persist_record(ANNOTATIONS_FILE, annotations)
    return html.Span("Annotation saved.", className="uw-status--ok")
