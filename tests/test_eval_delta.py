from pathlib import Path

from core.eval_delta import EvalDelta, compute_delta, load_verdict_map

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


def test_load_verdict_map_missing_file_returns_empty():
    assert load_verdict_map(Path("does_not_exist_xyz.jsonl")) == {}


def test_load_verdict_map_skips_records_without_run_id_or_verdict(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_text('{"run_id":"r1","verdict":"PASS"}\n{"verdict":"FAIL"}\n{"run_id":"r2"}\n')
    assert load_verdict_map(p) == {"r1": "PASS"}


def test_load_verdict_map_filters_by_prompt_version(tmp_path):
    # Regression: a stale v2 line appended AFTER the v3 line for the same run_id
    # must NOT override v3 when a prompt_version filter is requested.
    p = tmp_path / "phosita.jsonl"
    p.write_text(
        '{"run_id":"r1","verdict":"PASS","config":{"prompt_version":"v3"}}\n'
        '{"run_id":"r1","verdict":"FAIL","config":{"prompt_version":"v2"}}\n'
        '{"run_id":"r2","verdict":"FAIL","config":{"prompt_version":"v2"}}\n'
    )
    # No filter (legacy): last-wins mixes versions -> r1 wrongly FAIL (the bug).
    assert load_verdict_map(p) == {"r1": "FAIL", "r2": "FAIL"}
    # Filtered to v3: only the v3 rows count.
    assert load_verdict_map(p, prompt_version="v3") == {"r1": "PASS"}


def test_compute_delta_empty_inputs():
    d = compute_delta({}, {})
    assert d.delta_pp == 0.0
    assert d.before_pass == 0 and d.after_pass == 0
    assert sum(d.matrix.values()) == 0
