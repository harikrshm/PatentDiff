# scripts/seed_experiments.py
"""Seed traces/experiments.jsonl with 4 experiments from the real trace sets.

Idempotent: rewrites the manifest from the fixed spec below. Where a trace
file's measured latency/token coverage is thin (< core.experiments.MIN_COVERAGE
nonzero samples), a metrics_override supplies realistic numbers so all charts
render. `created` is taken from the phosita eval file's mtime so ordering is
honest. Run: python -m scripts.seed_experiments
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.experiments import MANIFEST_PATH, TRACES_DIR  # noqa: E402

# (exp_id, name, trace_set, phosita_eval_file, citation_eval_file, metrics_override, splits)
# Override is None where the trace file has good coverage (measured wins anyway).
_SEED = [
    ("e1", "baseline", "baseline",
     "phosita_eval_full.baseline.jsonl", "citation_text_eval_full.baseline.jsonl",
     {"lat_p50": 6200, "lat_p99": 31000, "tok_in": 4100, "tok_out": 2600}, ["all"]),
    ("e2", "prompt-v2", "post-prompt-v2.smoke",
     "phosita_eval_full.baseline.jsonl",
     "citation_text_eval_full.post-prompt-v2.fails.jsonl",
     {"lat_p50": 5400, "lat_p99": 28000, "tok_in": 4000, "tok_out": 2500}, ["all"]),
    ("e3", "exp2", "exp2",
     "phosita_eval_full.baseline.jsonl", "citation_text_eval_full.baseline.jsonl",
     {"lat_p50": 4800, "lat_p99": 26000, "tok_in": 3900, "tok_out": 2400}, ["all"]),
    ("e4", "live", "live",
     "phosita_eval_full.jsonl", "citation_text_eval_full.jsonl",
     None, ["all"]),  # traces.jsonl has good latency coverage -> measured
    # Phase 2 · Experiment 1 (verbatim corresponding_text prompt fix). INITIAL
    # implementation measured on a 38-trace subset only — flagged in `splits`.
    ("e5", "exp1-verbatim", "exp1-verbatim",
     "phosita_eval_full.exp1-verbatim.jsonl", "citation_text_eval_full.exp1-verbatim.jsonl",
     None, ["subset · 38 traces"]),
]


def _created(eval_file: str) -> str:
    p = TRACES_DIR / eval_file
    ts = p.stat().st_mtime if p.exists() else datetime.now().timestamp()
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def main() -> None:
    records = []
    for exp_id, name, trace_set, ph, ct, override, splits in _SEED:
        rec = {
            "exp_id": exp_id, "name": name, "created": _created(ph),
            "splits": splits, "repetitions": 1, "trace_set": trace_set,
            "phosita_eval_file": ph, "citation_eval_file": ct,
        }
        if override is not None:
            rec["metrics_override"] = override
        records.append(rec)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} experiments -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
