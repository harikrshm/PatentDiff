# Absent PHOSITA Reasoning — LLM-Judge Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a coded eval for the `absent_phosita_reasoning` failure mode that scores each trace PASS/FAIL via a single Groq `qwen/qwen3-32b` judge call, then compare verdicts against the 30-trace human ground truth.

**Architecture:** Single new module `core/phosita_eval.py` that owns the judge prompt, the Groq call, and trace-level orchestration. A thin runner script writes results to `traces/phosita_eval_full.jsonl` (idempotent cache keyed on `run_id` + `prompt_version`). A second runner reproduces the existing `eval_vs_human` confusion matrix flow for the new failure mode. One-line generalization to `core/eval_vs_human.classify_human` (add optional `failure_mode_key` parameter, default preserves existing behaviour).

**Tech Stack:** Python 3.11+, Groq Python SDK (already installed), pytest, the existing `core/eval_vs_human` helpers.

**Spec:** `docs/superpowers/specs/2026-05-27-phosita-llm-judge-design.md`

---

## File Map

**Create:**
- `core/phosita_eval.py` — module with `evaluate_trace`, `_build_judge_prompt`, `_call_judge`, `_has_novel_elements`, `PROMPT_VERSION`, `JUDGE_MODEL`.
- `scripts/run_phosita_eval.py` — CLI runner that iterates traces and writes `traces/phosita_eval_full.jsonl` with idempotent caching.
- `scripts/run_phosita_vs_human.py` — CLI runner that joins coded eval results with human annotations and writes a confusion matrix report.
- `tests/test_phosita_eval.py` — unit tests for the module.

**Modify:**
- `core/eval_vs_human.py` — add `failure_mode_key="citation_text"` argument to `classify_human` (one-line change, preserves existing behaviour).
- `tests/test_eval_vs_human.py` — add tests for the new parameter; existing tests keep passing because the default is unchanged.

**No changes:**
- `core/llm.py`, `core/models.py`, `core/citation_eval.py`, `core/report.py`, `core/annotation.py`, `core/trace_loader.py`.

---

## Task 1: Parameterize `classify_human` in `core/eval_vs_human.py`

**Files:**
- Modify: `core/eval_vs_human.py:9-13`
- Test: `tests/test_eval_vs_human.py` (append new tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_eval_vs_human.py`:

```python
def test_classify_human_with_phosita_key_positive():
    assert classify_human(["absent_phosita_reasoning"], "absent_phosita_reasoning") == 1


def test_classify_human_with_phosita_key_negative():
    assert classify_human(["citation_text"], "absent_phosita_reasoning") == 0


def test_classify_human_default_key_unchanged():
    # Default key must still be citation_text so existing callers don't break.
    assert classify_human(["citation_text"]) == 1
    assert classify_human(["absent_phosita_reasoning"]) == 0


def test_classify_human_multi_label_with_phosita_key():
    assert classify_human(
        ["citation_text", "absent_phosita_reasoning"],
        "absent_phosita_reasoning",
    ) == 1
```

- [ ] **Step 2: Run tests, verify the new ones fail**

Run from repo root:
```
pytest tests/test_eval_vs_human.py -v
```

Expected: the four new tests above FAIL with `TypeError: classify_human() takes 1 positional argument but 2 were given` (or similar). Existing tests still pass.

- [ ] **Step 3: Update `classify_human` signature**

Replace `core/eval_vs_human.py:9-13` (the entire `classify_human` function) with:

```python
def classify_human(
    failure_modes: Optional[Iterable[str]], failure_mode_key: str = "citation_text"
) -> int:
    """1 if the human tagged this trace with `failure_mode_key`, else 0."""
    if not failure_modes:
        return 0
    return 1 if failure_mode_key in failure_modes else 0
```

- [ ] **Step 4: Run tests, verify all pass**

Run:
```
pytest tests/test_eval_vs_human.py -v
```

Expected: all tests pass (old + new).

- [ ] **Step 5: Commit**

```
git add core/eval_vs_human.py tests/test_eval_vs_human.py
git commit -m "feat(eval_vs_human): parameterize classify_human failure_mode_key"
```

---

## Task 2: Stand up `core/phosita_eval.py` with constants and `_has_novel_elements`

**Files:**
- Create: `core/phosita_eval.py`
- Create: `tests/test_phosita_eval.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_phosita_eval.py` with:

```python
import json
from unittest.mock import MagicMock

import pytest

from core.phosita_eval import (
    PROMPT_VERSION,
    JUDGE_MODEL,
    _has_novel_elements,
)


def test_constants_have_expected_values():
    assert PROMPT_VERSION == "v1"
    assert JUDGE_MODEL == "qwen/qwen3-32b"


def test_has_novel_elements_true_when_one_n():
    mappings = [
        {"element_number": 1, "novelty": "Y"},
        {"element_number": 2, "novelty": "N"},
    ]
    assert _has_novel_elements(mappings) is True


def test_has_novel_elements_false_when_all_y():
    mappings = [
        {"element_number": 1, "novelty": "Y"},
        {"element_number": 2, "novelty": "Y"},
    ]
    assert _has_novel_elements(mappings) is False


def test_has_novel_elements_false_when_empty():
    assert _has_novel_elements([]) is False


def test_has_novel_elements_false_when_novelty_missing():
    # Missing novelty field is treated as not novel (don't crash, don't false-positive).
    mappings = [{"element_number": 1}]
    assert _has_novel_elements(mappings) is False
```

- [ ] **Step 2: Run tests, verify they fail**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: all fail with `ImportError: cannot import name ... from 'core.phosita_eval'` (module does not yet exist).

- [ ] **Step 3: Create `core/phosita_eval.py` with constants and helper**

Create `core/phosita_eval.py`:

```python
"""LLM-judge eval for the `absent_phosita_reasoning` failure mode.

See docs/superpowers/specs/2026-05-27-phosita-llm-judge-design.md for design.
"""
from __future__ import annotations

import json
import sys
from typing import Any

PROMPT_VERSION = "v1"
JUDGE_MODEL = "qwen/qwen3-32b"
JUDGE_TEMPERATURE = 0.2
JUDGE_MAX_TOKENS = 1024


def _has_novel_elements(element_mappings: list[dict]) -> bool:
    """True if at least one element is marked novelty='N'."""
    return any(em.get("novelty") == "N" for em in element_mappings)
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```
git add core/phosita_eval.py tests/test_phosita_eval.py
git commit -m "feat(phosita_eval): add module constants and _has_novel_elements helper"
```

---

## Task 3: Implement `_build_judge_prompt`

**Files:**
- Modify: `core/phosita_eval.py` (append function)
- Modify: `tests/test_phosita_eval.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_phosita_eval.py`:

```python
from core.phosita_eval import _build_judge_prompt


_SAMPLE_PARSED = {
    "element_mappings": [
        {
            "element_number": 1,
            "element_text": "receiving an input",
            "corresponding_text": "receiving an input",
            "novelty": "Y",
            "inventive_step": "Y",
            "verdict": "Y",
            "comment": "Found in target claim verbatim.",
        },
        {
            "element_number": 2,
            "element_text": "applying a neural network",
            "corresponding_text": "",
            "novelty": "N",
            "inventive_step": "N",
            "verdict": "N",
            "comment": "Not disclosed in target. Novel.",
        },
    ],
    "overall_opinion": "Source patent is valid because element 2 is novel.",
}


def test_build_judge_prompt_returns_system_and_user():
    system, user = _build_judge_prompt(_SAMPLE_PARSED)
    assert isinstance(system, str) and isinstance(user, str)
    assert len(system) > 0 and len(user) > 0


def test_build_judge_prompt_system_defines_pass_and_fail():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    # Both verdicts named in the rubric definition.
    assert "PASS" in system
    assert "FAIL" in system
    # Scope filter on novelty=Y elements documented.
    assert "novelty=Y" in system or "novelty = Y" in system


def test_build_judge_prompt_system_requires_json_output():
    system, _ = _build_judge_prompt(_SAMPLE_PARSED)
    assert "JSON" in system
    assert '"verdict"' in system
    assert '"comment"' in system


def test_build_judge_prompt_user_contains_overall_opinion():
    _, user = _build_judge_prompt(_SAMPLE_PARSED)
    assert "Source patent is valid because element 2 is novel." in user


def test_build_judge_prompt_user_contains_element_data():
    _, user = _build_judge_prompt(_SAMPLE_PARSED)
    # Element-level details the judge needs.
    assert "element_number" in user or "Element 1" in user or "1:" in user
    assert "Not disclosed in target. Novel." in user  # element 2's comment
    assert "novelty" in user.lower()
    assert "inventive_step" in user.lower() or "inventive step" in user.lower()


def test_build_judge_prompt_handles_missing_overall_opinion():
    parsed = {"element_mappings": _SAMPLE_PARSED["element_mappings"]}
    system, user = _build_judge_prompt(parsed)
    # Empty/missing overall_opinion should not crash; should be marked clearly.
    assert "(no overall opinion provided)" in user.lower() or "overall opinion" in user.lower()
```

- [ ] **Step 2: Run tests, verify they fail**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: the new tests FAIL with `ImportError: cannot import name '_build_judge_prompt'`.

- [ ] **Step 3: Implement `_build_judge_prompt`**

Append to `core/phosita_eval.py`:

```python
_SYSTEM_PROMPT = """You are evaluating a patent obviousness analysis. The analysis was produced
by an AI tool that assesses whether a source patent's independent claim is
invalid given a target patent (prior art). For each claim element, the tool
records novelty (Y/N) and inventive_step (Y/N), with a reasoning comment.
The tool also writes an overall_opinion on the source patent's validity.

Your job: judge whether the analysis contains genuine obviousness reasoning
grounded in the person-of-ordinary-skill-in-the-art (PSA) standard.

A PASS analysis:
- The overall_opinion explicitly engages with WHY novel elements are
  obvious or non-obvious to a PSA - it doesn't just state a conclusion.
- The obviousness claims in the overall_opinion are supported by the
  per-element comments (the elements actually contain the reasoning the
  overall_opinion claims).

A FAIL analysis (either pattern triggers FAIL):
- The overall_opinion is silent on obviousness, or asserts non-obviousness
  by default without engaging PSA reasoning ("all novel elements are
  non-obvious", "the source patent is valid because elements are novel").
- The overall_opinion claims obviousness reasoning that the element
  comments don't actually support - hand-waving disconnected from the
  per-element analysis.

Focus only on elements where novelty=N (the obviousness question only
applies to novel elements). Elements with novelty=Y are out of scope -
they're already disclosed, so obviousness doesn't matter.

Return ONLY valid JSON:
{
  "verdict": "PASS" or "FAIL",
  "comment": "1-3 sentences explaining why. Cite specific elements or quote phrases from overall_opinion to justify."
}"""


def _build_judge_prompt(parsed_output: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the judge call."""
    mappings = parsed_output.get("element_mappings") or []
    overall = parsed_output.get("overall_opinion") or "(no overall opinion provided)"

    element_lines = []
    for em in mappings:
        element_lines.append(
            f"Element {em.get('element_number')}:\n"
            f"  novelty: {em.get('novelty')}\n"
            f"  inventive_step: {em.get('inventive_step')}\n"
            f"  verdict: {em.get('verdict')}\n"
            f"  comment: {em.get('comment')}"
        )
    elements_block = "\n\n".join(element_lines) if element_lines else "(no element mappings)"

    user_prompt = (
        "ANALYSIS TO JUDGE:\n\n"
        "Element mappings:\n"
        f"{elements_block}\n\n"
        "Overall opinion:\n"
        f"{overall}"
    )
    return _SYSTEM_PROMPT, user_prompt
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add core/phosita_eval.py tests/test_phosita_eval.py
git commit -m "feat(phosita_eval): add _build_judge_prompt"
```

---

## Task 4: Implement `_call_judge` (Groq wrapper, mockable)

**Files:**
- Modify: `core/phosita_eval.py` (append)
- Modify: `tests/test_phosita_eval.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_phosita_eval.py`:

```python
from types import SimpleNamespace

from core.phosita_eval import _call_judge


def _make_mock_client(content: str):
    """Build a fake Groq-style client that returns the given string as content."""
    client = MagicMock()
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    client.chat.completions.create.return_value = response
    return client


def test_call_judge_parses_valid_json():
    client = _make_mock_client('{"verdict": "PASS", "comment": "Good reasoning."}')
    parsed, raw = _call_judge(client, "system", "user")
    assert parsed == {"verdict": "PASS", "comment": "Good reasoning."}
    assert raw == '{"verdict": "PASS", "comment": "Good reasoning."}'


def test_call_judge_raises_on_invalid_json():
    client = _make_mock_client("not json at all")
    with pytest.raises(ValueError):
        _call_judge(client, "system", "user")


def test_call_judge_passes_model_temperature_max_tokens():
    client = _make_mock_client('{"verdict": "PASS", "comment": "ok"}')
    _call_judge(client, "sys", "usr")
    call_args = client.chat.completions.create.call_args
    # Either positional or kwargs - assert via kwargs (Groq SDK uses kwargs).
    kwargs = call_args.kwargs
    assert kwargs["model"] == JUDGE_MODEL
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 1024
    assert kwargs["response_format"] == {"type": "json_object"}
    # Messages list contains the two prompts.
    msgs = kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1] == {"role": "user", "content": "usr"}
```

- [ ] **Step 2: Run tests, verify they fail**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: new tests FAIL with `ImportError: cannot import name '_call_judge'`.

- [ ] **Step 3: Implement `_call_judge`**

Append to `core/phosita_eval.py`:

```python
def _call_judge(client: Any, system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    """Call the judge model and parse JSON. Returns (parsed_dict, raw_content).

    Raises ValueError if the response is not valid JSON.
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
    return parsed, raw
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add core/phosita_eval.py tests/test_phosita_eval.py
git commit -m "feat(phosita_eval): add _call_judge wrapper"
```

---

## Task 5: Implement `evaluate_trace` orchestrator

**Files:**
- Modify: `core/phosita_eval.py` (append)
- Modify: `tests/test_phosita_eval.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_phosita_eval.py`:

```python
from core.phosita_eval import evaluate_trace


def _trace_with(parsed_output):
    return {"run_id": "test-rid", "parsed_output": parsed_output}


def test_evaluate_trace_returns_none_when_parsed_output_missing():
    assert evaluate_trace({"run_id": "x"}, MagicMock()) is None
    assert evaluate_trace({"run_id": "x", "parsed_output": None}, MagicMock()) is None


def test_evaluate_trace_pass_when_no_elements():
    trace = _trace_with({"element_mappings": [], "overall_opinion": "ok"})
    client = MagicMock()
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert "N/A" in result["comment"]
    assert "no elements" in result["comment"].lower()
    # Judge MUST NOT be called when short-circuiting.
    client.chat.completions.create.assert_not_called()


def test_evaluate_trace_pass_when_no_novel_elements():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "Y", "inventive_step": "Y",
             "verdict": "Y", "comment": "found"},
            {"element_number": 2, "novelty": "Y", "inventive_step": "Y",
             "verdict": "Y", "comment": "found"},
        ],
        "overall_opinion": "All elements disclosed in target.",
    })
    client = MagicMock()
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert "no novel elements" in result["comment"].lower()
    client.chat.completions.create.assert_not_called()


def test_evaluate_trace_calls_judge_when_novel_elements_present():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "Novel, not obvious."},
        ],
        "overall_opinion": "Element 1 is novel; source patent is valid.",
    })
    client = _make_mock_client('{"verdict": "FAIL", "comment": "No PSA reasoning."}')
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "FAIL"
    assert result["comment"] == "No PSA reasoning."
    assert result["run_id"] == "test-rid"
    assert result["eval_name"] == "absent_phosita_reasoning"
    assert result["judge_raw"] == '{"verdict": "FAIL", "comment": "No PSA reasoning."}'
    assert result["config"] == {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }
    client.chat.completions.create.assert_called_once()


def test_evaluate_trace_pass_verdict_from_judge():
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "Y",
             "verdict": "Y", "comment": "A PSA would find this obvious because..."},
        ],
        "overall_opinion": "Element 1 is novel but obvious; source patent invalid.",
    })
    client = _make_mock_client('{"verdict": "PASS", "comment": "PSA reasoning present."}')
    result = evaluate_trace(trace, client)
    assert result["verdict"] == "PASS"
    assert result["comment"] == "PSA reasoning present."
```

- [ ] **Step 2: Run tests, verify they fail**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: new tests FAIL with `ImportError: cannot import name 'evaluate_trace'`.

- [ ] **Step 3: Implement `evaluate_trace`**

Append to `core/phosita_eval.py`:

```python
def evaluate_trace(trace: dict, client: Any) -> dict | None:
    """Evaluate a single trace. Returns the verdict dict, or None on operational error."""
    run_id = trace.get("run_id")
    parsed = trace.get("parsed_output")
    if not parsed:
        print(f"phosita_eval: skipping {run_id}: no parsed_output", file=sys.stderr)
        return None

    mappings = parsed.get("element_mappings") or []
    config = {
        "judge_model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "temperature": JUDGE_TEMPERATURE,
    }

    if not mappings:
        return {
            "run_id": run_id,
            "eval_name": "absent_phosita_reasoning",
            "verdict": "PASS",
            "comment": "N/A: no elements analysed.",
            "judge_raw": "",
            "config": config,
        }

    if not _has_novel_elements(mappings):
        return {
            "run_id": run_id,
            "eval_name": "absent_phosita_reasoning",
            "verdict": "PASS",
            "comment": "N/A: no novel elements; obviousness reasoning not required.",
            "judge_raw": "",
            "config": config,
        }

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

    return {
        "run_id": run_id,
        "eval_name": "absent_phosita_reasoning",
        "verdict": verdict,
        "comment": comment,
        "judge_raw": raw,
        "config": config,
    }
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add core/phosita_eval.py tests/test_phosita_eval.py
git commit -m "feat(phosita_eval): add evaluate_trace orchestrator with short-circuits"
```

---

## Task 6: Add `evaluate_trace` error-handling tests

**Files:**
- Modify: `tests/test_phosita_eval.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_phosita_eval.py`:

```python
def test_evaluate_trace_returns_none_on_invalid_json(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    client = _make_mock_client("definitely not json")
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "test-rid" in captured.err


def test_evaluate_trace_returns_none_on_judge_exception(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network down")
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "test-rid" in captured.err
    assert "network down" in captured.err


def test_evaluate_trace_returns_none_on_invalid_verdict_string(capsys):
    trace = _trace_with({
        "element_mappings": [
            {"element_number": 1, "novelty": "N", "inventive_step": "N",
             "verdict": "N", "comment": "novel"},
        ],
        "overall_opinion": "valid",
    })
    client = _make_mock_client('{"verdict": "MAYBE", "comment": "unsure"}')
    result = evaluate_trace(trace, client)
    assert result is None
    captured = capsys.readouterr()
    assert "MAYBE" in captured.err
```

- [ ] **Step 2: Run tests, verify they pass already**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: ALL tests pass (the error-handling paths were already implemented in Task 5). If any of the three new tests fail, fix the implementation in `core/phosita_eval.py` to log to stderr and return None. The most likely failure: an assertion that the stderr message contains the run_id or the error text — adjust the format string in `evaluate_trace` to include both.

- [ ] **Step 3: Commit**

```
git add tests/test_phosita_eval.py
git commit -m "test(phosita_eval): pin error-handling behaviour"
```

---

## Task 7: Create `scripts/run_phosita_eval.py` with idempotent cache

**Files:**
- Create: `scripts/run_phosita_eval.py`
- Modify: `tests/test_phosita_eval.py` (append integration test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_phosita_eval.py`:

```python
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_traces_jsonl(path: Path, traces: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")


def test_runner_skips_traces_with_null_parsed_output(tmp_path, monkeypatch):
    """The runner must skip traces whose parsed_output is null without crashing."""
    traces_path = tmp_path / "traces.jsonl"
    out_path = tmp_path / "phosita_eval_full.jsonl"
    _write_traces_jsonl(traces_path, [
        {"run_id": "skip-1", "parsed_output": None},
        {"run_id": "skip-2"},  # no parsed_output key
    ])
    # No GROQ_API_KEY needed because no judge call happens for these short-circuits.
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-not-used")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_eval.py"),
         "--traces", str(traces_path),
         "--out", str(out_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"runner failed: {result.stderr}"
    # Output file may not exist if zero lines written - that's fine. If it exists, it's empty.
    if out_path.exists():
        assert out_path.read_text(encoding="utf-8").strip() == ""


def test_runner_short_circuits_no_novel_elements(tmp_path, monkeypatch):
    """Trace with all novelty=Y elements gets a PASS line written without judge call."""
    traces_path = tmp_path / "traces.jsonl"
    out_path = tmp_path / "phosita_eval_full.jsonl"
    _write_traces_jsonl(traces_path, [
        {
            "run_id": "all-y",
            "parsed_output": {
                "element_mappings": [
                    {"element_number": 1, "novelty": "Y", "inventive_step": "Y",
                     "verdict": "Y", "comment": "found"},
                ],
                "overall_opinion": "All disclosed.",
            },
        },
    ])
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-not-used")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_eval.py"),
         "--traces", str(traces_path),
         "--out", str(out_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"runner failed: {result.stderr}"
    lines = [json.loads(l) for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0]["run_id"] == "all-y"
    assert lines[0]["verdict"] == "PASS"
    assert lines[0]["config"]["prompt_version"] == PROMPT_VERSION


def test_runner_idempotent_cache_skips_already_evaluated(tmp_path, monkeypatch):
    """Second run with same prompt_version does not re-evaluate."""
    traces_path = tmp_path / "traces.jsonl"
    out_path = tmp_path / "phosita_eval_full.jsonl"
    _write_traces_jsonl(traces_path, [
        {
            "run_id": "all-y",
            "parsed_output": {
                "element_mappings": [
                    {"element_number": 1, "novelty": "Y", "inventive_step": "Y",
                     "verdict": "Y", "comment": "found"},
                ],
                "overall_opinion": "All disclosed.",
            },
        },
    ])
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-not-used")
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_eval.py"),
           "--traces", str(traces_path),
           "--out", str(out_path)]
    # First run.
    r1 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert r1.returncode == 0
    first_contents = out_path.read_text(encoding="utf-8")
    # Second run on the same trace + version: file unchanged.
    r2 = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert r2.returncode == 0
    assert out_path.read_text(encoding="utf-8") == first_contents
    # Stdout should report 0 newly evaluated, 1 cached.
    assert "cached" in r2.stdout.lower() or "skipped" in r2.stdout.lower()
```

- [ ] **Step 2: Run tests, verify they fail**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: the three new subprocess tests FAIL with non-zero return code or `FileNotFoundError` (script does not yet exist).

- [ ] **Step 3: Create `scripts/run_phosita_eval.py`**

Create `scripts/run_phosita_eval.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```
pytest tests/test_phosita_eval.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add scripts/run_phosita_eval.py tests/test_phosita_eval.py
git commit -m "feat(phosita_eval): add runner with idempotent cache"
```

---

## Task 8: Create `scripts/run_phosita_vs_human.py`

**Files:**
- Create: `scripts/run_phosita_vs_human.py`
- Modify: `tests/test_eval_vs_human.py` (append integration test — optional)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_eval_vs_human.py`:

```python
import json


def test_phosita_vs_human_cli_smoke(tmp_path):
    """The runner produces a report and confusion matrix from synthetic inputs."""
    # Build a synthetic phosita_eval_full.jsonl and a synthetic annotations file.
    eval_path = tmp_path / "phosita_eval_full.jsonl"
    ann_path = tmp_path / "traces_annotations.jsonl"
    report_path = tmp_path / "report.md"

    with open(eval_path, "w", encoding="utf-8") as f:
        # rid-1: coded FAIL
        f.write(json.dumps({
            "run_id": "rid-1", "verdict": "FAIL", "comment": "no reasoning",
            "config": {"prompt_version": "v1", "judge_model": "qwen/qwen3-32b", "temperature": 0.2},
        }) + "\n")
        # rid-2: coded PASS
        f.write(json.dumps({
            "run_id": "rid-2", "verdict": "PASS", "comment": "good",
            "config": {"prompt_version": "v1", "judge_model": "qwen/qwen3-32b", "temperature": 0.2},
        }) + "\n")

    with open(ann_path, "w", encoding="utf-8") as f:
        # rid-1: human tagged phosita -> TP
        f.write(json.dumps({
            "run_id": "rid-1", "source": "human", "comment": "real annotation",
            "failure_modes": ["absent_phosita_reasoning"],
        }) + "\n")
        # rid-2: human did NOT tag phosita -> TN
        f.write(json.dumps({
            "run_id": "rid-2", "source": "human", "comment": "real annotation",
            "failure_modes": ["citation_text"],
        }) + "\n")

    import subprocess, sys as _sys
    result = subprocess.run(
        [_sys.executable, str(REPO_ROOT / "scripts" / "run_phosita_vs_human.py"),
         "--eval", str(eval_path),
         "--annotations", str(ann_path),
         "--report", str(report_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"failed: {result.stderr}"
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "Confusion matrix" in text
    assert "absent_phosita_reasoning" in text
    assert "TPR" in text and "TNR" in text
```

- [ ] **Step 2: Run test, verify it fails**

Run:
```
pytest tests/test_eval_vs_human.py::test_phosita_vs_human_cli_smoke -v
```

Expected: FAIL with non-zero return code or `FileNotFoundError` (script does not exist).

- [ ] **Step 3: Create `scripts/run_phosita_vs_human.py`**

Create `scripts/run_phosita_vs_human.py`:

```python
#!/usr/bin/env python
"""Compare the absent_phosita_reasoning coded eval against human annotations.

Loads phosita_eval_full.jsonl (produced by scripts/run_phosita_eval.py) and
the human annotations from traces/traces_annotations.jsonl. Joins on run_id,
computes the confusion matrix, TPR, and TNR for the
`absent_phosita_reasoning` failure mode, and writes a markdown report.

Test rows (annotation comment starts with "Test") are excluded from the
sample, matching the convention in scripts/run_eval_vs_human.py.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.eval_vs_human import classify_coded, classify_human, confusion, tpr, tnr
from core.phosita_eval import JUDGE_MODEL, PROMPT_VERSION

DEFAULT_EVAL_PATH = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"
DEFAULT_ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"
DEFAULT_REPORT_PATH = REPO_ROOT / "traces" / "phosita_vs_human_report.md"

FAILURE_MODE_KEY = "absent_phosita_reasoning"


def load_human_annotations(path: Path) -> dict:
    annotations = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("source", "human") != "human":
                continue
            comment = row.get("comment") or ""
            if comment.startswith("Test"):
                continue
            annotations[row["run_id"]] = row
    return annotations


def load_coded_eval(path: Path) -> dict:
    coded = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # Keep only rows for the current prompt_version.
            ver = (row.get("config") or {}).get("prompt_version")
            if ver != PROMPT_VERSION:
                continue
            coded[row["run_id"]] = row
    return coded


def format_percent(value):
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def render_report(c: dict, t_pr, t_nr, sample_size: int) -> str:
    tpr_denom = c["tp"] + c["fn"]
    tnr_denom = c["tn"] + c["fp"]
    tpr_line = (
        f"- **TPR (sensitivity)** = TP / (TP + FN) = {c['tp']} / {tpr_denom} = "
        f"{format_percent(t_pr) if t_pr is not None else 'N/A (no positives in sample)'}"
    )
    tnr_line = (
        f"- **TNR (specificity)** = TN / (TN + FP) = {c['tn']} / {tnr_denom} = "
        f"{format_percent(t_nr) if t_nr is not None else 'N/A (no negatives in sample)'}"
    )
    return f"""# Absent PHOSITA Reasoning - Coded Eval vs Human Eval

**Sample:** {sample_size} human-annotated traces (`source="human"`, comment does not start with "Test", matching coded eval entry exists)
**Positive class:** human tagged `{FAILURE_MODE_KEY}`
**Coded mapping:** FAIL -> positive; PASS -> negative
**Judge model:** {JUDGE_MODEL}
**Prompt version:** {PROMPT_VERSION}

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** | {c['tp']:>14} | {c['fp']:>14} |
| **Coded negative** | {c['fn']:>14} | {c['tn']:>14} |

## Metrics

{tpr_line}
{tnr_line}
"""


def run(eval_path: Path, annotations_path: Path, report_path: Path) -> int:
    annotations = load_human_annotations(annotations_path)
    coded = load_coded_eval(eval_path)

    pairs = []
    fp_run_ids = []
    fn_run_ids = []
    missing_coded = []
    for run_id, ann in annotations.items():
        if run_id not in coded:
            missing_coded.append(run_id)
            continue
        human_label = classify_human(ann.get("failure_modes"), FAILURE_MODE_KEY)
        coded_label = classify_coded(coded[run_id]["verdict"])
        pairs.append((human_label, coded_label))
        if human_label == 0 and coded_label == 1:
            fp_run_ids.append(run_id)
        elif human_label == 1 and coded_label == 0:
            fn_run_ids.append(run_id)

    c = confusion(pairs)
    t_pr = tpr(c["tp"], c["fn"])
    t_nr = tnr(c["tn"], c["fp"])

    report = render_report(c, t_pr, t_nr, sample_size=len(pairs))
    if fp_run_ids or fn_run_ids:
        report += "\n## Disagreement run_ids (for spot-check)\n\n"
        if fp_run_ids:
            report += "**False positives (coded FAIL, human did not tag phosita):**\n"
            for rid in fp_run_ids:
                report += f"- {rid}\n"
            report += "\n"
        if fn_run_ids:
            report += "**False negatives (human tagged phosita, coded PASS):**\n"
            for rid in fn_run_ids:
                report += f"- {rid}\n"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    if missing_coded:
        print(
            f"WARNING: {len(missing_coded)} human-annotated run_ids have no coded eval entry "
            f"and were excluded from the sample.",
            file=sys.stderr,
        )
    try:
        rel = report_path.relative_to(REPO_ROOT)
    except ValueError:
        rel = report_path
    print(f"Wrote {rel}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    return run(args.eval, args.annotations, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test, verify pass**

Run:
```
pytest tests/test_eval_vs_human.py::test_phosita_vs_human_cli_smoke -v
```

Expected: pass.

- [ ] **Step 5: Run the full test suite for regressions**

Run:
```
pytest -q
```

Expected: all tests pass. Pay attention to `test_eval_vs_human.py::test_cli_smoke_runs_and_writes_report` — it must still pass (the citation_text runner is untouched and `classify_human` default behaviour is preserved).

- [ ] **Step 6: Commit**

```
git add scripts/run_phosita_vs_human.py tests/test_eval_vs_human.py
git commit -m "feat(eval_vs_human): add phosita-vs-human comparison runner"
```

---

## Task 9: End-to-end dry run against real traces

This task does not write code. It exercises the full pipeline against the real corpus to verify integration. Produces no commits unless something needs fixing.

- [ ] **Step 1: Confirm GROQ_API_KEY is set**

Run:
```
python -c "import os; print('GROQ_API_KEY set' if os.environ.get('GROQ_API_KEY') else 'NOT SET')"
```

If NOT SET, export it before continuing.

- [ ] **Step 2: Run the coded eval against `traces/traces.jsonl`**

Run from repo root:
```
python scripts/run_phosita_eval.py
```

Expected: ~5-8 min wall time. Output reports `Read N traces from traces.jsonl; evaluated N new (cached 0, skipped K with null parsed_output, 0 judge failures)`. PASS and FAIL counts both > 0. File `traces/phosita_eval_full.jsonl` exists and has one JSON line per evaluated trace.

If `judge failures > 0`, inspect stderr output to identify the cause (most likely: judge returned non-JSON). Re-run only the failed traces by deleting their lines from the output file (cache will then miss them).

- [ ] **Step 3: Run the validation vs human ground truth**

Run:
```
python scripts/run_phosita_vs_human.py
```

Expected: a markdown report is written to `traces/phosita_vs_human_report.md` and printed to stdout. Confusion matrix has non-zero entries. Sample size is close to 30 (the full human-annotated set). TPR and TNR are reported as percentages.

- [ ] **Step 4: Re-run the coded eval to confirm cache works**

Run:
```
python scripts/run_phosita_eval.py
```

Expected: `evaluated 0 new (cached N, ...)`. The output file is unchanged. Runtime is < 5 seconds.

- [ ] **Step 5: Report results to user**

Print the contents of `traces/phosita_vs_human_report.md` (the confusion matrix, TPR, TNR, and disagreement run_ids) and any judge failures from Step 2. Do not iterate on the judge prompt in this task — that decision is out of scope per the spec.

---

## Self-Review Notes

**Spec coverage check:** every "In scope" item from the spec maps to a task: `core/phosita_eval.py` (Tasks 2-6), `scripts/run_phosita_eval.py` (Task 7), one-line `classify_human` change (Task 1), unit tests (Tasks 2-6), `eval_vs_human` invocation for the new failure mode (Task 8). Out-of-scope items (re-annotation, sub-verdicts, patent text in judge input, threshold dimensions) are absent from the plan as required.

**Type consistency:** `evaluate_trace(trace, client) -> dict | None` is consistent across spec, tests, and implementation. `PROMPT_VERSION`, `JUDGE_MODEL`, `JUDGE_TEMPERATURE`, `JUDGE_MAX_TOKENS` are the same constants in every reference. `verdict` is always `"PASS" | "FAIL"` in the output contract; `"PASS"` short-circuit cases preserve this contract.

**Placeholder scan:** no TBD/TODO/"add appropriate error handling" — every test and code step contains the literal content. Tests cite real assertions; code is real Python.

**Open follow-ups (deliberately deferred, not in this plan):**
- Concurrent judge calls via `asyncio.gather` — only worth doing if the ~5-8 min sequential run becomes a friction point.
- Spot-checking the FP/FN run_ids to inform a `PROMPT_VERSION = "v2"` iteration — out of scope per spec design decision 7 ("validation is diagnostic, not gating").
