"""PatentDiff Eval Workbench — console layout builder.

Exposes ``build_console_body()`` for use by the unified app's /eval page.
The unified shell owns the global Dash instance, dcc.Location, dcc.Store
(theme / data-version), and the theme-toggle button; this module must NOT
duplicate any of those.

Previously run standalone with ``python -m app_workbench.app``; the unified
app (``python -m app_unified.app``) is now the entry point.
"""
from __future__ import annotations

from dash import Input, Output, dash_table, dcc, html

from app_workbench.components import assumed_badge, human_field
from app_workbench.constants import DECISION_MODES, LAYER_OPTIONS
from app_workbench.data import trace_set_options

# Priority dimensions (mirrors core.priority.MODE_VERDICT + the analyst grid).
PRIORITY_MODES = ["Absent PHOSITA", "Citation Text"]
PRIORITY_IMPACT_DEFAULT = {"Absent PHOSITA": "High", "Citation Text": "Low"}
PRIORITY_CELLS = [(ct, rel) for ct in ("Method", "System")
                  for rel in ("Anticipation", "Implicit", "Novel")]
TIER_OPTIONS = [{"label": t, "value": t} for t in ("High", "Med", "Low")]

# ── The five funnel steps: (anchor id, number, title, the question it answers) ──
STEPS = [
    ("how-bad", "01", "How bad", "What's the headline failure magnitude?"),
    ("where", "02", "Where", "Which dimensions concentrate the failures?"),
    ("why", "03", "Why", "Which architecture layer does the shape implicate?"),
    ("priority", "04", "Priority", "What ranks first by Frequency × Impact × Exposure?"),
    ("decision", "05", "Decision", "What do we fix first — and why this order?"),
]


def _control_bar() -> html.Header:
    """Sticky, frosted chrome: corpus selector · run eval · last-run.

    Note: the theme-toggle button is owned by the unified shell's appbar and
    must NOT be duplicated here.
    """
    return html.Header(
        className="wb-controlbar",
        children=[
            html.Div(
                className="wb-controlbar__brand",
                children=[
                    html.Span("PatentDiff", className="wb-controlbar__brand-strong"),
                    html.Span("Eval Workbench", className="wb-controlbar__brand-sub"),
                ],
            ),
            html.Div(
                className="wb-controlbar__group",
                children=[
                    html.Label("Trace set", htmlFor="corpus-selector",
                               className="wb-kicker"),
                    dcc.Dropdown(
                        id="corpus-selector",
                        options=trace_set_options(),
                        value="live",
                        clearable=False,
                        className="wb-dropdown wb-dropdown--corpus",
                    ),
                ],
            ),
            html.Div(
                className="wb-controlbar__group",
                children=[
                    html.Button(
                        "Run eval", id="run-eval-btn", n_clicks=0,
                        className="wb-btn wb-btn--primary",
                    ),
                    html.Span(id="run-eval-status", className="wb-controlbar__status",
                              role="status", **{"aria-live": "polite"}),
                ],
            ),
            html.Div(
                className="wb-controlbar__group wb-controlbar__group--last",
                children=[
                    html.Span("Last run", className="wb-kicker"),
                    html.Span("—", id="last-run", className="wb-num wb-controlbar__lastrun"),
                ],
            ),
        ],
    )


def _step_rail() -> html.Nav:
    """Slim left rail: ①–⑤ anchors with scroll-spy active state (workbench.js)."""
    return html.Nav(
        className="wb-rail",
        **{"aria-label": "Decision steps"},
        children=[
            html.A(
                href=f"#{anchor}",
                className="wb-rail__step",
                title=f"{title} — {question}",
                **{"data-step": anchor},
                children=[
                    html.Span(num, className="wb-rail__num wb-num"),
                    html.Span(title, className="wb-rail__label"),
                ],
            )
            for anchor, num, title, question in STEPS
        ],
    )


def _section(anchor: str, num: str, title: str, question: str,
             body: html.Div) -> html.Section:
    return html.Section(
        id=anchor,
        className="wb-section",
        children=[
            html.Div(
                className="wb-section__head",
                children=[
                    html.Span(f"STEP {num}", className="wb-kicker wb-section__kicker"),
                    html.H2(title, className="wb-section__title"),
                    html.P(question, className="wb-section__question"),
                ],
            ),
            body,
        ],
    )


def _loading(child, **kwargs):
    """Wrap a dynamic container so a subtle indigo spinner shows while it updates."""
    return dcc.Loading(child, type="dot", color="#4F46E5",
                       className="wb-loading", **kwargs)


def _placeholder(task: str) -> html.Div:
    """Temporary section body until the owning task fills it in."""
    return html.Div(className="wb-placeholder",
                    children=html.Span(f"⌁ {task}", className="wb-mono"))


def _eval_toggle() -> html.Div:
    """Segmented PHOSITA · Citation · Either control. Shared by §2 and §3."""
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


def _where_body() -> html.Div:
    return html.Div(
        id="where-body",
        children=[
            html.Div(
                className="wb-where__controls",
                children=[
                    html.Span("Show eval", className="wb-kicker"),
                    _eval_toggle(),
                ],
            ),
            _loading(html.Div(id="heatmap-container", className="wb-card wb-heatmap-card")),
        ],
    )


def _tier_dropdown(id_dict: dict, default: str) -> dcc.Dropdown:
    return dcc.Dropdown(
        id=id_dict, options=TIER_OPTIONS, value=default, clearable=False,
        className="wb-dropdown wb-dropdown--tier",
    )


def _impact_grid() -> html.Div:
    grid = html.Div(
        className="wb-tier-grid wb-tier-grid--impact",
        children=[
            html.Div(className="wb-tier-cell", children=[
                html.Span(mode, className="wb-tier-cell__label"),
                _tier_dropdown({"type": "impact", "mode": mode},
                               PRIORITY_IMPACT_DEFAULT[mode]),
            ])
            for mode in PRIORITY_MODES
        ],
    )
    return human_field("Impact per failure mode — domain judgment", grid,
                       help="How much each failure hurts the product if it ships. Your call.")


def _exposure_grid() -> html.Div:
    grid = html.Div(
        className="wb-tier-grid wb-tier-grid--exposure",
        children=[
            html.Div(className="wb-tier-cell", children=[
                html.Span([f"{ct} × {rel} ", assumed_badge()], className="wb-tier-cell__label"),
                _tier_dropdown({"type": "exposure", "cell": f"{ct} × {rel}"}, "Med"),
            ])
            for ct, rel in PRIORITY_CELLS
        ],
    )
    return human_field(
        ["Exposure per dimension cell — production query mix ", assumed_badge()],
        grid,
        help=("Every value is a placeholder until the live claim_type × relationship "
              "query distribution is instrumented."),
    )


# DataTable theme — tokens via CSS vars (valid as inline CSS values).
_TABLE_STYLE = dict(
    style_as_list_view=True,
    style_table={"overflowX": "auto"},
    style_header={
        "backgroundColor": "var(--color-bg-tertiary)",
        "color": "var(--color-text-secondary)",
        "fontFamily": "var(--font-family-body)",
        "fontSize": "11px", "fontWeight": "600",
        "textTransform": "uppercase", "letterSpacing": "0.06em",
        "border": "none", "borderBottom": "1px solid var(--color-border-primary)",
        "padding": "8px 12px",
    },
    style_cell={
        "backgroundColor": "var(--color-bg-secondary)",
        "color": "var(--color-text-primary)",
        "fontFamily": "var(--font-family-mono)",
        "fontSize": "12px", "textAlign": "right",
        "border": "none", "borderBottom": "1px solid var(--color-border-secondary)",
        "padding": "8px 12px",
    },
    style_cell_conditional=[
        {"if": {"column_id": c}, "textAlign": "left",
         "fontFamily": "var(--font-family-body)"}
        for c in ("failure_mode", "cell")
    ],
    style_data_conditional=[
        # Top-priority rows: indigo attention wash (NOT data red — discipline).
        {"if": {"filter_query": "{score} >= 18"},
         "backgroundColor": "var(--color-accent-subtle)"},
        {"if": {"filter_query": "{score} >= 12 && {score} < 18"},
         "backgroundColor": "var(--color-bg-tertiary)"},
        {"if": {"column_id": "score"}, "fontWeight": "700",
         "color": "var(--color-text-primary)"},
        {"if": {"column_id": "n"}, "color": "var(--color-text-tertiary)"},
        # Low-confidence rows (n<3): flag the count amber, like the heatmap ⚠.
        {"if": {"filter_query": "{n} < 3", "column_id": "n"},
         "color": "var(--color-status-warning)", "fontWeight": "600"},
    ],
)


def _priority_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="priority-table",
        columns=[
            {"name": "Failure mode", "id": "failure_mode"},
            {"name": "Cell", "id": "cell"},
            {"name": "FAIL %", "id": "fail_pct"},
            {"name": "n", "id": "n"},
            {"name": "Freq", "id": "frequency_tier"},
            {"name": "Impact", "id": "impact_tier"},
            {"name": "Exposure", "id": "exposure_tier"},
            {"name": "Score", "id": "score"},
        ],
        sort_action="native",
        sort_by=[{"column_id": "score", "direction": "desc"}],
        **_TABLE_STYLE,
    )


def _priority_body() -> list:
    return [
        html.Div(className="wb-tier-grids", children=[_impact_grid(), _exposure_grid()]),
        _loading(html.Div(className="wb-card wb-table-card", children=_priority_table())),
        html.Div(id="priority-rollup", className="wb-rollup"),
    ]


def _decision_mode_card(mode: str) -> html.Div:
    """Per failure mode: its §3 HYPOTHESIS echo + the your-voice layer call."""
    layer_radio = dcc.RadioItems(
        id={"type": "layer", "mode": mode},
        options=LAYER_OPTIONS, value=None, className="wb-layer-radio",
    )
    return html.Div(
        className="wb-decision-card",
        children=[
            html.H3(mode, className="wb-decision-card__mode"),
            html.Div(id={"type": "layer-hypo", "mode": mode}),  # filled by callback
            human_field("Final layer — you decide", layer_radio,
                        help="The hypothesis is the console's; the layer is yours."),
        ],
    )


def _decision_body() -> list:
    return [
        html.Div(
            className="wb-decision-cards",
            children=[_decision_mode_card(m) for m in DECISION_MODES],
        ),
        _loading(html.Div(id="decision-recommendation", className="wb-reco")),
        human_field(
            "Why we fix in this order — your rationale (required)",
            dcc.Textarea(
                id="decision-rationale", className="wb-input--area",
                placeholder=("e.g. Citation is uniform → L1 verbatim instruction, nearly "
                             "free, ship first. PHOSITA Novel cluster reads L2/L3; gate it "
                             "behind the prompt fix and re-measure before investing."),
            ),
            help="This is the audit trail — the why behind the order. Required before acting.",
        ),
        html.Span(id="decision-saved", className="wb-saved",
                  role="status", **{"aria-live": "polite"}),
    ]


# Section bodies carry the ids later tasks attach to; placeholders for now.
_SECTION_BODIES = {
    "how-bad": _loading(html.Div(id="kpi-row")),
    "where": _where_body(),
    "why": html.Div(
        id="why-body",
        children=[
            _loading(html.Div(id="shape-read")),
            human_field(
                "Your read — which architecture layer, and how confident?",
                dcc.Textarea(
                    id="why-conclusion",
                    className="wb-input--area",
                    placeholder=("e.g. Agree the rising gradient points at reasoning "
                                 "capability (L2/L3); but Implicit n is thin, so I'd "
                                 "verify before committing. Citation looks uniform → L1."),
                ),
                help=("The console offers a hypothesis from the numbers. The layer "
                      "call is yours — record it here; it carries into the Decision step."),
            ),
            html.Span(id="why-saved", className="wb-saved",
                      role="status", **{"aria-live": "polite"}),
        ],
    ),
    "priority": html.Div(id="priority-body", children=_priority_body()),
    "decision": html.Div(id="decision-body", children=_decision_body()),
}


def build_console_body() -> html.Div:
    """The console's scrolling narrative, minus the global stores/Location/theme
    toggle (the unified shell owns those)."""
    return html.Div(
        className="wb-shell wb-page",
        children=[
            _control_bar(),
            html.Div(
                className="wb-shell__body",
                children=[
                    _step_rail(),
                    html.Main(
                        className="wb-main",
                        children=[
                            _section(anchor, num, title, question, _SECTION_BODIES[anchor])
                            for anchor, num, title, question in STEPS
                        ],
                    ),
                ],
            ),
        ],
    )


# Register section callbacks against the global registry (after layout helpers exist).
from app_workbench import callbacks  # noqa: E402,F401
