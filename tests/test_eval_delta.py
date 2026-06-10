from core.eval_delta import EvalDelta, compute_delta

BEFORE = {"r1": "FAIL", "r2": "PASS", "r3": "FAIL", "r4": "PASS"}
AFTER = {"r1": "PASS", "r2": "PASS", "r3": "FAIL", "r4": "MISSING"}


def test_transition_matrix_counts():
    d = compute_delta(BEFORE, AFTER)
    assert d.matrix[("FAIL", "PASS")] == 1     # r1 fixed
    assert d.matrix[("FAIL", "FAIL")] == 1     # r3 still failing
    assert d.matrix[("PASS", "PASS")] == 1     # r2
    assert d.matrix[("PASS", "MISSING")] == 1  # r4 dropped


def test_pass_rate_delta():
    d = compute_delta(BEFORE, AFTER)
    # before scored (PASS+FAIL): r1,r2,r3,r4 → 2/4 = 50%
    assert round(d.before_rate, 3) == 0.5
    # after scored: r1,r2,r3 → 2/3 = 66.7% (r4 MISSING not scored)
    assert round(d.after_rate, 3) == 0.667
    assert d.delta_pp > 0


def test_flipped_buckets_list_run_ids():
    d = compute_delta(BEFORE, AFTER)
    assert d.buckets[("FAIL", "PASS")] == ["r1"]


def test_run_id_filter_restricts():
    d = compute_delta(BEFORE, AFTER, run_ids={"r1"})
    assert sum(d.matrix.values()) == 1
    assert d.matrix[("FAIL", "PASS")] == 1
