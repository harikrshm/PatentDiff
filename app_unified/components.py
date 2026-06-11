# app_unified/components.py
"""Shared chrome for the unified workbench shell — left sidebar + page header.

The persistent left sidebar is the single primary navigation. Active state is
re-rendered per route by a callback in app.py (`sidebar_nav(pathname)`).
"""
from __future__ import annotations

from dash import dcc, html

# (label, href, glyph). Glyphs are neutral geometric marks (not emoji) so they
# read as instrument iconography and survive the icon-collapsed sidebar.
PRIMARY = [("PatentDiff", "/", "⊟")]
EVAL_GROUP = [
    ("Overview", "/eval", "◉"),
    ("Traces", "/eval/traces", "≣"),
    ("Comparison", "/eval/comparison", "⇄"),
]


def _is_active(href: str, path: str) -> bool:
    if href == "/":
        return path == "/"
    if href == "/eval":
        return path == "/eval"           # exact — sub-routes own their own active
    return path == href or path.startswith(href + "/")


def _nav_item(label: str, href: str, glyph: str, active: bool) -> dcc.Link:
    # NOTE: dcc.Link has a fixed prop list (no aria-* passthrough), so active
    # state is conveyed structurally here (indigo rail + bg + text). Screen-reader
    # aria-current is set in the T10 accessibility pass via a clientside attribute.
    return dcc.Link(
        href=href,
        className="uw-nav__item" + (" is-active" if active else ""),
        title=label,                      # tooltip when collapsed to icons (T3)
        children=[
            html.Span(glyph, className="uw-nav__icon", **{"aria-hidden": "true"}),
            html.Span(label, className="uw-nav__label"),
        ],
    )


def sidebar_nav(active_path: str | None) -> list:
    """Sidebar nav children with the current route marked active."""
    path = active_path or "/"
    items = [_nav_item(l, h, g, _is_active(h, path)) for l, h, g in PRIMARY]
    items.append(html.Div("Evaluation", className="uw-nav__group"))
    items += [_nav_item(l, h, g, _is_active(h, path)) for l, h, g in EVAL_GROUP]
    return items


def sidebar() -> html.Aside:
    """Persistent left sidebar: brand + primary nav.

    The <aside> reserves the layout footprint (full or, on /eval, collapsed
    width); the inner __panel is the visual surface that overlays content when
    hovered/focused while collapsed, so expanding never shifts the page (T3).
    """
    return html.Aside(
        id="uw-sidebar",
        className="uw-sidebar",
        **{"aria-label": "Primary"},
        children=html.Div(
            className="uw-sidebar__panel",
            children=[
                html.Div(
                    className="uw-sidebar__brand",
                    children=[
                        html.Span("PD", className="uw-sidebar__brand-mark",
                                  **{"aria-hidden": "true"}),
                        # Themeable wordmark (mirrors assets/logo.svg) — "Diff"
                        # carries the indigo accent; colors flip with the theme.
                        html.Span(
                            className="uw-sidebar__wordmark",
                            **{"aria-label": "PatentDiff"},
                            children=[
                                html.Span("Patent", className="uw-wordmark__a"),
                                html.Span("Diff", className="uw-wordmark__b"),
                            ],
                        ),
                    ],
                ),
                html.Nav(id="uw-sidebar-nav", className="uw-nav",
                         children=sidebar_nav("/")),
            ],
        ),
    )


def page_header(title: str, subtitle: str = "") -> html.Header:
    """Lightweight per-page header for the ported views."""
    children = [html.H1(title, className="uw-page__title")]
    if subtitle:
        children.append(html.P(subtitle, className="uw-page__subtitle"))
    return html.Header(className="uw-page__header", children=children)
