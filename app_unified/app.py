# app_unified/app.py
"""Unified PatentDiff workbench — single Dash app housing every tool.

Routes:
    /                 PatentDiff prototype
    /eval             Overview (analyst console)
    /eval/traces      Annotation tool
    /eval/comparison  Before/after eval delta

Run with:
    python -m app_unified.app
"""
from __future__ import annotations

from pathlib import Path

import diskcache
from dash import (Dash, DiskcacheManager, Input, Output, State, dcc, html,
                  page_container)

from app_unified.components import eval_subnav, top_nav

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / ".dash_cache"

background_callback_manager = DiskcacheManager(diskcache.Cache(str(CACHE_DIR)))

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    background_callback_manager=background_callback_manager,
    suppress_callback_exceptions=True,
)
app.title = "PatentDiff — Workbench"


def _theme_toggle() -> html.Button:
    return html.Button(
        id="theme-toggle",
        className="uw-themetoggle",
        n_clicks=0,
        title="Toggle light / dark",
        **{"aria-label": "Toggle light or dark theme"},
        children=html.Span("◐", className="uw-themetoggle__glyph",
                            **{"aria-hidden": "true"}),
    )


app.layout = html.Div(
    className="uw-root",
    children=[
        dcc.Location(id="url"),
        html.Div(id="url-writer-dummy", style={"display": "none"}),
        dcc.Store(id="theme", data="light"),     # app-global; console figures read it
        dcc.Store(id="data-version", data=0),     # console refresh signal
        html.Header(
            className="uw-appbar",
            children=[
                html.Div(
                    className="uw-appbar__brand",
                    children=[
                        html.Span("PatentDiff", className="uw-appbar__brand-strong"),
                        html.Span("Workbench", className="uw-appbar__brand-sub"),
                    ],
                ),
                top_nav(),
                _theme_toggle(),
            ],
        ),
        html.Div(id="uw-subnav-slot"),
        html.Main(className="uw-pagewrap", children=page_container),
    ],
)


# Show the eval sub-nav only on /eval* routes.
@app.callback(Output("uw-subnav-slot", "children"), Input("url", "pathname"))
def _render_subnav(pathname: str):
    pathname = pathname or "/"
    if pathname == "/eval" or pathname.startswith("/eval/"):
        return eval_subnav(pathname)
    return None


# Theme toggle (clientside): flips <html data-theme>, persists, mirrors to `theme`
# store so server-side Plotly figures recolor. On initial load (no click) it just
# reports the theme workbench.js already set.
app.clientside_callback(
    """
    function(n_clicks, current) {
        var html = document.documentElement;
        var present = html.getAttribute('data-theme');
        if (!present) {
            present = (window.matchMedia &&
                window.matchMedia('(prefers-color-scheme: dark)').matches)
                ? 'dark' : 'light';
        }
        if (!n_clicks) { return present; }
        var next = present === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        try { localStorage.setItem('wb-theme', next); } catch (e) {}
        return next;
    }
    """,
    Output("theme", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme", "data"),
)

if __name__ == "__main__":
    app.run(debug=True)
