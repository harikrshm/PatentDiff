# core/eval_delta.py
"""Compare two eval-verdict maps (before/after) by run_id.

A "verdict map" is {run_id: verdict} where verdict ∈ VERDICTS. Used by both
scripts/compute_eval_delta.py (CLI) and the Comparison page.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

VERDICTS = ["PASS", "FAIL", "NO_CITATIONS", "MISSING"]
Transition = Tuple[str, str]


@dataclass
class EvalDelta:
    matrix: Counter[Transition]                        # (before, after) -> count
    buckets: Dict[Transition, List[str]]              # (before, after) -> run_ids
    before_rate: float
    after_rate: float
    before_pass: int
    after_pass: int
    before_scored: int
    after_scored: int

    @property
    def delta_pp(self) -> float:
        """Change in PASS rate, in percentage points."""
        return 100.0 * (self.after_rate - self.before_rate)


def load_verdict_map(path: Path) -> Dict[str, str]:
    """Read {run_id: verdict} from an eval JSONL file (empty if missing)."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("run_id") and d.get("verdict"):
                out[d["run_id"]] = d["verdict"]
    return out


def _pass_rate(d: Dict[str, str]) -> Tuple[float, int, int]:
    scored = [v for v in d.values() if v in ("PASS", "FAIL")]
    if not scored:
        return 0.0, 0, 0
    pc = sum(v == "PASS" for v in scored)
    return pc / len(scored), pc, len(scored)


def compute_delta(before: Dict[str, str], after: Dict[str, str],
                  run_ids: Optional[Iterable[str]] = None) -> EvalDelta:
    if run_ids is not None:
        ids = set(run_ids)
        before = {k: v for k, v in before.items() if k in ids}
        after = {k: v for k, v in after.items() if k in ids}
        all_ids = ids
    else:
        all_ids = set(before) | set(after)

    matrix: Counter = Counter()
    buckets: Dict[Transition, List[str]] = defaultdict(list)
    for rid in sorted(all_ids):
        b = before.get(rid, "MISSING")
        a = after.get(rid, "MISSING")
        matrix[(b, a)] += 1
        buckets[(b, a)].append(rid)

    br, bp, before_scored = _pass_rate(before)
    ar, ap, after_scored = _pass_rate(after)
    return EvalDelta(matrix=matrix, buckets=dict(buckets),
                     before_rate=br, after_rate=ar,
                     before_pass=bp, after_pass=ap,
                     before_scored=before_scored, after_scored=after_scored)
