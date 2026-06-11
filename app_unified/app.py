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

from app_unified.components import sidebar, sidebar_nav

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
app.title = "PatentDiff"


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
        html.Div(
            id="uw-shell",
            className="uw-shell",
            children=[
                sidebar(),
                html.Div(
                    className="uw-content",
                    children=[
                        html.Header(
                            className="uw-toolbar",
                            children=[
                                # Page-contextual controls mount here per route.
                                html.Div(id="uw-toolbar-context",
                                         className="uw-toolbar__context"),
                                _theme_toggle(),
                            ],
                        ),
                        html.Main(className="uw-pagewrap", children=page_container),
                    ],
                ),
            ],
        ),
    ],
)


# Per-route shell state: mark the active nav item AND collapse the sidebar to an
# icon rail on the Overview console (/eval only) so its own step-rail can lead the
# left edge. Every other route shows the full labeled sidebar.
@app.callback(
    Output("uw-sidebar-nav", "children"),
    Output("uw-shell", "className"),
    Input("url", "pathname"),
)
def _shell_state(pathname: str):
    collapsed = (pathname or "/") == "/eval"
    shell_class = "uw-shell" + (" is-collapsed" if collapsed else "")
    return sidebar_nav(pathname), shell_class


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
