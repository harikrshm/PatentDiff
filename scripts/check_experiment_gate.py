# scripts/check_experiment_gate.py
"""Print the Phase 2 success-gate verdict for an experiment vs a baseline.

Both trace sets are discovered by suffix (core.workbench_data.list_trace_sets),
so they must already have their suffixed eval files written. Computes overall +
targeted-segment FAIL for both evals and the per-cell heatmap deltas, then calls
core.experiment_gate.evaluate_gate. Ruler stability is passed in via --ruler-ok
(read off the *_vs_human report by the operator).

Usage:
  python scripts/check_experiment_gate.py --baseline live --after exp1-verbatim \
      --target citation --segment-claim-type Method --segment-claim-length Short --ruler-ok
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.experiment_gate import evaluate_gate
from core.workbench_data import list_trace_sets, load_merged

TRACES = REPO_ROOT / "traces"
ANN = TRACES / "traces_annotations.jsonl"


def _frame(set_name):
    sets = {x.name: x for x in list_trace_sets(TRACES)}
    if set_name not in sets:
        raise SystemExit(f"trace set {set_name!r} not found; have: {sorted(sets)}")
    return load_merged(sets[set_name], ANN)


def _fail(df, vcol, ct=None, cl=None):
    sub = df[df[vcol].isin(["PASS", "FAIL"])]
    if ct:
        sub = sub[sub["claim_type"] == ct]
    if cl:
        sub = sub[sub["claim_length"] == cl]
    n = len(sub)
    return (100.0 * (sub[vcol] == "FAIL").sum() / n) if n else 0.0


def _cell_deltas(b, a, vcol):
    out = {}
    for ct in ("Method", "System"):
        for cl in ("Short", "Long"):
            out[f"{ct}/{cl}"] = _fail(a, vcol, ct, cl) - _fail(b, vcol, ct, cl)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--baseline", required=True)
    p.add_argument("--after", required=True)
    p.add_argument("--target", required=True, choices=["phosita", "citation"])
    p.add_argument("--segment-claim-type", default=None)
    p.add_argument("--segment-claim-length", default=None)
    p.add_argument("--ruler-ok", action="store_true")
    a = p.parse_args()

    b, af = _frame(a.baseline), _frame(a.after)
    tcol = f"{a.target}_verdict"
    ocol = "phosita_verdict" if a.target == "citation" else "citation_verdict"
    ct, cl = a.segment_claim_type, a.segment_claim_length

    res = evaluate_gate(
        target_eval=a.target,
        before=_fail(b, tcol), after=_fail(af, tcol),
        segment_before=_fail(b, tcol, ct, cl), segment_after=_fail(af, tcol, ct, cl),
        other_before=_fail(b, ocol), other_after=_fail(af, ocol),
        cell_deltas_pp=_cell_deltas(b, af, tcol),
        ruler_ok=a.ruler_ok)

    print(f"GATE: {'PASS' if res.passed else 'FAIL'}")
    for r in res.reasons:
        print("  " + r)
    return 0 if res.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
