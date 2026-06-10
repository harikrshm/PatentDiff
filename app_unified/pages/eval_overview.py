# app_unified/pages/eval_overview.py
"""Overview — the analyst console, folded in as the /eval page."""
import dash

from app_workbench.app import build_console_body

dash.register_page(__name__, path="/eval", name="Overview")

layout = build_console_body()
