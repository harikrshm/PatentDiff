#!/usr/bin/env python
"""Compare two citation_text eval outputs by run_id and print a transition matrix.

Usage:
  python scripts/compute_eval_delta.py \
      --before traces/citation_text_eval_full.jsonl \
      --after  traces/citation_text_eval_full.post-prompt-v2.jsonl

For each run_id present in either file, classify the verdict transition
(PASS/FAIL/NO_CITATIONS/MISSING) and emit:
  - a transition matrix (counts)
  - aggregate PASS rates among scored (PASS+FAIL) before vs after
  - top run_ids in each transition bucket (for spot-checking)
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.eval_delta import VERDICTS, compute_delta, load_verdict_map


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--run-ids", type=Path, default=None, help="Optional: restrict comparison to run_ids in this file")
    args = parser.parse_args()

    before = load_verdict_map(args.before)
    after = load_verdict_map(args.after)

    run_ids = None
    if args.run_ids:
        ids = set()
        with open(args.run_ids, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ids.add(line)
        run_ids = ids

    delta = compute_delta(before, after, run_ids=run_ids)

    print("Transition matrix (rows=before, cols=after, cells=count)")
    print()
    header = " " * 14 + "".join(f" {v:>14}" for v in VERDICTS)
    print(header)
    for b in VERDICTS:
        row = f"{b:14}"
        for a in VERDICTS:
            cnt = delta.matrix[(b, a)]
            row += f" {cnt:>14}"
        print(row)
    print()

    print(f"PASS rate among scored (PASS+FAIL):")
    print(f"  before : {delta.before_pass}/{delta.before_scored} = {100*delta.before_rate:.1f}%")
    print(f"  after  : {delta.after_pass}/{delta.after_scored} = {100*delta.after_rate:.1f}%")
    print(f"  delta  : {delta.delta_pp:+.1f} pp")
    print()

    print("Per-bucket run_ids (first 8 each, for spot-checking):")
    for b in VERDICTS:
        for a in VERDICTS:
            ids_in_bucket = delta.buckets.get((b, a), [])
            if not ids_in_bucket:
                continue
            sample = " ".join(rid[:8] for rid in ids_in_bucket[:8])
            print(f"  {b:>14} -> {a:<14} ({len(ids_in_bucket):3d}): {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
