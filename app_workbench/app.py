"""PatentDiff Eval Workbench — Dash entry point.

Run with:
    python -m app_workbench.app
"""
from __future__ import annotations

from pathlib import Path

import dash
import diskcache
from dash import DiskcacheManager, Dash, dcc, html, page_container

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
app.title = "PatentDiff — Eval Workbench"

app.layout = html.Div(
    [
        html.H1("PatentDiff — Eval Workbench"),
        html.Nav(
            [
                dcc.Link("Explore", href="/"),
                html.Span(" · "),
                dcc.Link("Decision", href="/decision"),
            ]
        ),
        html.Hr(),
        page_container,
    ]
)

if __name__ == "__main__":
    app.run(debug=True)
