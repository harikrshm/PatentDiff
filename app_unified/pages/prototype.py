# app_unified/pages/prototype.py
import dash
from dash import html

dash.register_page(__name__, path="/", name="PatentDiff")

layout = html.Div("PatentDiff prototype — coming in Task 1", className="uw-stub")
