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
import json
from collections import Counter, defaultdict
from pathlib import Path

VERDICTS = ["PASS", "FAIL", "NO_CITATIONS", "MISSING"]


def load_eval(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out[d["run_id"]] = d["verdict"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--run-ids", type=Path, default=None, help="Optional: restrict comparison to run_ids in this file")
    args = parser.parse_args()

    before = load_eval(args.before)
    after = load_eval(args.after)

    if args.run_ids:
        ids = set()
        with open(args.run_ids, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ids.add(line)
        before = {k: v for k, v in before.items() if k in ids}
        after = {k: v for k, v in after.items() if k in ids}
        all_ids = ids
    else:
        all_ids = set(before) | set(after)

    matrix: Counter[tuple[str, str]] = Counter()
    buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rid in sorted(all_ids):
        b = before.get(rid, "MISSING")
        a = after.get(rid, "MISSING")
        matrix[(b, a)] += 1
        buckets[(b, a)].append(rid)

    print("Transition matrix (rows=before, cols=after, cells=count)")
    print()
    header = " " * 14 + "".join(f" {v:>14}" for v in VERDICTS)
    print(header)
    for b in VERDICTS:
        row = f"{b:14}"
        for a in VERDICTS:
            cnt = matrix[(b, a)]
            row += f" {cnt:>14}"
        print(row)
    print()

    def pass_rate(d: dict[str, str]) -> tuple[float, int, int]:
        scored = [v for v in d.values() if v in ("PASS", "FAIL")]
        pass_count = sum(1 for v in scored if v == "PASS")
        rate = pass_count / len(scored) if scored else 0.0
        return rate, pass_count, len(scored)

    rb, pb, sb = pass_rate(before)
    ra, pa, sa = pass_rate(after)
    print(f"PASS rate among scored (PASS+FAIL):")
    print(f"  before : {pb}/{sb} = {100*rb:.1f}%")
    print(f"  after  : {pa}/{sa} = {100*ra:.1f}%")
    print(f"  delta  : {100*(ra - rb):+.1f} pp")
    print()

    print("Per-bucket run_ids (first 8 each, for spot-checking):")
    for b in VERDICTS:
        for a in VERDICTS:
            ids_in_bucket = buckets[(b, a)]
            if not ids_in_bucket:
                continue
            sample = " ".join(rid[:8] for rid in ids_in_bucket[:8])
            print(f"  {b:>14} -> {a:<14} ({len(ids_in_bucket):3d}): {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
