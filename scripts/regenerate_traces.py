#!/usr/bin/env python
"""Re-run the model against every input in traces/traces.jsonl using the current
build_system_prompt + build_user_prompt, and write a fresh JSONL.

Preserves the original run_id per line so post-regeneration eval results can be
diff'd against the original by run_id. The output schema matches what
tracing.logger.build_trace_record produces, except run_id is reused.

Usage:
  python scripts/regenerate_traces.py
  python scripts/regenerate_traces.py --limit 5     # smoke test
  python scripts/regenerate_traces.py --out traces/traces.post-prompt-v2.jsonl
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.llm import build_system_prompt, build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response

DEFAULT_TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "traces" / "traces.post-prompt-v2.jsonl"


def regenerate_one(trace: dict, system_prompt: str) -> dict:
    inputs = trace["inputs"]
    source = PatentInput(**inputs["source_patent"])
    target = PatentInput(**inputs["target_patent"])
    user_prompt, truncation_warnings = build_user_prompt(source, target)

    parsed_dump = None
    status = "ok"
    error = None
    llm_response = {"raw_output": "", "model": "", "tokens_input": 0, "tokens_output": 0, "latency_ms": 0}
    try:
        llm_response = call_groq(system_prompt, user_prompt)
        try:
            parsed = parse_llm_response(llm_response["raw_output"])
            parsed_dump = parsed.model_dump()
        except ValueError as parse_err:
            status = "parse_error"
            error = str(parse_err)
    except Exception as api_err:
        status = "api_error"
        error = str(api_err)

    return {
        "run_id": trace["run_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "prompt": {"system_prompt": system_prompt, "user_prompt": user_prompt},
        "llm_response": llm_response,
        "parsed_output": parsed_dump,
        "status": status,
        "error": error,
        "truncation_warnings": truncation_warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES_PATH, help="Source traces JSONL")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output JSONL")
    parser.add_argument("--limit", type=int, default=None, help="Max traces to process (smoke test)")
    parser.add_argument("--resume", action="store_true", help="Skip run_ids already present in --out")
    args = parser.parse_args()

    system_prompt = build_system_prompt()

    done_ids: set[str] = set()
    if args.resume and args.out.exists():
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                done_ids.add(json.loads(line)["run_id"])
        print(f"Resume: {len(done_ids)} run_ids already in {args.out.name}, will skip")

    out_mode = "a" if args.resume and args.out.exists() else "w"

    processed = 0
    ok = 0
    parse_err = 0
    api_err = 0

    with open(args.traces, encoding="utf-8") as src, open(args.out, out_mode, encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            trace = json.loads(line)
            if args.limit is not None and processed >= args.limit:
                break
            if trace["run_id"] in done_ids:
                continue

            print(f"[{processed + 1}] {trace['run_id'][:8]} {trace['inputs']['source_patent']['label']} -> {trace['inputs']['target_patent']['label']} ...", end=" ", flush=True)
            new_trace = regenerate_one(trace, system_prompt)
            dst.write(json.dumps(new_trace) + "\n")
            dst.flush()

            processed += 1
            if new_trace["status"] == "ok":
                ok += 1
                print("ok")
            elif new_trace["status"] == "parse_error":
                parse_err += 1
                print("PARSE_ERR")
            else:
                api_err += 1
                print(f"API_ERR ({new_trace['error'][:60]})")

    print()
    print(f"Processed {processed} traces -> {args.out}")
    print(f"  ok            : {ok}")
    print(f"  parse_error   : {parse_err}")
    print(f"  api_error     : {api_err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
