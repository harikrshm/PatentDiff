"""Selectable-dimension heatmap pivot (Block 3)."""
import pandas as pd

from app_workbench.heatmap import dim_pivot


def _df():
    # 4 scored traces across claim_type x relationship
    return pd.DataFrame([
        {"claim_type": "Method", "claim_length": "Short", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        {"claim_type": "Method", "claim_length": "Long", "relationship": "Novel",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
        {"claim_type": "System", "claim_length": "Short", "relationship": "Anticipation",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        {"claim_type": "System", "claim_length": "Long", "relationship": "Unknown",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
    ])


def test_dim_pivot_arbitrary_axes_and_excludes_unknown():
    piv = dim_pivot(_df(), "phosita", row_dim="claim_type", col_dim="relationship")
    assert piv.rows == ["Method", "System"]
    assert piv.cols == ["Anticipation", "Implicit", "Novel"]
    # Method×Novel: one FAIL + one PASS -> 0.5, n=2
    mi, ni = piv.rows.index("Method"), piv.cols.index("Novel")
    assert piv.rate[mi][ni] == 0.5 and piv.n[mi][ni] == 2
    # System×Anticipation: one FAIL -> 1.0, n=1
    si, ai = piv.rows.index("System"), piv.cols.index("Anticipation")
    assert piv.rate[si][ai] == 1.0 and piv.n[si][ai] == 1
    # The Unknown-relationship row is excluded entirely.
    assert sum(sum(row) for row in piv.n) == 3


def test_dim_pivot_swaps_axes():
    piv = dim_pivot(_df(), "phosita", row_dim="claim_length", col_dim="claim_type")
    assert piv.rows == ["Short", "Long"]
    assert piv.cols == ["Method", "System"]
