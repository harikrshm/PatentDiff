"""Shared render helpers for the analyst-console workbench.

The signature motif (from the brief): the app **guides**, the PM **decides** — and
you can always tell which is which. Two visually distinct, reusable voices:

  • machine_note(...)  → HYPOTHESIS. Cool indigo, FILLED, solid rule, mono tag.
                          Deterministic/templated. Never a verdict.
  • human_field(...)   → YOUR CALL. Warm ochre, OUTLINED, dashed rule, editable.
                          Everything the PM inputs or concludes.

The hue (cool vs warm) AND the treatment (filled vs dashed-outline) both differ,
so the distinction survives grayscale — an accessibility requirement, not polish.

All styling lives in assets/workbench.css; these helpers only assign classes
(plus the occasional token via `var(--…)`). No hard-coded hex here.
"""
from __future__ import annotations

from typing import Optional

from dash import html


# ── KPI valence (data hue — used only for the FAIL/clean rule on tiles) ──────
def valence_var(rate: float, *, invert: bool = False) -> str:
    """Return the CSS data-hue token for a rate in [0,1].

    invert=True for metrics where HIGH is good (e.g. "fully clean").
    Emits `var(--data-…)` so it tracks the active theme.
    """
    r = (1.0 - rate) if invert else rate
    if r >= 0.67:
        return "var(--data-bad)"
    if r >= 0.34:
        return "var(--data-mid)"
    return "var(--data-good)"


# ── Empty state (consistent "why + what to do") ──────────────────────────────
def empty_state(title: str, detail: str) -> html.Div:
    """A calm, consistent empty/guard panel that explains why and the next step."""
    return html.Div(
        className="wb-empty",
        children=[
            html.Div("◌", className="wb-empty__icon"),
            html.Div(title, className="wb-empty__title"),
            html.Div(detail, className="wb-empty__detail wb-caption"),
        ],
    )


# ── KPI tile (§1 How bad) ────────────────────────────────────────────────────
def kpi_tile(label: str, value: str, sub: str, *,
             rate: Optional[float] = None, invert: bool = False) -> html.Div:
    """A single KPI: mono numeral, left valence rule (data hue), label + n.

    `rate` (the metric as a fraction) tints the left rule via `valence_var`;
    `invert=True` for metrics where high is good (e.g. fully-clean).
    """
    style = {"borderLeftColor": valence_var(rate, invert=invert)} if rate is not None else {}
    return html.Div(
        className="wb-kpi",
        style=style,
        children=[
            html.Div(label, className="wb-kpi__label"),
            html.Div(value, className="wb-kpi__value wb-num"),
            html.Div(sub, className="wb-kpi__sub wb-num"),
        ],
    )


# ── MACHINE voice — HYPOTHESIS ───────────────────────────────────────────────
def machine_note(text: str, *, meta: Optional[str] = None) -> html.Div:
    """A deterministic, templated machine hypothesis. Never phrased as a verdict.

    `meta` is the supporting-numbers line (e.g. dispersion + gradient), rendered
    in mono so small-n cells can be discounted at a glance.
    """
    children = [
        html.Span("HYPOTHESIS", className="wb-voice__tag"),
        html.Span(text, className="wb-voice__body"),
    ]
    if meta:
        children.append(html.Div(meta, className="wb-voice__meta wb-mono"))
    return html.Div(children, className="wb-voice wb-voice--machine")


# ── HUMAN voice — YOUR CALL ──────────────────────────────────────────────────
def human_field(
    label: str,
    control,
    *,
    tag: str = "YOUR CALL",
    help: Optional[str] = None,
) -> html.Div:
    """Wrap a PM input control in the warm, editable 'your voice' treatment.

    `control` is any Dash input (dcc.Textarea / dcc.Dropdown / dcc.RadioItems),
    so callers keep full control of ids, options, and persistence wiring.
    """
    body = [
        html.Div(
            [
                html.Span(tag, className="wb-voice__tag"),
                html.Span(label, className="wb-voice__label"),
            ],
            className="wb-voice__head",
        ),
        html.Div(control, className="wb-voice__control"),
    ]
    if help:
        body.append(html.P(help, className="wb-voice__help wb-caption"))
    return html.Div(body, className="wb-voice wb-voice--human")


# ── ⚠ assumed badge (caution = amber, not data red) ─────────────────────────
def assumed_badge(
    tooltip: str = (
        "Placeholder until the live claim_type × relationship query "
        "distribution is instrumented."
    ),
) -> html.Span:
    """Marks a domain-assumed (not measured) input. Consistent everywhere."""
    return html.Span(
        ["⚠", html.Span("assumed", className="wb-badge-assumed__text")],
        title=tooltip,
        className="wb-badge-assumed",
    )
