import pandas as pd

from core.diagnostics import (
    cell_fail_rates,
    dispersion_pp,
    relationship_gradient,
    evidence_note,
)


def _df(rows):
    return pd.DataFrame(rows)


def test_cell_fail_rates_excludes_low_n_from_dispersion():
    df = _df([
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
    ])
    rates = cell_fail_rates(df, "phosita")
    assert rates[("Method", "Anticipation")] == (0.0, 3)
    assert rates[("System", "Novel")] == (1.0, 3)


def test_dispersion_pp_is_max_minus_min_over_reliable_cells():
    df = _df([
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
    ])
    assert dispersion_pp(df, "phosita") == 100.0  # 0% vs 100%


def test_relationship_gradient_detects_monotonic_increase():
    rows = []
    # Anticipation 0/4, Implicit 2/4, Novel 4/4
    for v in ["PASS", "PASS", "PASS", "PASS"]:
        rows.append({"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": v})
    for v in ["PASS", "PASS", "FAIL", "FAIL"]:
        rows.append({"claim_type": "Method", "relationship": "Implicit", "phosita_verdict": v})
    for v in ["FAIL", "FAIL", "FAIL", "FAIL"]:
        rows.append({"claim_type": "Method", "relationship": "Novel", "phosita_verdict": v})
    g = relationship_gradient(_df(rows), "phosita")
    assert g.monotonic_increasing is True
    assert g.worst_relationship == "Novel"
    assert g.rates["Anticipation"] == 0.0
    assert g.rates["Novel"] == 1.0


def test_evidence_note_uniform_says_layer1():
    note = evidence_note(dispersion=10.0, gradient=None)
    assert "uniform" in note.lower()
    assert "layer-1" in note.lower() or "layer 1" in note.lower()


def test_evidence_note_gradient_says_reasoning_correlated():
    from core.diagnostics import RelationshipGradient
    g = RelationshipGradient(
        rates={"Anticipation": 0.17, "Implicit": 0.5, "Novel": 0.68},
        monotonic_increasing=True,
        worst_relationship="Novel",
    )
    note = evidence_note(dispersion=51.0, gradient=g)
    assert "reasoning" in note.lower()
    assert "novel" in note.lower()
