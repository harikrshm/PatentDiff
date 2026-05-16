#!/usr/bin/env python
"""Run the citation_text coded eval on unannotated traces.

Reads traces/traces.jsonl and traces/traces_annotations.jsonl, runs
core.citation_eval.evaluate_trace on every trace whose run_id is not a
reviewed annotation, and writes results to traces/citation_text_eval.jsonl.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.citation_eval import evaluate_trace

TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"
OUTPUT_PATH = REPO_ROOT / "traces" / "citation_text_eval.jsonl"


def load_reviewed_run_ids() -> set[str]:
    reviewed: set[str] = set()
    if not ANNOTATIONS_PATH.exists():
        return reviewed
    with open(ANNOTATIONS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("reviewed"):
                reviewed.add(d["run_id"])
    return reviewed


def iter_eval_traces(reviewed: set[str]):
    with open(TRACES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            trace = json.loads(line)
            if trace.get("run_id") in reviewed:
                continue
            if not trace.get("parsed_output"):
                continue
            yield trace


def main() -> int:
    reviewed = load_reviewed_run_ids()
    results = []
    for trace in iter_eval_traces(reviewed):
        result = evaluate_trace(trace)
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        results.append(result)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    counts = {"PASS": 0, "FAIL": 0, "NO_CITATIONS": 0}
    for r in results:
        counts[r["verdict"]] += 1
    total = len(results)
    print(f"Evaluated {total} unannotated traces")
    print(f"  PASS         : {counts['PASS']}")
    print(f"  FAIL         : {counts['FAIL']}")
    print(f"  NO_CITATIONS : {counts['NO_CITATIONS']}")
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
