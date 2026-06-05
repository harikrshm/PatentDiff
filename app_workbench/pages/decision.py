"""Surface 2 — Decision."""
from __future__ import annotations

import dash
from dash import html

dash.register_page(__name__, path="/decision", name="Decision")

layout = html.Div([html.H2("Decision")])
