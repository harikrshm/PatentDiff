"""Review — trace review coverage: how much of the corpus has been reviewed.

Read-only instrument readout. `layout` is a function so the numbers refresh on
every visit (annotations are written on the Traces tab). Backend frozen.
"""
from __future__ import annotations

from pathlib import Path

import dash
from dash import html

from app_unified.components import page_header
from core.annotation import load_annotations
from core.trace_loader import load_traces

dash.register_page(__name__, path="/eval/review", name="Review")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_FILE = REPO_ROOT / "traces" / "traces.jsonl"
ANNOTATIONS_FILE = REPO_ROOT / "traces" / "traces_annotations.jsonl"

_MAX_LEFT = 40  # cap the "what's left" chip list


def review_progress(traces_file: Path = TRACES_FILE,
                    annotations_file: Path = ANNOTATIONS_FILE) -> dict:
    """Coverage counts over the trace corpus (unit-tested)."""
    traces = load_traces(traces_file)
    trace_ids = [t.run_id for t in traces]
    total = len(trace_ids)
    anns = load_annotations(annotations_file)
    reviewed_ids = {rid for rid, a in anns.items() if a.reviewed}
    annotated_ids = set(anns)

    reviewed = sum(1 for rid in trace_ids if rid in reviewed_ids)
    annotated_not_reviewed = sum(
        1 for rid in trace_ids if rid in annotated_ids and rid not in reviewed_ids)
    untouched = total - sum(1 for rid in trace_ids if rid in annotated_ids)
    unreviewed = [rid for rid in trace_ids if rid not in reviewed_ids]
    return {
        "total": total, "reviewed": reviewed,
        "annotated_not_reviewed": annotated_not_reviewed,
        "untouched": untouched, "unreviewed": unreviewed,
    }


def _stat(label: str, value: int) -> html.Div:
    return html.Div(className="uw-review__stat", children=[
        html.Span(str(value), className="uw-review__stat-val uw-num"),
        html.Span(label, className="uw-review__stat-label"),
    ])


def layout() -> html.Div:
    p = review_progress()
    total, reviewed = p["total"], p["reviewed"]
    pct = (reviewed / total * 100) if total else 0
    left = p["unreviewed"]

    progress = html.Div(className="uw-review__card", children=[
        html.Div(className="uw-review__head", children=[
            html.Span(f"{reviewed} of {total}", className="uw-review__headline uw-num"),
            html.Span("traces reviewed", className="uw-review__headline-sub"),
            html.Span(f"{pct:.0f}%", className="uw-review__pct uw-num"),
        ]),
        html.Div(className="uw-kt__bar", children=html.Div(
            className="uw-kt__fill", style={"width": f"{pct:.0f}%"})),
        html.Div(className="uw-review__stats", children=[
            _stat("Reviewed", reviewed),
            _stat("Annotated, not reviewed", p["annotated_not_reviewed"]),
            _stat("Untouched", p["untouched"]),
        ]),
    ])

    if left:
        shown = left[:_MAX_LEFT]
        chips = [html.Span(rid[:8], className="uw-review__chip uw-num") for rid in shown]
        more = (f"  +{len(left) - _MAX_LEFT} more"
                if len(left) > _MAX_LEFT else "")
        whats_left = html.Div(className="uw-review__left", children=[
            html.Div(className="uw-review__left-head", children=[
                html.Span("What's left", className="wb-kicker"),
                html.Span(f"{len(left)} to review", className="uw-num"),
            ]),
            html.Div(className="uw-review__chips", children=chips + (
                [html.Span(more, className="uw-review__more")] if more else [])),
        ])
    else:
        whats_left = html.P("Everything is reviewed. ✓", className="uw-review__done")

    return html.Div(
        className="uw-page uw-page--instrument uw-review",
        children=[
            page_header("Review — Trace coverage",
                        "How much of the corpus has been reviewed."),
            progress,
            whats_left,
        ],
    )
