"""Shared Plotly theme for the Eval Workbench analyst console.

Plotly figures are rendered server-side and cannot read CSS custom properties,
so the token values are mirrored here. **Keep in sync with**
``app_workbench/assets/workbench.css`` / ``.design/eval-workbench/DESIGN_TOKENS.css``.

Discipline (from the brief): the diverging ``FAIL_COLORSCALE`` is the ONLY place
the red→amber→teal data scale may appear. Categorical/chrome colors use the
indigo family, never the data scale.
"""
from __future__ import annotations

import plotly.graph_objects as go

# ── Token mirror ────────────────────────────────────────────────────────────
_LIGHT = {
    "paper": "#FFFFFF",        # --color-bg-secondary
    "plot": "#FFFFFF",
    "text": "#586374",         # --color-text-secondary
    "text_strong": "#1A2027",  # --color-text-primary
    "grid": "#E9EDF2",         # --color-border-secondary
    "axis": "#DCE1E8",         # --color-border-primary
    "cell_text_low": "#1A2027",
    "cell_text_high": "#FFFFFF",
    # FAIL-rate diverging stops (low/good → high/bad)
    "fail": ["#C8E6DF", "#86C5B6", "#EAC36A", "#DC8A52", "#C0392B"],
    # indigo chrome family for any categorical series
    "categorical": ["#4F46E5", "#6366F1", "#8B85F2", "#312E81", "#9AA5B1"],
}
_DARK = {
    "paper": "#161A21",
    "plot": "#161A21",
    "text": "#9AA5B1",
    "text_strong": "#E6EAEF",
    "grid": "#1F262E",
    "axis": "#28303A",
    "cell_text_low": "#0E1116",
    "cell_text_high": "#F4F6F8",
    "fail": ["#1E3A36", "#2F7A6E", "#C99A3E", "#CC744A", "#D6473A"],
    "categorical": ["#7C74F0", "#8B85F2", "#9A93F5", "#C7D2FE", "#9AA5B1"],
}

FONT_MONO = "IBM Plex Mono, JetBrains Mono, ui-monospace, monospace"
FONT_BODY = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"


def _stops(scale: list[str]) -> list[list]:
    """Map 5 hex stops to a Plotly colorscale at 0, .25, .5, .75, 1."""
    return [[i / (len(scale) - 1), c] for i, c in enumerate(scale)]


def fail_colorscale(dark: bool = False) -> list[list]:
    """The RESERVED FAIL-rate diverging colorscale (heatmap only)."""
    return _stops((_DARK if dark else _LIGHT)["fail"])


def cell_text_color(rate: float, dark: bool = False) -> str:
    """Legible % text color for a heatmap cell at the given FAIL rate."""
    t = _DARK if dark else _LIGHT
    # Deep red high-end needs light text; pale low/mid needs dark text.
    return t["cell_text_high"] if rate >= 0.75 else t["cell_text_low"]


def workbench_template(dark: bool = False) -> go.layout.Template:
    """Shared layout template — fonts, gridlines, margins, neutral chrome.

    Apply per-figure via ``fig.update_layout(template=workbench_template(dark))``.
    """
    t = _DARK if dark else _LIGHT
    return go.layout.Template(
        layout=dict(
            paper_bgcolor=t["paper"],
            plot_bgcolor=t["plot"],
            font=dict(family=FONT_MONO, size=12, color=t["text"]),
            title=dict(font=dict(family=FONT_BODY, size=14, color=t["text_strong"])),
            colorway=t["categorical"],
            margin=dict(l=16, r=16, t=24, b=16),  # multiples of --space-*
            xaxis=dict(
                gridcolor=t["grid"], zerolinecolor=t["grid"],
                linecolor=t["axis"], tickfont=dict(family=FONT_BODY, color=t["text"]),
                automargin=True,
            ),
            yaxis=dict(
                gridcolor=t["grid"], zerolinecolor=t["grid"],
                linecolor=t["axis"], tickfont=dict(family=FONT_BODY, color=t["text"]),
                automargin=True,
            ),
            coloraxis=dict(colorscale=_stops(t["fail"])),
            hoverlabel=dict(
                font=dict(family=FONT_MONO, size=12),
                bgcolor=t["paper"], bordercolor=t["axis"],
            ),
        )
    )
