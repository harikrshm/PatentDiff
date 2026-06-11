"""PatentDiff Eval Dashboard — /eval page layout builder.

Exposes ``build_console_body()`` for the unified app's /eval page: a 6-block
instrument dashboard (2x3 grid). "Show, don't conclude" — visualization and
numbers only. The unified shell owns the global Dash instance, dcc.Location,
dcc.Store (theme / data-version), and the theme-toggle; this module must NOT
duplicate any of those.

Entry point: ``python -m app_unified.app`` (route /eval).
"""
from __future__ import annotations

from dash import dcc, html

from app_workbench.data import trace_set_options


def _loading(child, **kwargs):
    """Wrap a dynamic container so a subtle indigo spinner shows while it updates."""
    return dcc.Loading(child, type="dot", color="#4F46E5",
                       className="wb-loading", **kwargs)


def _placeholder(task: str) -> html.Div:
    """Temporary block body until the owning task fills it in."""
    return html.Div(className="uw-dash__placeholder",
                    children=html.Span(f"⌁ {task}", className="wb-mono"))


def _block(kicker: str, title: str, body, *, wide: bool = False) -> html.Section:
    """One instrument card in the dashboard grid."""
    cls = "uw-dash__block" + (" uw-dash__block--wide" if wide else "")
    return html.Section(
        className=cls,
        children=[
            html.Div(
                className="uw-dash__block-head",
                children=[
                    html.Span(kicker, className="wb-kicker uw-dash__block-kicker"),
                    html.H2(title, className="uw-dash__block-title"),
                ],
            ),
            html.Div(className="uw-dash__block-body", children=body),
        ],
    )


def _eval_toggle() -> html.Div:
    """Segmented PHOSITA · Citation · Either control (drives the Block 3 heatmap)."""
    return html.Div(
        className="wb-segmented",
        role="radiogroup",
        **{"aria-label": "Show eval: PHOSITA, Citation, or Either"},
        children=dcc.RadioItems(
            id="eval-toggle",
            options=[
                {"label": "PHOSITA", "value": "phosita"},
                {"label": "Citation", "value": "citation"},
                {"label": "Either", "value": "either"},
            ],
            value="phosita",
            className="wb-segmented__items",
        ),
    )


def _block1_trace_properties() -> list:
    """Trace-set selector + Run eval + status + last-run + run metadata.

    The run UI is a STATIC part of this block (not a floating header). The
    run-eval-btn n_clicks guard (callbacks.run_eval) prevents run-on-navigation.
    """
    return [
        html.Div(
            className="uw-dash__field",
            children=[
                html.Label("Trace set", htmlFor="corpus-selector", className="wb-kicker"),
                dcc.Dropdown(
                    id="corpus-selector", options=trace_set_options(), value="live",
                    clearable=False, className="wb-dropdown wb-dropdown--corpus",
                ),
            ],
        ),
        html.Div(
            className="uw-dash__run",
            children=[
                html.Button("Run eval", id="run-eval-btn", n_clicks=0,
                            className="wb-btn wb-btn--primary"),
                html.Span(id="run-eval-status", className="wb-controlbar__status",
                          role="status", **{"aria-live": "polite"}),
            ],
        ),
        html.Div(
            className="uw-dash__meta",
            children=[
                html.Div(className="uw-dash__metarow", children=[
                    html.Span("Last run", className="wb-kicker"),
                    html.Span("—", id="last-run", className="wb-num"),
                ]),
                # T2 fills richer run metadata (prompt version, n scored) here.
                html.Div(id="trace-meta", className="uw-dash__metagrid"),
            ],
        ),
    ]


def _block2_eval_summary() -> html.Div:
    """Interim: the existing 'how bad' KPI row (render_kpis). T3 replaces this
    with the failure-mode share-of-FAILs bar chart."""
    return _loading(html.Div(id="kpi-row"))


def _block3_heatmap() -> list:
    """Dimension heatmap. T4 adds the row/col dimension dropdowns; for now it
    keeps the eval toggle + the existing heatmap container."""
    return [
        html.Div(className="uw-dash__field", children=[
            html.Span("Show eval", className="wb-kicker"),
            _eval_toggle(),
        ]),
        _loading(html.Div(id="heatmap-container", className="wb-card wb-heatmap-card")),
    ]


def build_console_body() -> html.Div:
    """The /eval dashboard: a 2x3 grid of instrument blocks. No funnel, no
    machine-written insight — just the controls, charts, and numbers."""
    return html.Div(
        className="wb-root uw-dash",
        children=html.Div(
            className="uw-dash__grid",
            children=[
                _block("01 · SET & RUN", "Trace Properties", _block1_trace_properties()),
                _block("02 · HOW BAD", "Eval Summary", _block2_eval_summary()),
                _block("03 · WHERE", "Dimension Heatmap", _block3_heatmap()),
                _block("04 · VS TARGET", "Eval Score vs Target", _placeholder("Block 4 · T5")),
                _block("05 · OVER TIME", "Metric Trajectory", _placeholder("Block 5 · T6")),
                _block("06 · TARGET", "Set KPI Target", _placeholder("Block 6 · T7")),
            ],
        ),
    )


# Side-effect import — registers @callback decorators against the global Dash registry.
from app_workbench import callbacks  # noqa: E402,F401
