"""Frequency × Impact × Exposure priority scoring (Notion Steps 1 / 1b).

Frequency is computed from the eval data. Impact and Exposure are PM-supplied
domain judgments (High/Med/Low) — the dashboard never invents them.
"""
from __future__ import annotations

import pandas as pd

TIER = {"High": 3, "Med": 2, "Low": 1}
MODE_VERDICT = {"Absent PHOSITA": "phosita_verdict", "Citation Text": "citation_verdict"}


def frequency_tier(fail_rate: float) -> int:
    """Heatmap tiering: >=67% -> 3, 34-66% -> 2, <=33% -> 1."""
    if fail_rate >= 0.67:
        return 3
    if fail_rate >= 0.34:
        return 2
    return 1


def priority_table(
    df: pd.DataFrame,
    impact_tiers: dict[str, str],
    exposure_tiers: dict[tuple[str, str], str],
) -> pd.DataFrame:
    """One row per (failure mode × claim_type × relationship) cell, scored & sorted.

    Columns: failure_mode, cell, claim_type, relationship, fail_rate, n,
    frequency_tier, impact_tier, exposure_tier, score.
    """
    rows = []
    for mode, col in MODE_VERDICT.items():
        scored = df[df[col].isin(["PASS", "FAIL"])].copy()
        scored = scored[(scored["claim_type"] != "Unknown")
                        & (scored["relationship"] != "Unknown")]
        scored["fail"] = scored[col] == "FAIL"
        for (ctype, rel), series in scored.groupby(["claim_type", "relationship"])["fail"]:
            fail_rate = float(series.mean())
            n = int(series.count())
            f_tier = frequency_tier(fail_rate)
            i_tier = TIER.get(impact_tiers.get(mode, "Med"), 2)
            e_tier = TIER.get(exposure_tiers.get((ctype, rel), "Med"), 2)
            rows.append({
                "failure_mode": mode,
                "cell": f"{ctype} × {rel}",
                "claim_type": ctype,
                "relationship": rel,
                "fail_rate": fail_rate,
                "n": n,
                "frequency_tier": f_tier,
                "impact_tier": i_tier,
                "exposure_tier": e_tier,
                "score": f_tier * i_tier * e_tier,
            })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.sort_values("score", ascending=False, ignore_index=True)
