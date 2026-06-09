import pandas as pd

from core.priority import frequency_tier, priority_table


def test_frequency_tier_boundaries():
    assert frequency_tier(0.83) == 3   # >=0.67
    assert frequency_tier(0.50) == 2   # 0.34-0.66
    assert frequency_tier(0.20) == 1   # <=0.33


def test_priority_table_scores_and_sorts():
    df = pd.DataFrame([
        # System x Novel: 2/2 FAIL on phosita -> tier 3
        {"claim_type": "System", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        # Method x Anticipation: 0/3 FAIL on phosita -> tier 1
        {"claim_type": "Method", "relationship": "Anticipation",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
    ])
    impact = {"Absent PHOSITA": "High", "Citation Text": "Low"}
    exposure = {("System", "Novel"): "Med", ("Method", "Anticipation"): "Med"}

    table = priority_table(df, impact_tiers=impact, exposure_tiers=exposure)

    top = table.iloc[0]
    assert top["failure_mode"] == "Absent PHOSITA"
    assert top["cell"] == "System × Novel"
    assert top["frequency_tier"] == 3
    assert top["impact_tier"] == 3       # High
    assert top["exposure_tier"] == 2     # Med
    assert top["score"] == 18            # 3*3*2
    # sorted descending: System×Novel (18) before Method×Anticipation (low)
    assert table["score"].is_monotonic_decreasing
