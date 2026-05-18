#!/usr/bin/env python
"""Run the citation_text coded eval on every trace and write the framework output.

Reads traces/traces.jsonl, runs core.citation_eval.evaluate_trace on every
trace with a non-null parsed_output, and writes results to
traces/citation_text_eval_full.jsonl. Traces whose parsed_output is null
(model run failed) are skipped.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.citation_eval import evaluate_trace

DEFAULT_TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "traces" / "citation_text_eval_full.jsonl"


def run(traces_path: Path, output_path: Path) -> int:
    results = []
    skipped_no_parsed = 0
    total_lines = 0
    with open(traces_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            trace = json.loads(line)
            if not trace.get("parsed_output"):
                skipped_no_parsed += 1
                continue
            result = evaluate_trace(trace)
            result["timestamp"] = datetime.now(timezone.utc).isoformat()
            results.append(result)

    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    counts = {"PASS": 0, "FAIL": 0, "NO_CITATIONS": 0}
    for r in results:
        counts[r["verdict"]] += 1
    total = len(results)
    print(f"Read {total_lines} traces from {traces_path.name}; evaluated {total} (skipped {skipped_no_parsed} with null parsed_output)")
    print(f"  PASS         : {counts['PASS']}")
    print(f"  FAIL         : {counts['FAIL']}")
    print(f"  NO_CITATIONS : {counts['NO_CITATIONS']}")
    try:
        rel = output_path.relative_to(REPO_ROOT)
    except ValueError:
        rel = output_path
    print(f"Wrote {rel}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES_PATH, help="Path to traces JSONL file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH, help="Path to write eval JSONL output")
    args = parser.parse_args()
    return run(args.traces, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
