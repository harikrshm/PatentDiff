"""Surface 1 — Explore / Eval Workbench."""
from __future__ import annotations

import dash
from dash import html

dash.register_page(__name__, path="/", name="Explore")

layout = html.Div([html.H2("Explore / Eval Workbench")])
