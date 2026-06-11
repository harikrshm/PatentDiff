"""Run-eval callback must only fire on a real click — never on tab navigation.

Regression guard: client-side navigation to /eval re-inserts run-eval-btn with
n_clicks=0, which fires run_eval even under prevent_initial_call. Without a guard
that re-ran the full eval on every visit.
"""
from dash import no_update

import app_workbench.callbacks as cb


def _noop_progress(*_a, **_k):
    pass


def test_run_eval_ignores_mount_fire_nclicks_zero():
    # n_clicks == 0 is the value sent when the button is re-inserted on navigation.
    def boom(*_a, **_k):
        raise AssertionError("run_evals must not run on a mount-fire")

    orig = cb.run_evals
    cb.run_evals = boom
    try:
        out = cb.run_eval(_noop_progress, 0, "baseline", 3)
    finally:
        cb.run_evals = orig
    assert out == (no_update, no_update)


def test_run_eval_ignores_none_clicks():
    orig = cb.run_evals
    cb.run_evals = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no run"))
    try:
        out = cb.run_eval(_noop_progress, None, "baseline", 0)
    finally:
        cb.run_evals = orig
    assert out == (no_update, no_update)


def test_run_eval_runs_on_real_click():
    calls = []
    orig_run, orig_resolve = cb.run_evals, cb.resolve_set_strict
    cb.run_evals = lambda *a, **k: calls.append((a, k))
    cb.resolve_set_strict = lambda _name: object()  # non-None: a real set
    try:
        out = cb.run_eval(_noop_progress, 1, "baseline", 4)
    finally:
        cb.run_evals, cb.resolve_set_strict = orig_run, orig_resolve
    assert len(calls) == 1                 # the eval actually ran
    assert out[1] == 5                     # data-version bumped from 4 -> 5


def test_run_eval_records_history_on_real_click():
    import types

    captured = {}
    fake_set = types.SimpleNamespace(name="live",
                                     phosita_path="phosita.jsonl",
                                     citation_path="citation.jsonl")
    orig = (cb.run_evals, cb.resolve_set_strict, cb.load_verdict_map,
            cb._pass_rate, cb.append_run)
    cb.run_evals = lambda *a, **k: "ok"
    cb.resolve_set_strict = lambda _n: fake_set
    cb.load_verdict_map = lambda _p: {"r": "PASS"}
    cb._pass_rate = lambda _m: (1.0, 1, 1)
    cb.append_run = lambda recs, **k: captured.setdefault("recs", recs)
    try:
        cb.run_eval(lambda *_: None, 1, "live", 0)
    finally:
        (cb.run_evals, cb.resolve_set_strict, cb.load_verdict_map,
         cb._pass_rate, cb.append_run) = orig

    recs = captured["recs"]
    assert {r.eval_kind for r in recs} == {"phosita", "citation"}
    assert len({r.run_id for r in recs}) == 1          # one run group
    assert all(r.trace_set == "live" and r.pass_rate == 1.0 for r in recs)
