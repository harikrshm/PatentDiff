# app_unified/pages/eval_overview.py
"""Overview — the analyst console, folded in as the /eval page."""
import dash
from dash import dcc, html

from app_workbench.app import build_console_body

dash.register_page(__name__, path="/eval", name="Overview")

layout = html.Div(
    [
        dcc.Link(
            "→ Ask the Experiment Agent to act on this",
            href="/eval/agent",
            className="wb-link",
        ),
        build_console_body(),
    ]
)
