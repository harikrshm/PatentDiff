"""Small shared render helpers for the workbench pages."""
from __future__ import annotations

from dash import html

GREEN, YELLOW, RED = "#2e7d32", "#f9a825", "#c62828"


def fail_color(rate: float) -> str:
    """Red/yellow/green for a FAIL rate in [0,1]."""
    if rate >= 0.67:
        return RED
    if rate >= 0.34:
        return YELLOW
    return GREEN


def kpi_tile(label: str, value: str, sub: str) -> html.Div:
    """A single KPI metric tile."""
    return html.Div(
        [
            html.Div(label, style={"fontSize": "0.8rem", "color": "#555"}),
            html.Div(value, style={"fontSize": "1.8rem", "fontWeight": "700"}),
            html.Div(sub, style={"fontSize": "0.75rem", "color": "#888"}),
        ],
        style={"padding": "0.75rem", "border": "1px solid #e0e0e0",
               "borderRadius": "8px", "minWidth": "150px"},
    )


def assumed_badge() -> html.Span:
    """The ⚠ badge marking a domain-assumed (not measured) input."""
    return html.Span(
        "⚠ assumed",
        title="Placeholder until the live claim_type × relationship query "
              "distribution is instrumented.",
        style={"color": RED, "fontSize": "0.7rem", "marginLeft": "0.4rem"},
    )


def evidence_note(text: str) -> html.Div:
    """Render a deterministic evidence-note, clearly labeled as a hypothesis."""
    return html.Div(
        [
            html.Span("HYPOTHESIS  ",
                      style={"fontWeight": "700", "color": "#1565c0",
                             "fontSize": "0.7rem"}),
            html.Span(text, style={"fontSize": "0.85rem"}),
        ],
        style={"padding": "0.4rem 0.6rem", "background": "#e3f2fd",
               "borderRadius": "6px", "margin": "0.3rem 0"},
    )
