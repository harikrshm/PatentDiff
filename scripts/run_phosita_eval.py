#!/usr/bin/env python
"""Run the absent_phosita_reasoning LLM-judge eval on every trace.

Reads traces/traces.jsonl, runs core.phosita_eval.evaluate_trace on every
trace whose parsed_output is non-null, and APPENDS results to
traces/phosita_eval_full.jsonl. Idempotent: traces already present in the
output file for the current PROMPT_VERSION are skipped.

Requires GROQ_API_KEY environment variable for the judge call.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from groq import Groq

from core.phosita_eval import PROMPT_VERSION, evaluate_trace

DEFAULT_TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"


def _load_cache(out_path: Path) -> set[tuple[str, str]]:
    """Return set of (run_id, prompt_version) already in out_path."""
    cache = set()
    if not out_path.exists():
        return cache
    with open(out_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = row.get("run_id")
            ver = (row.get("config") or {}).get("prompt_version")
            if rid and ver:
                cache.add((rid, ver))
    return cache


def run(traces_path: Path, output_path: Path) -> int:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        # Allow short-circuit-only runs (no novel elements anywhere) by deferring
        # client creation to the first time it's actually needed.
        client = None
    else:
        client = Groq(api_key=api_key)

    cache = _load_cache(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    cached = 0
    skipped_no_parsed = 0
    new_results: list[dict] = []
    judge_failures = 0

    with open(traces_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            trace = json.loads(line)
            rid = trace.get("run_id")
            if (rid, PROMPT_VERSION) in cache:
                cached += 1
                continue
            if not trace.get("parsed_output"):
                skipped_no_parsed += 1
                continue
            # Only instantiate a real client when the first non-short-circuit trace appears.
            if client is None:
                if not os.environ.get("GROQ_API_KEY"):
                    print(
                        "ERROR: GROQ_API_KEY not set and a trace requires a judge call.",
                        file=sys.stderr,
                    )
                    return 1
                client = Groq(api_key=os.environ["GROQ_API_KEY"])
            result = evaluate_trace(trace, client)
            if result is None:
                judge_failures += 1
                continue
            result["timestamp"] = datetime.now(timezone.utc).isoformat()
            new_results.append(result)

    # Append in one shot (idempotency: if the script crashes mid-loop, no half-state).
    if new_results:
        with open(output_path, "a", encoding="utf-8") as f:
            for r in new_results:
                f.write(json.dumps(r) + "\n")

    pass_count = sum(1 for r in new_results if r["verdict"] == "PASS")
    fail_count = sum(1 for r in new_results if r["verdict"] == "FAIL")
    print(
        f"Read {total_lines} traces from {traces_path.name}; "
        f"evaluated {len(new_results)} new (cached {cached}, "
        f"skipped {skipped_no_parsed} with null parsed_output, "
        f"{judge_failures} judge failures)"
    )
    print(f"  PASS : {pass_count}")
    print(f"  FAIL : {fail_count}")
    try:
        rel = output_path.relative_to(REPO_ROOT)
    except ValueError:
        rel = output_path
    print(f"Wrote {rel}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    return run(args.traces, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
