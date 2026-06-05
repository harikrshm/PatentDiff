"""Deterministic 'shape read' diagnostics for the Eval Workbench.

These functions describe the SHAPE of the failure distribution (how spread out,
whether it rises with reasoning difficulty) and emit a TEMPLATED hypothesis
string. They never return a verdict — the PM assigns the architecture layer.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MIN_RELIABLE_N = 3
REL_ORDER = ["Anticipation", "Implicit", "Novel"]
UNIFORM_THRESHOLD_PP = 25.0  # spread below this reads as "uniform"


def _verdict_col(eval_name: str) -> str:
    return "phosita_verdict" if eval_name == "phosita" else "citation_verdict"


def cell_fail_rates(df: pd.DataFrame, eval_name: str) -> dict[tuple[str, str], tuple[float, int]]:
    """FAIL rate + n per (claim_type, relationship) cell, scored traces only."""
    col = _verdict_col(eval_name)
    scored = df[df[col].isin(["PASS", "FAIL"])].copy()
    scored = scored[(scored["claim_type"] != "Unknown")
                    & (scored["relationship"] != "Unknown")]
    scored["fail"] = scored[col] == "FAIL"
    out: dict[tuple[str, str], tuple[float, int]] = {}
    grouped = scored.groupby(["claim_type", "relationship"])["fail"]
    for key, series in grouped:
        out[key] = (float(series.mean()), int(series.count()))
    return out


def dispersion_pp(df: pd.DataFrame, eval_name: str) -> float:
    """Spread (max - min, in percentage points) of FAIL rate across reliable cells."""
    rates = [r for r, n in cell_fail_rates(df, eval_name).values() if n >= MIN_RELIABLE_N]
    if len(rates) < 2:
        return 0.0
    return round((max(rates) - min(rates)) * 100, 1)


@dataclass
class RelationshipGradient:
    rates: dict[str, float]
    monotonic_increasing: bool
    worst_relationship: str | None


def relationship_gradient(df: pd.DataFrame, eval_name: str) -> RelationshipGradient:
    """FAIL rate along Anticipation -> Implicit -> Novel, and whether it rises monotonically."""
    col = _verdict_col(eval_name)
    scored = df[df[col].isin(["PASS", "FAIL"])].copy()
    scored["fail"] = scored[col] == "FAIL"
    rates: dict[str, float] = {}
    for rel in REL_ORDER:
        sub = scored[scored["relationship"] == rel]["fail"]
        if not sub.empty:
            rates[rel] = float(sub.mean())
    ordered = [rates[r] for r in REL_ORDER if r in rates]
    monotonic = len(ordered) >= 2 and all(b >= a for a, b in zip(ordered, ordered[1:]))
    worst = max(rates, key=rates.get) if rates else None
    return RelationshipGradient(rates=rates, monotonic_increasing=monotonic, worst_relationship=worst)


def evidence_note(dispersion: float, gradient: RelationshipGradient | None) -> str:
    """Templated hypothesis string. NOT a verdict."""
    if dispersion <= UNIFORM_THRESHOLD_PP:
        return (f"FAIL% spread across cells = {dispersion:.0f}pp (low) → uniform → "
                f"Layer-1 (instruction) hypothesis.")
    parts = [f"FAIL% spread across cells = {dispersion:.0f}pp (high) → clustered."]
    if gradient and gradient.monotonic_increasing and gradient.rates:
        chain = " → ".join(f"{r} {gradient.rates[r]:.0%}"
                               for r in REL_ORDER if r in gradient.rates)
        parts.append(f"Rises monotonically with reasoning difficulty ({chain}) → "
                     f"reasoning-correlated → Layer-2/3 signal; "
                     f"worst cluster: {gradient.worst_relationship}.")
    else:
        parts.append("No clean reasoning gradient → inspect which cells drive the cluster.")
    return " ".join(parts)
