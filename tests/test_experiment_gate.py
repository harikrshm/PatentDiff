# tests/test_experiment_gate.py
from core.experiment_gate import evaluate_gate, system_prompt_within_budget


def _gate(**kw):
    base = dict(target_eval="citation", before=54.0, after=50.0,
                segment_before=58.0, segment_after=55.0,
                other_before=46.0, other_after=46.0,
                cell_deltas_pp={"Method/Short": -5.0, "System/Long": 3.0},
                ruler_ok=True)
    base.update(kw)
    return evaluate_gate(**base)


def test_gate_passes_on_overall_target_improvement():
    assert _gate().passed                       # citation -4pp, nothing else regresses


def test_gate_passes_on_segment_threshold_when_overall_small():
    # overall only -2pp (< 3pp bar) but the targeted segment drops 10pp -> still passes
    r = _gate(after=52.0, segment_after=48.0)
    assert r.passed


def test_gate_fails_when_target_unmoved():
    r = _gate(after=53.0, segment_after=57.0)   # -1pp overall, -1pp segment
    assert not r.passed
    assert any("target" in reason.lower() for reason in r.reasons)


def test_gate_fails_when_other_eval_regresses():
    r = _gate(other_after=49.0)                  # +3pp > +2pp guardrail
    assert not r.passed
    assert any("other eval" in reason.lower() for reason in r.reasons)


def test_gate_fails_on_cell_regression():
    r = _gate(cell_deltas_pp={"System/Short": 12.0})   # > 10pp worse
    assert not r.passed
    assert any("cell" in reason.lower() for reason in r.reasons)


def test_gate_fails_when_ruler_moved():
    r = _gate(ruler_ok=False)
    assert not r.passed
    assert any("ruler" in reason.lower() for reason in r.reasons)


def test_system_prompt_within_budget_current():
    ok, n = system_prompt_within_budget()
    assert ok and n <= 1800
