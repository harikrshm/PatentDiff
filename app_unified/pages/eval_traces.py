# app_unified/pages/eval_traces.py
import dash
from dash import html

dash.register_page(__name__, path="/eval/traces", name="Traces")

layout = html.Div("Traces — coming in Task 2", className="uw-stub")
