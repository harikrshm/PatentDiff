# PHOSITA Judge v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v1 PHOSITA judge prompt with a chain-of-thought v2 that distinguishes conclusion vocabulary from genuine PSA reasoning, and rewrite the runner with async concurrency to avoid Groq rate-limit waits.

**Architecture:** `core/phosita_eval.py` gains a new system prompt (4-rule rubric, opinion-only input, `opinion_check` CoT output), `_call_judge_async`, and `evaluate_trace_async`. `scripts/run_phosita_eval.py` is rewritten to use `AsyncGroq` with 4-way `asyncio.Semaphore` concurrency; sync `evaluate_trace` is kept for unit-test compatibility.

**Tech Stack:** Python 3.13, groq SDK (`Groq` + `AsyncGroq`), pytest, asyncio, subprocess (for runner integration tests).

---

## File Map

| File | Change |
|---|---|
| `core/phosita_eval.py` | Bump `PROMPT_VERSION`, new system prompt, `_build_judge_prompt` (opinion-only), `_call_judge` validation, new `_call_judge_async`, new `evaluate_trace_async` |
| `scripts/run_phosita_eval.py` | Full async rewrite with `AsyncGroq` + `asyncio.Semaphore(4)` |
| `tests/test_phosita_eval.py` | Update stale assertions, replace one test, add 3 new tests |

---

## Task 1: Update tests for v2 — prompt content, opinion-only input, opinion_check schema

**Files:**
- Modify: `tests/test_phosita_eval.py`

These tests will fail until Task 2 implements the changes. Run them after each edit to confirm the right failures appear before implementing anything.

- [ ] **Step 1: Update `test_constants_have_expected_values`**

Change the `PROMPT_VERSION` assertion from `"v1"` to `"v2"`:

```python
def test_constants_have_expected_values():
    assert PROMPT_VERSION == "v2"
    assert JUDGE_MODEL == "qwen/qwen3-32b"
```

- [ ] **Step 2: Update `test_build_judge_prompt_system_defines_pass_and_fail`**

Remove the `novelty=Y` check (no longer in v2 system prompt). Add assertion for the CoT field name:

```python
def test_build_judge_prompt_system_defines_pass_and_fail():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    assert "PASS" in system
    assert "FAIL" in system
    assert "has_psa_argument" in system
```

- [ ] **Step 3: Update `test_build_judge_prompt_system_requires_json_output`**

Add assertion for the new `opinion_check` key documented in the system prompt:

```python
def test_build_judge_prompt_system_requires_json_output():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    assert "JSON" in system
    assert '"verdict"' in system
    assert '"comment"' in system
    assert '"opinion_check"' in system
```

- [ ] **Step 4: Replace `test_build_judge_prompt_user_contains_element_data` with an opinion-only assertion**

The old test asserts element text is present — v2 sends only the overall opinion. Delete the old test and add:

```python
def test_build_judge_prompt_user_contains_only_overall_opinion():
    _, user = _build_judge_prompt(_SAMPLE_PARSED)
    # Overall opinion must be present.
    assert "Source patent is valid because element 2 is novel." in user
    # Element-level data must NOT be present in v2.
    assert "Not disclosed in target. Novel." not in user
    assert "element_number" not in user.lower()
    assert "novelty" not in user.lower()
```

- [ ] **Step 5: Update `test_call_judge_parses_valid_json`**

The mock must now return the v2 schema (with `opinion_check`):

```python
def test_call_judge_parses_valid_json():
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": False,
            "note": "No PSA argument found.",
        },
        "verdict": "FAIL",
        "comment": "No PSA reasoning present.",
    }
    raw = json.dumps(payload)
    client = _make_mock_client(raw)
    parsed, returned_raw = _call_judge(client, "system", "user")
    assert parsed["verdict"] == "FAIL"
    assert parsed["opinion_check"]["has_psa_argument"] is False
    assert returned_raw == raw
```

- [ ] **Step 6: Add `test_call_judge_raises_when_opinion_check_missing`**

```python
def test_call_judge_raises_when_opinion_check_missing():
    # Old v1-style response without opinion_check must raise ValueError.
    client = _make_mock_client('{"verdict": "PASS", "comment": "ok"}')
    with pytest.raises(ValueError, match="opinion_check"):
        _call_judge(client, "system", "user")
```

- [ ] **Step 7: Update `test_evaluate_trace_calls_judge_when_novel_elements_present`**

Update the mock to return the v2 schema and assert judge_raw captures the full response:

```python
def test_evaluate_trace_calls_judge_when_novel_elements_present():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Novel, not obvious."},
        ],
        "overall_opinion": "Element 1 is novel; source patent is valid.",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": False,
            "note": "Just a conclusion.",
        },
        "verdict": "FAIL",
        "comment": "No PSA reasoning.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "FAIL"
    assert result["comment"] == "No PSA reasoning."
    assert result["run_id"] == "test-rid"
    assert result["eval_name"] == "absent_phosita_reasoning"
    assert result["config"] == {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }
    assert json.loads(result["judge_raw"])["opinion_check"]["has_psa_argument"] is False
    client.chat.completions.create.assert_called_once()
```

- [ ] **Step 8: Update `test_evaluate_trace_pass_verdict_from_judge`**

```python
def test_evaluate_trace_pass_verdict_from_judge():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "Y",
             "verdict": "Y", "comment": "A PSA would find this obvious because..."},
        ],
        "overall_opinion": "Element 1 is novel but obvious; source patent invalid.",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": True,
            "has_psa_argument": True,
            "note": "Explains why PSA would not combine.",
        },
        "verdict": "PASS",
        "comment": "PSA reasoning present.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert result["comment"] == "PSA reasoning present."
```

- [ ] **Step 9: Update `test_evaluate_trace_returns_none_on_invalid_verdict_string`**

Add `opinion_check` to the mock so `_call_judge` doesn't raise before the verdict check:

```python
def test_evaluate_trace_returns_none_on_invalid_verdict_string(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": False,
            "note": "x",
        },
        "verdict": "MAYBE",
        "comment": "unsure",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "MAYBE" in captured.err
```

- [ ] **Step 10: Add `test_evaluate_trace_fail_when_no_psa_argument`**

```python
def test_evaluate_trace_fail_when_no_psa_argument():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Not disclosed."},
        ],
        "overall_opinion": "Element 1 is novel and non-obvious.",
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": True,
            "has_psa_argument": False,
            "note": "'novel and non-obvious' is a conclusion, not reasoning.",
        },
        "verdict": "FAIL",
        "comment": "PSA vocabulary present but no argument given.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "FAIL"
```

- [ ] **Step 11: Add `test_evaluate_trace_pass_when_psa_argument_present`**

```python
def test_evaluate_trace_pass_when_psa_argument_present():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Not disclosed."},
        ],
        "overall_opinion": (
            "The feedback loop mechanism is entirely absent from prior art; "
            "a PSA cannot combine what does not exist."
        ),
    })
    payload = {
        "opinion_check": {
            "uses_psa_vocabulary": False,
            "has_psa_argument": True,
            "note": "Complete technical absence documented — implicit PSA argument.",
        },
        "verdict": "PASS",
        "comment": "Complete absence of mechanism is an implicit PSA argument.",
    }
    client = _make_mock_client(json.dumps(payload))
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
```

- [ ] **Step 12: Run the full test suite and confirm failures are expected**

```
pytest tests/test_phosita_eval.py -v
```

Expected: failures on `test_constants_have_expected_values`, `test_build_judge_prompt_*`, `test_call_judge_parses_valid_json`, `test_call_judge_raises_when_opinion_check_missing`, and the updated `evaluate_trace` tests. All failures should say "assertion error" or "did not raise" — not import errors or syntax errors.

---

## Task 2: Implement v2 in `core/phosita_eval.py`

**Files:**
- Modify: `core/phosita_eval.py`

Replace the entire file content. Every section is shown below.

- [ ] **Step 1: Write the new `core/phosita_eval.py`**

```python
"""LLM-judge eval for the `absent_phosita_reasoning` failure mode.

See docs/superpowers/specs/2026-05-30-phosita-judge-v2-design.md for design.
"""
from __future__ import annotations

import json
import sys
from typing import Any

PROMPT_VERSION = "v2"
JUDGE_MODEL = "qwen/qwen3-32b"
JUDGE_TEMPERATURE = 0.2
JUDGE_MAX_TOKENS = 1024


def _has_novel_elements(element_mappings: list[dict]) -> bool:
    """True if at least one element is marked novelty='N'."""
    return any(em.get("novelty") == "N" for em in element_mappings)


_SYSTEM_PROMPT = """You are evaluating a patent obviousness analysis produced by an AI tool.
The tool writes an overall_opinion on whether a source patent is valid
given a target patent (prior art).

Your job: judge whether the overall_opinion contains genuine
person-of-ordinary-skill-in-the-art (PSA) obviousness reasoning.

Rules:

1. CONCLUSION TEST — PSA vocabulary is not reasoning.
   Phrases like "non-obvious", "novel and non-obvious", "would not be
   obvious to a person of ordinary skill" are legal conclusions.
   Their presence alone does NOT make a PASS. You must find an
   argument, not just a label.

2. WHAT COUNTS AS REASONING — the opinion must engage with WHY.
   Reasoning explains: what background knowledge or capability a PSA
   has, what prior-art components a PSA would naturally combine, or
   why the specific step or combination is non-trivial given what a
   PSA knows. A one-sentence explanation grounded in the technology
   is sufficient.

3. COMPLETE-ABSENCE IMPLICIT ARGUMENT.
   When the opinion documents that specific named technical mechanisms
   are entirely absent from prior art — not merely unmatched by label,
   but architecturally foreign — that absence is itself an implicit
   PSA argument (a PSA cannot combine what does not exist). In this
   case mark has_psa_argument=true even without explicit PSA language.

4. ALL-NOVEL SHORTCUT.
   If the opinion states that every claim element is novel (no prior
   art overlap at all), obviousness is vacuous. Mark verdict PASS.

Return ONLY valid JSON in this exact shape:
{
  "opinion_check": {
    "uses_psa_vocabulary": true or false,
    "has_psa_argument": true or false,
    "note": "one sentence explaining your classification"
  },
  "verdict": "PASS" or "FAIL",
  "comment": "1-3 sentences explaining the verdict. Quote specific phrases from the overall_opinion to justify."
}

verdict must be FAIL if has_psa_argument is false.
verdict must be PASS if has_psa_argument is true."""


def _build_judge_prompt(parsed_output: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the judge call."""
    overall = parsed_output.get("overall_opinion") or "(no overall opinion provided)"
    user_prompt = f"Overall opinion:\n{overall}"
    return _SYSTEM_PROMPT, user_prompt


def _call_judge(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Call the judge model and parse JSON. Returns (parsed_dict, raw_content).

    Raises ValueError if the response is not valid JSON or opinion_check is missing.
    """
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge returned non-JSON: {raw!r}") from e
    opinion_check = parsed.get("opinion_check")
    if not isinstance(opinion_check, dict) or "has_psa_argument" not in opinion_check:
        raise ValueError(f"Judge response missing opinion_check.has_psa_argument: {raw!r}")
    return parsed, raw


async def _call_judge_async(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Async version of _call_judge for use with AsyncGroq."""
    response = await client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge returned non-JSON: {raw!r}") from e
    opinion_check = parsed.get("opinion_check")
    if not isinstance(opinion_check, dict) or "has_psa_argument" not in opinion_check:
        raise ValueError(f"Judge response missing opinion_check.has_psa_argument: {raw!r}")
    return parsed, raw


def _log_inconsistency(run_id: str, has_psa: object, verdict: str) -> None:
    print(
        f"phosita_eval: {run_id}: warning: has_psa_argument={has_psa} "
        f"inconsistent with verdict={verdict!r}; trusting verdict",
        file=sys.stderr,
    )


def _build_result(run_id: str, verdict: str, comment: str, raw: str, parsed_judge: dict) -> dict:
    config = {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }
    has_psa = parsed_judge.get("opinion_check", {}).get("has_psa_argument")
    if (has_psa is False and verdict == "PASS") or (has_psa is True and verdict == "FAIL"):
        _log_inconsistency(run_id, has_psa, verdict)
    return {
        "run_id": run_id,
        "eval_name": "absent_phosita_reasoning",
        "verdict": verdict,
        "comment": comment,
        "judge_raw": raw,
        "config": config,
    }


def _short_circuit_result(run_id: str, comment: str) -> dict:
    return {
        "run_id": run_id,
        "eval_name": "absent_phosita_reasoning",
        "verdict": "PASS",
        "comment": comment,
        "judge_raw": "",
        "config": {
            "judge_model": JUDGE_MODEL,
            "prompt_version": PROMPT_VERSION,
            "temperature": JUDGE_TEMPERATURE,
        },
    }


def evaluate_trace(trace: dict, client: Any) -> dict | None:
    """Evaluate a single trace. Returns the verdict dict, or None on operational error."""
    run_id = trace.get("run_id")
    parsed = trace.get("parsed_output")
    if not parsed:
        print(f"phosita_eval: skipping {run_id}: no parsed_output", file=sys.stderr)
        return None

    mappings = parsed.get("element_mappings") or []

    if not mappings:
        return _short_circuit_result(run_id, "N/A: no elements analysed.")

    if not _has_novel_elements(mappings):
        return _short_circuit_result(run_id, "N/A: no novel elements; obviousness reasoning not required.")

    system, user = _build_judge_prompt(parsed)
    try:
        parsed_judge, raw = _call_judge(client, system, user)
    except ValueError as e:
        print(f"phosita_eval: skipping {run_id}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"phosita_eval: skipping {run_id}: judge call failed: {e}", file=sys.stderr)
        return None

    verdict = parsed_judge.get("verdict")
    comment = parsed_judge.get("comment", "")
    if verdict not in ("PASS", "FAIL"):
        print(
            f"phosita_eval: skipping {run_id}: judge returned invalid verdict {verdict!r}",
            file=sys.stderr,
        )
        return None

    return _build_result(run_id, verdict, comment, raw, parsed_judge)


async def evaluate_trace_async(trace: dict, client: Any) -> dict | None:
    """Async version of evaluate_trace for concurrent runner use."""
    run_id = trace.get("run_id")
    parsed = trace.get("parsed_output")
    if not parsed:
        print(f"phosita_eval: skipping {run_id}: no parsed_output", file=sys.stderr)
        return None

    mappings = parsed.get("element_mappings") or []

    if not mappings:
        return _short_circuit_result(run_id, "N/A: no elements analysed.")

    if not _has_novel_elements(mappings):
        return _short_circuit_result(run_id, "N/A: no novel elements; obviousness reasoning not required.")

    system, user = _build_judge_prompt(parsed)
    try:
        parsed_judge, raw = await _call_judge_async(client, system, user)
    except ValueError as e:
        print(f"phosita_eval: skipping {run_id}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"phosita_eval: skipping {run_id}: judge call failed: {e}", file=sys.stderr)
        return None

    verdict = parsed_judge.get("verdict")
    comment = parsed_judge.get("comment", "")
    if verdict not in ("PASS", "FAIL"):
        print(
            f"phosita_eval: skipping {run_id}: judge returned invalid verdict {verdict!r}",
            file=sys.stderr,
        )
        return None

    return _build_result(run_id, verdict, comment, raw, parsed_judge)
```

- [ ] **Step 2: Run the full test suite**

```
pytest tests/test_phosita_eval.py -v
```

Expected: all tests pass. If any fail, check the error message — most likely a mock payload still using the old schema.

- [ ] **Step 3: Commit**

```
git add core/phosita_eval.py tests/test_phosita_eval.py
git commit -m "feat(phosita_eval): v2 CoT prompt — opinion-only input, opinion_check validation, async judge"
```

---

## Task 3: Rewrite `scripts/run_phosita_eval.py` with async concurrency

**Files:**
- Modify: `scripts/run_phosita_eval.py`

The existing subprocess-based runner tests exercise the runner's behavior (short-circuit pass, idempotent cache). They will pass after this rewrite without changes.

- [ ] **Step 1: Write the new `scripts/run_phosita_eval.py`**

```python
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

from core.phosita_eval import (
    PROMPT_VERSION,
    _has_novel_elements,
    evaluate_trace,
    evaluate_trace_async,
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
        mappings = (trace.get("parsed_output") or {}).get("element_mappings") or []
        if not mappings or not _has_novel_elements(mappings):
            short_circuit_traces.append(trace)
        else:
            judge_traces.append(trace)

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

        async def _one(trace: dict):
            async with sem:
                return await evaluate_trace_async(trace, client)

        results = await asyncio.gather(
            *[_one(t) for t in judge_traces], return_exceptions=True
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
```

- [ ] **Step 2: Run the runner integration tests**

```
pytest tests/test_phosita_eval.py -v -k "runner"
```

Expected: all 3 runner tests pass (`test_runner_skips_traces_with_null_parsed_output`, `test_runner_short_circuits_no_novel_elements`, `test_runner_idempotent_cache_skips_already_evaluated`).

- [ ] **Step 3: Run the full test suite one more time**

```
pytest tests/test_phosita_eval.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```
git add scripts/run_phosita_eval.py
git commit -m "feat(runner): async 4-way concurrency for phosita eval — reduces Groq rate-limit waits"
```

---

## Task 4: Run v2 eval and compare TPR/TNR

**Files:**
- Reads: `traces/traces.jsonl`, `traces/traces_annotations.jsonl`
- Writes: `traces/phosita_eval_full.jsonl` (appends v2 entries), `traces/phosita_vs_human_report.md`

- [ ] **Step 1: Run the v2 eval**

```
python scripts/run_phosita_eval.py
```

Expected output (approximate — exact counts depend on traces):
```
Read 91 traces from traces.jsonl; evaluated N new (cached M, skipped K with null parsed_output, 0 judge failures)
  PASS : ...
  FAIL : ...
Wrote traces\phosita_eval_full.jsonl
```

If you see `ERROR: GROQ_API_KEY not set`, set it first: `$env:GROQ_API_KEY = "your-key"` (PowerShell).

If you see judge failures, check stderr — common causes are rate-limit errors (retry after a minute) or JSON parse failures (check `judge_raw` in the output file for the affected `run_id`).

- [ ] **Step 2: Run the comparison report**

```
python scripts/run_phosita_vs_human.py
```

Expected: a markdown confusion matrix printed to stdout. Check `traces/phosita_vs_human_report.md`.

- [ ] **Step 3: Compare v2 metrics against v1 baseline**

v1 baseline: TPR = 33.3% (3/9), TNR = 76.2% (16/21).

| Metric | v1 | v2 |
|---|---|---|
| TPR (sensitivity) | 33.3% | _(from report)_ |
| TNR (specificity) | 76.2% | _(from report)_ |

Target: TPR > 33% without TNR < 76%. If TPR did not improve, examine the judge comments for the FN run_ids in the report (spot-check via `traces/phosita_eval_full.jsonl` filtered to `config.prompt_version == "v2"`).

- [ ] **Step 4: Commit the updated output files**

```
git add traces/phosita_eval_full.jsonl traces/phosita_vs_human_report.md
git commit -m "report(phosita_eval): v2 judge results and human comparison"
```
