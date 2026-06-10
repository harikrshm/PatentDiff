# app_unified/pages/eval_comparison.py
import dash
from dash import html

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

layout = html.Div("Comparison — coming in Task 5", className="uw-stub")
