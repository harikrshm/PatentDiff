#!/usr/bin/env python
"""Run the absent_phosita_reasoning LLM-judge eval on every trace.

Reads traces/traces.jsonl, runs core.phosita_eval.evaluate_trace_async on
traces requiring a judge call (4-way concurrent), and APPENDS results to
traces/phosita_eval_full.jsonl. Idempotent: traces already present in the
output file for the current PROMPT_VERSION are skipped.

Short-circuit traces (no elements or no novel elements) are resolved without
an API call. Only traces with novel elements hit the Groq API.

Requires GROQ_API_KEY environment variable when any trace needs a judge call.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from core.phosita_eval import (
    PROMPT_VERSION,
    evaluate_trace,
    evaluate_trace_async,
    needs_judge_call,
)

DEFAULT_TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"
CONCURRENCY = 4


def _load_cache(out_path: Path) -> set[tuple[str, str]]:
    """Return set of (run_id, prompt_version) already in out_path."""
    cache: set[tuple[str, str]] = set()
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


async def _judge_one(trace: dict, sem: asyncio.Semaphore, client) -> dict | None:
    async with sem:
        return await evaluate_trace_async(trace, client)


async def _run_async(traces_path: Path, output_path: Path) -> int:
    cache = _load_cache(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_traces: list[dict] = []
    with open(traces_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            all_traces.append(json.loads(line))

    total_lines = len(all_traces)
    cached = 0
    skipped_no_parsed = 0
    judge_failures = 0
    new_results: list[dict] = []

    short_circuit_traces: list[dict] = []
    judge_traces: list[dict] = []

    for trace in all_traces:
        rid = trace.get("run_id")
        if (rid, PROMPT_VERSION) in cache:
            cached += 1
            continue
        if not trace.get("parsed_output"):
            skipped_no_parsed += 1
            continue
        if needs_judge_call(trace):
            judge_traces.append(trace)
        else:
            short_circuit_traces.append(trace)

    for trace in short_circuit_traces:
        result = evaluate_trace(trace, None)
        if result is not None:
            result["timestamp"] = datetime.now(timezone.utc).isoformat()
            new_results.append(result)

    if judge_traces:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print(
                "ERROR: GROQ_API_KEY not set and traces require judge calls.",
                file=sys.stderr,
            )
            return 1

        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)
        sem = asyncio.Semaphore(CONCURRENCY)

        results = await asyncio.gather(
            *[_judge_one(t, sem, client) for t in judge_traces],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                print(f"phosita_eval: unexpected exception: {r}", file=sys.stderr)
                judge_failures += 1
            elif r is None:
                judge_failures += 1
            else:
                r["timestamp"] = datetime.now(timezone.utc).isoformat()
                new_results.append(r)

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


def run(traces_path: Path, output_path: Path) -> int:
    return asyncio.run(_run_async(traces_path, output_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    return run(args.traces, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
