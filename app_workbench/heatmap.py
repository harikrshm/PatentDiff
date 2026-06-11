"""§2 Where — custom themed FAIL-rate heatmap (replaces dash-pivottable).

A hand-built go.Heatmap on the fixed analyst grid (claim profile × prior-art
relationship), using the RESERVED diverging scale. The % and n are printed in
every cell (color is never the only signal); n<3 cells are flagged ⚠.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from app_workbench.theme import cell_text_color, fail_colorscale, workbench_template

PROFILE_ORDER = ["Method · Short", "Method · Long", "System · Short", "System · Long"]
REL_ORDER = ["Anticipation", "Implicit", "Novel"]
MIN_N = 3  # cells below this are low-confidence (⚠)

# Selectable heatmap dimensions (Block 3). Value order is the display order.
DIM_ORDERS = {
    "claim_type": ["Method", "System"],
    "claim_length": ["Short", "Long"],
    "relationship": ["Anticipation", "Implicit", "Novel"],
}
DIM_LABELS = {
    "claim_type": "Claim type",
    "claim_length": "Claim length",
    "relationship": "Relationship",
}


@dataclass
class Pivot:
    profiles: list[str]          # y, top→bottom as displayed
    rels: list[str]              # x
    rate: list[list[float | None]]   # FAIL rate per [profile][rel], None if empty
    n: list[list[int]]           # sample count per cell
    col_avg: dict[str, float]    # relationship → FAIL rate over all its cells
    col_n: dict[str, int]


def fail_label(df: pd.DataFrame, eval_name: str) -> pd.Series:
    """Boolean 'this trace FAILed under the chosen eval' over scored rows only."""
    if eval_name == "phosita":
        scored = df[df["phosita_verdict"].isin(["PASS", "FAIL"])]
        return scored["phosita_verdict"] == "FAIL"
    if eval_name == "citation":
        scored = df[df["citation_verdict"].isin(["PASS", "FAIL"])]
        return scored["citation_verdict"] == "FAIL"
    # either
    mask = (df["phosita_verdict"].isin(["PASS", "FAIL"])
            | df["citation_verdict"].isin(["PASS", "FAIL"]))
    scored = df[mask]
    return (scored["phosita_verdict"] == "FAIL") | (scored["citation_verdict"] == "FAIL")


def fail_pivot(df: pd.DataFrame, eval_name: str) -> Pivot:
    """Build the profile × relationship FAIL-rate pivot for known dimensions."""
    work = df.copy()
    work["profile"] = work["claim_type"] + " · " + work["claim_length"]
    work["fail"] = fail_label(df, eval_name)
    work = work.loc[work["fail"].index]  # align to scored rows
    work = work[(work["claim_type"] != "Unknown") & (work["relationship"] != "Unknown")]

    rate, n = [], []
    for prof in PROFILE_ORDER:
        rrow, nrow = [], []
        for rel in REL_ORDER:
            cell = work[(work["profile"] == prof) & (work["relationship"] == rel)]
            nrow.append(len(cell))
            rrow.append(float(cell["fail"].mean()) if len(cell) else None)
        rate.append(rrow)
        n.append(nrow)

    col_avg, col_n = {}, {}
    for rel in REL_ORDER:
        cells = work[work["relationship"] == rel]
        col_n[rel] = len(cells)
        col_avg[rel] = float(cells["fail"].mean()) if len(cells) else 0.0

    return Pivot(PROFILE_ORDER, REL_ORDER, rate, n, col_avg, col_n)


@dataclass
class DimPivot:
    rows: list[str]                  # y values (row_dim), top→bottom as displayed
    cols: list[str]                  # x values (col_dim)
    rate: list[list[float | None]]   # FAIL rate per [row][col], None if empty
    n: list[list[int]]               # sample count per cell
    col_avg: dict[str, float]        # col value → FAIL rate over its column
    col_n: dict[str, int]
    row_dim: str
    col_dim: str


def dim_pivot(df: pd.DataFrame, eval_name: str, row_dim: str, col_dim: str) -> DimPivot:
    """FAIL-rate pivot over any two dimension columns (known values only)."""
    fail = fail_label(df, eval_name)
    work = df.loc[fail.index].copy()
    work["fail"] = fail
    work = work[(work[row_dim] != "Unknown") & (work[col_dim] != "Unknown")]

    rows = [v for v in DIM_ORDERS.get(row_dim, sorted(work[row_dim].dropna().unique()))]
    cols = [v for v in DIM_ORDERS.get(col_dim, sorted(work[col_dim].dropna().unique()))]

    rate, n = [], []
    for rv in rows:
        rrow, nrow = [], []
        for cv in cols:
            cell = work[(work[row_dim] == rv) & (work[col_dim] == cv)]
            nrow.append(len(cell))
            rrow.append(float(cell["fail"].mean()) if len(cell) else None)
        rate.append(rrow)
        n.append(nrow)

    col_avg, col_n = {}, {}
    for cv in cols:
        cells = work[work[col_dim] == cv]
        col_n[cv] = len(cells)
        col_avg[cv] = float(cells["fail"].mean()) if len(cells) else 0.0

    return DimPivot(rows, cols, rate, n, col_avg, col_n, row_dim, col_dim)


def dim_heatmap_figure(piv: DimPivot, *, dark: bool = False) -> go.Figure:
    """Themed FAIL-rate heatmap over arbitrary row/col dimensions; % + n per cell."""
    y = list(reversed(piv.rows))      # Plotly draws y bottom→top
    z = list(reversed(piv.rate))
    n = list(reversed(piv.n))

    fig = go.Figure(go.Heatmap(
        z=z, x=piv.cols, y=y, zmin=0.0, zmax=1.0,
        colorscale=fail_colorscale(dark), xgap=3, ygap=3, customdata=n,
        hovertemplate="%{y} · %{x}<br>FAIL %{z:.0%}<br>n=%{customdata}<extra></extra>",
        colorbar=dict(title=dict(text="FAIL %", side="right"),
                      tickformat=".0%", thickness=10, outlinewidth=0, len=0.9),
    ))

    annotations = []
    for yi, rv in enumerate(y):
        for xi, cv in enumerate(piv.cols):
            rate = z[yi][xi]
            cnt = n[yi][xi]
            if rate is None:
                txt, color = "—", "#9AA5B1"
            else:
                flag = "  ⚠" if cnt < MIN_N else ""
                txt = f"{rate:.0%}{flag}<br>n={cnt}"
                color = cell_text_color(rate, dark)
            annotations.append(go.layout.Annotation(
                x=cv, y=rv, text=txt, showarrow=False,
                font=dict(family="IBM Plex Mono, monospace", size=12, color=color),
                align="center"))

    fig.update_layout(
        template=workbench_template(dark), annotations=annotations, height=300,
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(side="top", showgrid=False, ticks="", fixedrange=True, automargin=True),
        yaxis=dict(showgrid=False, ticks="", fixedrange=True, automargin=True),
    )
    return fig


def heatmap_figure(piv: Pivot, *, dark: bool = False) -> go.Figure:
    """Themed heatmap; % + n printed per cell with contrast-correct text color."""
    # Plotly draws y bottom→top, so reverse rows to read top→bottom as listed.
    y = list(reversed(piv.profiles))
    z = list(reversed(piv.rate))
    n = list(reversed(piv.n))

    fig = go.Figure(
        go.Heatmap(
            z=z, x=piv.rels, y=y,
            zmin=0.0, zmax=1.0,
            colorscale=fail_colorscale(dark),
            xgap=3, ygap=3,
            customdata=n,
            hovertemplate="%{y} · %{x}<br>FAIL %{z:.0%}<br>n=%{customdata}<extra></extra>",
            colorbar=dict(
                title=dict(text="FAIL %", side="right"),
                tickformat=".0%", thickness=10, outlinewidth=0, len=0.9,
            ),
        )
    )

    annotations = []
    for yi, prof in enumerate(y):
        for xi, rel in enumerate(piv.rels):
            rate = z[yi][xi]
            cnt = n[yi][xi]
            if rate is None:
                txt, color = "—", "#9AA5B1"
            else:
                flag = "  ⚠" if cnt < MIN_N else ""
                txt = f"{rate:.0%}{flag}<br>n={cnt}"
                color = cell_text_color(rate, dark)
            annotations.append(go.layout.Annotation(
                x=rel, y=prof, text=txt, showarrow=False,
                font=dict(family="IBM Plex Mono, monospace", size=12, color=color),
                align="center",
            ))

    fig.update_layout(
        template=workbench_template(dark),
        annotations=annotations,
        height=300,
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(side="top", showgrid=False, ticks="", fixedrange=True),
        yaxis=dict(showgrid=False, ticks="", fixedrange=True, automargin=True),
    )
    return fig
