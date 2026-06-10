"""PatentDiff prototype — claim-diff form → Analyze → report. Port of app.py."""
from __future__ import annotations

import dash
from dash import Input, Output, State, callback, dash_table, dcc, html

from app_unified.components import page_header
from core.llm import build_system_prompt, build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response
from tracing.logger import build_trace_record
from tracing.store import append_trace

dash.register_page(__name__, path="/", name="PatentDiff")

_EMPTY_LLM = {"raw_output": "", "model": "", "tokens_input": 0,
              "tokens_output": 0, "latency_ms": 0}


def _patent_column(side: str, title: str) -> html.Div:
    return html.Div(
        className="uw-proto__col",
        children=[
            html.H2(title, className="uw-proto__coltitle"),
            dcc.Input(id=f"label-{side}", type="text", placeholder="e.g., US10,123,456",
                      className="uw-input"),
            html.Label("Independent Claim", className="uw-label"),
            dcc.Textarea(id=f"claim-{side}", className="uw-input--area", style={"height": "200px"}),
            html.Label("Specification Support", className="uw-label"),
            dcc.Textarea(id=f"spec-{side}", className="uw-input--area", style={"height": "200px"}),
        ],
    )


layout = html.Div(
    className="uw-page uw-proto",
    children=[
        page_header("PatentDiff — Patent Claim Analysis"),
        html.Div(
            className="uw-proto__grid",
            children=[
                _patent_column("a", "Patent A (Source)"),
                _patent_column("b", "Patent B (Target / Prior Art)"),
            ],
        ),
        html.Button("Analyze", id="analyze-btn", n_clicks=0,
                    className="uw-btn uw-btn--primary uw-proto__analyze"),
        html.Div(id="analyze-status", className="uw-status", role="status",
                 **{"aria-live": "polite"}),
        dcc.Loading(html.Div(id="analyze-report"), type="dot"),
        html.Div(id="analyze-meta"),
    ],
)


def run_analysis(label_a, claim_a, spec_a, label_b, claim_b, spec_b):
    """Pure logic: validate, call the LLM, append a trace, build report children.

    Returns (status_message, report_children, meta_children). status_message is
    "" on success, an error string otherwise. Mirrors app.py exactly.
    """
    if not all([label_a, claim_a, spec_a, label_b, claim_b, spec_b]):
        return "Please fill in all fields for both patents.", None, None

    source = PatentInput(label=label_a, independent_claim=claim_a, specification=spec_a)
    target = PatentInput(label=label_b, independent_claim=claim_b, specification=spec_b)

    system_prompt = build_system_prompt()
    user_prompt, truncation_warnings = build_user_prompt(source, target)

    llm_response = None
    try:
        llm_response = call_groq(system_prompt, user_prompt)
        report = parse_llm_response(llm_response["raw_output"])
        append_trace(build_trace_record(
            source_patent=source, target_patent=target,
            system_prompt=system_prompt, user_prompt=user_prompt,
            llm_response=llm_response, parsed_output=report,
            status="success", error=None, truncation_warnings=truncation_warnings,
        ))
    except Exception as e:  # noqa: BLE001 — mirror app.py's broad guard
        append_trace(build_trace_record(
            source_patent=source, target_patent=target,
            system_prompt=system_prompt, user_prompt=user_prompt,
            llm_response=llm_response or dict(_EMPTY_LLM),
            parsed_output=None, status="error", error=str(e),
            truncation_warnings=truncation_warnings,
        ))
        return f"Analysis failed: {e}", None, None

    rows = [{
        "Element #": em.element_number,
        "Patent A Element": em.element_text,
        "Patent B Corresponding Text": em.corresponding_text,
        "Novelty": "✅" if em.novelty else "❌",
        "Inventive Step": "✅" if em.inventive_step else "❌",
        "Verdict": em.verdict,
        "Comment": em.comment,
    } for em in report.element_mappings]

    report_children = html.Div([
        html.H2("Element Mapping", className="uw-proto__h2"),
        dash_table.DataTable(
            data=rows,
            columns=[{"name": c, "id": c} for c in
                     ["Element #", "Patent A Element", "Patent B Corresponding Text",
                      "Novelty", "Inventive Step", "Verdict", "Comment"]],
            style_table={"overflowX": "auto"}, style_cell={"textAlign": "left"},
        ),
        html.H2("Overall Opinion", className="uw-proto__h2"),
        html.P(report.overall_opinion),
    ])
    meta_children = html.Details([
        html.Summary("Run Metadata"),
        html.P(f"Model: {llm_response['model']}"),
        html.P(f"Input tokens: {llm_response['tokens_input']}"),
        html.P(f"Output tokens: {llm_response['tokens_output']}"),
        html.P(f"Latency: {llm_response['latency_ms']}ms"),
    ])
    return "", report_children, meta_children


@callback(
    Output("analyze-status", "children"),
    Output("analyze-report", "children"),
    Output("analyze-meta", "children"),
    Input("analyze-btn", "n_clicks"),
    State("label-a", "value"), State("claim-a", "value"), State("spec-a", "value"),
    State("label-b", "value"), State("claim-b", "value"), State("spec-b", "value"),
    prevent_initial_call=True,
)
def _on_analyze(_n, la, ca, sa, lb, cb, sb):
    return run_analysis(la, ca, sa, lb, cb, sb)
