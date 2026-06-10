# app_unified/components.py
"""Shared chrome for the unified workbench shell."""
from __future__ import annotations

from dash import dcc, html

# Top-level sections and the eval sub-views (label, href).
TOP_NAV = [("PatentDiff", "/"), ("Evaluation", "/eval")]
EVAL_SUBNAV = [
    ("Overview", "/eval"),
    ("Traces", "/eval/traces"),
    ("Comparison", "/eval/comparison"),
]


def top_nav() -> html.Nav:
    """Primary nav: PatentDiff | Evaluation."""
    return html.Nav(
        className="uw-topnav",
        **{"aria-label": "Primary"},
        children=[
            dcc.Link(label, href=href, className="uw-topnav__link")
            for label, href in TOP_NAV
        ],
    )


def eval_subnav(active: str) -> html.Nav:
    """Secondary strip shown on /eval* routes; `active` is the current pathname."""
    def cls(href: str) -> str:
        is_active = active == href or (href != "/eval" and active.startswith(href))
        return "uw-subnav__link" + (" is-active" if is_active else "")

    return html.Nav(
        className="uw-subnav",
        **{"aria-label": "Evaluation views"},
        children=[
            dcc.Link(label, href=href, className=cls(href)) for label, href in EVAL_SUBNAV
        ],
    )


def page_header(title: str, subtitle: str = "") -> html.Header:
    """Lightweight per-page header for the ported views."""
    children = [html.H1(title, className="uw-page__title")]
    if subtitle:
        children.append(html.P(subtitle, className="uw-page__subtitle"))
    return html.Header(className="uw-page__header", children=children)
