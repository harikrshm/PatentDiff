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


def _block2_eval_summary() -> list:
    """Radial gauge of the current FAIL-rate for the SELECTED eval on the active
    set (render_failrate_gauge). Segmented PHOSITA · Citation picker drives it;
    severity-colored needle with a marker at the KPI target. No failure-mode
    breakdown, no untagged/unverified split."""
    return [
        html.Div(
            className="wb-segmented uw-dash__fr-pick",
            role="radiogroup",
            **{"aria-label": "Failure-rate eval: PHOSITA or Citation"},
            children=dcc.RadioItems(
                id="fr-eval",
                options=[
                    {"label": "PHOSITA", "value": "phosita"},
                    {"label": "Citation", "value": "citation"},
                ],
                value="phosita",
                className="wb-segmented__items",
            ),
        ),
        _loading(dcc.Graph(
            id="fr-gauge",
            config={"displayModeBar": False, "responsive": True},
            style={"height": "208px"},
        )),
        html.P(id="fr-caption", className="wb-caption"),
    ]


_DIM_OPTIONS = [
    {"label": "Claim type", "value": "claim_type"},
    {"label": "Claim length", "value": "claim_length"},
    {"label": "Relationship", "value": "relationship"},
]


def _block3_heatmap() -> list:
    """Dimension heatmap with selectable row/col dimensions + the eval toggle."""
    def _dim(id_, label, default):
        return html.Div(className="uw-dash__dim", children=[
            html.Label(label, className="wb-kicker", htmlFor=id_),
            dcc.Dropdown(id=id_, options=_DIM_OPTIONS, value=default,
                         clearable=False, className="wb-dropdown wb-dropdown--tier"),
        ])
    return [
        html.Div(className="uw-dash__heat-controls", children=[
            html.Div(className="uw-dash__field", children=[
                html.Span("Show eval", className="wb-kicker"),
                _eval_toggle(),
            ]),
            _dim("heat-row", "Rows", "claim_type"),
            _dim("heat-col", "Columns", "relationship"),
        ]),
        _loading(dcc.Graph(
            id="heatmap",
            config={"displayModeBar": False, "responsive": True},
            style={"height": "300px"})),
        html.Div(id="heatmap-avg", className="uw-dash__heat-avg"),
    ]


def _block6_set_target() -> list:
    """PM inputs that write a KPI target (rate + date + baseline run) per eval
    kind; saving (render in callbacks) bumps kpi-version so Blocks 4/5 refresh."""
    def _field(label, control):
        return html.Div(className="uw-dash__field", children=[
            html.Label(label, className="wb-kicker"), control])
    return [
        _field("Metric", dcc.Dropdown(
            id="kt-eval",
            options=[{"label": "PHOSITA", "value": "phosita"},
                     {"label": "Citation", "value": "citation"}],
            value="phosita", clearable=False, className="wb-dropdown wb-dropdown--tier")),
        _field("Target max FAIL %", dcc.Input(
            id="kt-rate", type="number", min=0, max=100, step=1,
            placeholder="e.g. 15", className="uw-input")),
        _field("Target date", dcc.Input(
            id="kt-date", type="text", placeholder="YYYY-MM-DD", className="uw-input")),
        _field("Baseline run", dcc.Dropdown(
            id="kt-baseline", options=[], placeholder="earliest (default)",
            className="wb-dropdown wb-dropdown--tier")),
        html.Button("Save target", id="kt-save", n_clicks=0,
                    className="uw-btn uw-btn--primary uw-dash__save"),
        html.Div(id="kt-status", className="uw-status", role="status",
                 **{"aria-live": "polite"}),
    ]


def build_console_body() -> html.Div:
    """The /eval dashboard: a 2x3 grid of instrument blocks. No funnel, no
    machine-written insight — just the controls, charts, and numbers."""
    return html.Div(
        className="wb-root uw-dash",
        children=[
            # Page-local signal: Block 6 bumps this when a target is saved so
            # Blocks 4 & 5 refresh without a reload.
            dcc.Store(id="kpi-version", data=0),
            html.Div(
                className="uw-dash__grid",
                children=[
                    _block("SET & RUN", "Trace Properties", _block1_trace_properties()),
                    _block("HOW BAD", "Eval Summary", _block2_eval_summary()),
                    _block("WHERE", "Dimension Heatmap", _block3_heatmap()),
                    _block("TARGET", "Set KPI Target", _block6_set_target()),
                    _block("VS TARGET", "Eval Score vs Target",
                           _loading(html.Div(id="kpi-target-readout"))),
                    _block("OVER TIME", "Metric Trajectory", _loading(dcc.Graph(
                        id="trajectory-chart",
                        config={"displayModeBar": False, "responsive": True},
                        style={"height": "232px"}))),
                ],
            ),
        ],
    )


# Side-effect import — registers @callback decorators against the global Dash registry.
from app_workbench import callbacks  # noqa: E402,F401
