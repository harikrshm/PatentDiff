# app_unified/pages/eval_overview.py
"""Overview — the analyst console, folded in as the /eval page."""
import dash
from dash import dcc, html

from app_workbench.app import build_console_body

dash.register_page(__name__, path="/eval", name="Dashboard")

layout = html.Div(
    [
        html.Div(
            className="uw-dash__agentlink",
            children=dcc.Link(
                "Ask the Experiment Agent to act on this →",
                href="/eval/agent",
                className="uw-link",
            ),
        ),
        build_console_body(),
    ]
)
