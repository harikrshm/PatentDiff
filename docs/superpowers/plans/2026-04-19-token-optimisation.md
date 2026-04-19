# Token Optimisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add claim-aware smart truncation of specification text so PatentDiff stays within Groq's 8,000 token input limit without any visible change to the user.

**Architecture:** New `core/truncation.py` module with keyword extraction and sentence-level truncation; `build_user_prompt()` in `core/llm.py` calls truncation internally and returns `tuple[str, list[str]]`; truncation warnings are passed silently to the trace record only.

**Tech Stack:** Python 3.11+, existing project stack (no new dependencies)

---

## File Structure

| File | Change |
|------|--------|
| `core/truncation.py` | Create — `extract_keywords()` and `smart_truncate_spec()` |
| `tests/test_truncation.py` | Create — tests for both truncation functions |
| `core/llm.py` | Modify — add constants, update `build_user_prompt()` signature and body |
| `tests/test_llm.py` | Modify — update tests for new `build_user_prompt()` return type |
| `tracing/logger.py` | Modify — add `truncation_warnings` parameter and field |
| `tests/test_tracing.py` | Modify — update `build_trace_record` calls to pass `truncation_warnings` |
| `app.py` | Modify — unpack tuple from `build_user_prompt()`, pass warnings to tracer |

---

### Task 1: `core/truncation.py` — Keyword Extraction

**Files:**
- Create: `core/truncation.py`
- Create: `tests/test_truncation.py`

- [ ] **Step 1: Write failing tests for `extract_keywords`**

```python
# tests/test_truncation.py
from core.truncation import extract_keywords


def test_extract_keywords_removes_stop_words():
    claim = "A system comprising at least one computer processor"
    keywords = extract_keywords(claim)
    assert "comprising" not in keywords
    assert "least" not in keywords
    assert "system" in keywords
    assert "computer" in keywords
    assert "processor" in keywords


def test_extract_keywords_filters_short_words():
    claim = "A method for processing data using an algorithm"
    keywords = extract_keywords(claim)
    assert "for" not in keywords
    assert "an" not in keywords
    assert "method" in keywords
    assert "processing" in keywords
    assert "data" in keywords
    assert "algorithm" in keywords


def test_extract_keywords_is_case_insensitive():
    claim = "A System comprising a Processor and Memory"
    keywords = extract_keywords(claim)
    assert "system" in keywords
    assert "processor" in keywords
    assert "memory" in keywords
    # All returned keywords should be lowercase
    for kw in keywords:
        assert kw == kw.lower()


def test_extract_keywords_returns_unique():
    claim = "processor and processor and processor"
    keywords = extract_keywords(claim)
    assert isinstance(keywords, set)
    assert keywords.count("processor") if hasattr(keywords, "count") else len([k for k in keywords if k == "processor"]) == 1


def test_extract_keywords_empty_claim():
    keywords = extract_keywords("")
    assert keywords == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_truncation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.truncation'`

- [ ] **Step 3: Implement `extract_keywords`**

```python
# core/truncation.py
import re

_STOP_WORDS = {
    "a", "an", "the", "comprising", "wherein", "said", "least", "having",
    "each", "one", "at", "of", "to", "for", "with", "by", "or", "and",
    "is", "are", "that", "which", "this", "in", "on", "from", "be", "as",
    "its", "into", "based", "using", "more", "than", "not", "such", "any",
    "also", "when", "then", "than", "where", "how",
}


def extract_keywords(claim_text: str) -> set[str]:
    """Extract technical keywords from a patent claim.

    Strips stop words and short words, returns lowercase unique terms.
    """
    words = re.findall(r"[a-zA-Z]+", claim_text.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOP_WORDS}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_truncation.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/truncation.py tests/test_truncation.py
git commit -m "feat: add extract_keywords for claim-aware spec truncation"
```

---

### Task 2: `core/truncation.py` — Smart Spec Truncation

**Files:**
- Modify: `core/truncation.py`
- Modify: `tests/test_truncation.py`

- [ ] **Step 1: Write failing tests for `smart_truncate_spec`**

Add these tests to `tests/test_truncation.py`:

```python
from core.truncation import extract_keywords, smart_truncate_spec


def test_no_truncation_when_within_budget():
    spec = "The processor executes instructions. The memory stores data."
    claim = "A system comprising a processor and memory"
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=1000)
    assert was_truncated is False
    assert result == spec


def test_truncation_removes_unprotected_sentences():
    # Sentence 1: contains "processor" (keyword) — protected
    # Sentence 2: no keywords — unprotected, should be dropped
    spec = "The processor executes instructions stored in memory. The widget is used for filing purposes."
    claim = "A system comprising a processor"
    # Budget: only enough for ~10 tokens — forces truncation
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=10)
    assert was_truncated is True
    assert "processor" in result
    assert "widget" not in result


def test_protected_sentences_preserved_over_budget():
    # Two protected sentences, budget only fits one — protected ones take priority
    spec = "The processor executes instructions. The memory stores processor data. Unrelated filler text here."
    claim = "A system comprising a processor"
    # Budget fits ~8 tokens — enough for one protected sentence
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=8)
    assert was_truncated is True
    assert "processor" in result


def test_result_preserves_original_sentence_order():
    spec = "First sentence about widget. Second sentence about processor. Third about memory. Fourth about widget again."
    claim = "A method using processor and memory"
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=1000)
    # No truncation expected, order must be original
    assert was_truncated is False
    proc_idx = result.index("processor")
    mem_idx = result.index("memory")
    assert proc_idx < mem_idx


def test_no_truncation_empty_spec():
    result, was_truncated = smart_truncate_spec("", "A system comprising a processor", token_budget=100)
    assert was_truncated is False
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_truncation.py::test_no_truncation_when_within_budget -v`
Expected: FAIL — `ImportError: cannot import name 'smart_truncate_spec'`

- [ ] **Step 3: Implement `smart_truncate_spec`**

Add to `core/truncation.py` (after `extract_keywords`):

```python
def _estimate_tokens(text: str) -> int:
    """Estimate token count as word count * 1.3."""
    return int(len(text.split()) * 1.3)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '. ' and double newlines."""
    # Split on paragraph breaks first, then sentence boundaries
    parts = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # Split on '. ' but reattach the period to the preceding sentence
        chunks = paragraph.split(". ")
        for i, chunk in enumerate(chunks):
            if i < len(chunks) - 1:
                parts.append(chunk + ".")
            else:
                parts.append(chunk)
    return [p for p in parts if p.strip()]


def smart_truncate_spec(
    spec_text: str,
    claim_text: str,
    token_budget: int,
) -> tuple[str, bool]:
    """Truncate spec_text to fit within token_budget, protecting sentences
    that contain keywords from claim_text.

    Returns (truncated_text, was_truncated).
    """
    if not spec_text.strip():
        return spec_text, False

    # No truncation needed
    if _estimate_tokens(spec_text) <= token_budget:
        return spec_text, False

    keywords = extract_keywords(claim_text)
    sentences = _split_sentences(spec_text)

    # Classify sentences
    protected = set()
    for i, sentence in enumerate(sentences):
        lower = sentence.lower()
        if any(kw in lower for kw in keywords):
            protected.add(i)

    # Calculate token budget used by protected sentences
    protected_tokens = sum(
        _estimate_tokens(sentences[i]) for i in protected
    )

    # Remaining budget for unprotected sentences
    remaining_budget = token_budget - protected_tokens

    # Select which unprotected sentences to include (in order)
    included = set(protected)
    if remaining_budget > 0:
        for i, sentence in enumerate(sentences):
            if i in protected:
                continue
            cost = _estimate_tokens(sentence)
            if cost <= remaining_budget:
                included.add(i)
                remaining_budget -= cost

    # Reassemble in original document order
    result = " ".join(sentences[i] for i in sorted(included))
    return result, True
```

- [ ] **Step 4: Run all truncation tests**

Run: `python -m pytest tests/test_truncation.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/truncation.py tests/test_truncation.py
git commit -m "feat: add smart_truncate_spec with keyword-protected sentence preservation"
```

---

### Task 3: Update `core/llm.py` — Token Budget and New Return Type

**Files:**
- Modify: `core/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests for updated `build_user_prompt`**

Replace the existing `test_build_user_prompt_contains_both_patents` and `test_build_user_prompt_labels_source_and_target` in `tests/test_llm.py` with these updated versions, and add a new test for the return type:

```python
# tests/test_llm.py  — replace the two existing build_user_prompt tests and add one new test

def test_build_user_prompt_returns_tuple():
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification="Step X does something.",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification="Step Y does something else.",
    )
    result = build_user_prompt(source, target)
    assert isinstance(result, tuple)
    assert len(result) == 2
    prompt, warnings = result
    assert isinstance(prompt, str)
    assert isinstance(warnings, list)


def test_build_user_prompt_contains_both_patents():
    source = PatentInput(
        label="US-PATENT-A",
        independent_claim="A method comprising step X.",
        specification="Step X does something.",
    )
    target = PatentInput(
        label="US-PATENT-B",
        independent_claim="A method comprising step Y.",
        specification="Step Y does something else.",
    )
    prompt, warnings = build_user_prompt(source, target)
    assert "US-PATENT-A" in prompt
    assert "US-PATENT-B" in prompt
    assert "A method comprising step X." in prompt
    assert "A method comprising step Y." in prompt


def test_build_user_prompt_labels_source_and_target():
    source = PatentInput(
        label="Patent A",
        independent_claim="claim A",
        specification="spec A",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="claim B",
        specification="spec B",
    )
    prompt, warnings = build_user_prompt(source, target)
    source_idx = prompt.lower().index("source")
    target_idx = prompt.lower().index("target")
    assert source_idx < target_idx
    assert prompt.index("claim A") < prompt.index("claim B")
    assert prompt.index("spec A") < prompt.index("spec B")


def test_build_user_prompt_no_warnings_for_short_specs():
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification="Step X does something useful.",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification="Step Y does something else.",
    )
    _, warnings = build_user_prompt(source, target)
    assert warnings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL — `assert isinstance(result, tuple)` fails because `build_user_prompt` currently returns `str`

- [ ] **Step 3: Update `core/llm.py`**

Replace the entire `core/llm.py` with:

```python
# core/llm.py
import os
import time

from groq import Groq

from core.models import PatentInput
from core.truncation import smart_truncate_spec

GROQ_TOKEN_LIMIT = 8000
SYSTEM_PROMPT_TOKENS = 500
TEMPLATE_OVERHEAD_TOKENS = 150
SAFETY_BUFFER_TOKENS = 300


def _estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def build_system_prompt() -> str:
    return """You are an expert patent analyst. Your task is to assess the validity of a source patent's independent claim against a target patent (prior art).

## Workflow

1. **Parse the source patent's independent claim into individual elements.** Use claim language conventions — semicolons, line breaks, and preamble vs. body structure — to identify each discrete claim element. Number them sequentially.

2. **For each element, search the target patent's independent claim and specification** for corresponding language, concepts, or disclosure.

3. **For each element, evaluate:**
   - **Novelty:** Is this element disclosed in the target patent? If the target patent describes the same technical feature, the element is NOT novel (Y). If not found, it IS novel (N).
   - **Inventive Step:** Given the target patent's teaching, is this technical approach obvious? If obvious, mark Y. If it represents a meaningful, non-obvious technical improvement, mark N.

4. **Produce a verdict per element:**
   - "Y" = element is found in target patent AND is obvious (source patent LACKS novelty/inventive step for this element)
   - "N" = element is novel OR non-obvious (source patent HAS novelty/inventive step for this element)
   - Include a comment with step-by-step reasoning through novelty and inventive step before the verdict.

5. **Produce an overall opinion** on the source patent's validity. Focus your assessment on the **core technical advancement elements** — give less weight to routine pre-processing steps or standard output/display elements, and more weight to the main novel technical contribution. Base your overall opinion primarily on whether the key technical advancement elements are mapped as Y or N and explain your reasoning.

## Output Format

Return ONLY valid JSON matching this exact schema — no markdown fences, no extra text:

{
  "element_mappings": [
    {
      "element_number": 1,
      "element_text": "the exact text of the claim element from the source patent",
      "corresponding_text": "the corresponding text found in the target patent's claim or specification, or empty string if not found",
      "novelty": "Y or N",
      "inventive_step": "Y or N",
      "verdict": "Y or N",
      "comment": "Step-by-step reasoning: first assess novelty, then inventive step, then conclude with verdict"
    }
  ],
  "overall_opinion": "Final validity assessment focusing on the core technical advancement elements"
}"""


def build_user_prompt(
    source: PatentInput,
    target: PatentInput,
) -> tuple[str, list[str]]:
    """Build the user prompt with smart spec truncation to stay within token budget.

    Returns (prompt_string, truncation_warnings).
    truncation_warnings is empty if no truncation was needed.
    """
    claim_a_tokens = _estimate_tokens(source.independent_claim)
    claim_b_tokens = _estimate_tokens(target.independent_claim)

    available = (
        GROQ_TOKEN_LIMIT
        - SYSTEM_PROMPT_TOKENS
        - TEMPLATE_OVERHEAD_TOKENS
        - SAFETY_BUFFER_TOKENS
        - claim_a_tokens
        - claim_b_tokens
    )
    per_spec_budget = max(available // 2, 500)

    spec_a, a_truncated = smart_truncate_spec(
        source.specification, source.independent_claim, per_spec_budget
    )
    spec_b, b_truncated = smart_truncate_spec(
        target.specification, target.independent_claim, per_spec_budget
    )

    warnings = []
    if a_truncated:
        warnings.append("Patent A specification truncated")
    if b_truncated:
        warnings.append("Patent B specification truncated")

    prompt = f"""## SOURCE PATENT (Patent A) — The patent being assessed for validity

**Label:** {source.label}

**Independent Claim:**
{source.independent_claim}

**Specification Support:**
{spec_a}

---

## TARGET PATENT (Patent B) — Prior art reference

**Label:** {target.label}

**Independent Claim:**
{target.independent_claim}

**Specification Support:**
{spec_b}"""

    return prompt, warnings


def call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict:
    """Call the Groq API and return a dict with raw_output, model, token counts, and latency.

    Returns:
        {
            "raw_output": str,
            "model": str,
            "tokens_input": int,
            "tokens_output": int,
            "latency_ms": int,
        }
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    client = Groq(api_key=api_key)
    model_name = model or os.environ.get("PATENTDIFF_MODEL", "openai/gpt-oss-120b")

    start = time.time()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )
    latency_ms = int((time.time() - start) * 1000)

    choice = response.choices[0]
    usage = response.usage

    return {
        "raw_output": choice.message.content,
        "model": model_name,
        "tokens_input": usage.prompt_tokens if usage else 0,
        "tokens_output": usage.completion_tokens if usage else 0,
        "latency_ms": latency_ms,
    }
```

- [ ] **Step 4: Run all LLM tests**

Run: `python -m pytest tests/test_llm.py -v`
Expected: All 6 tests PASS (5 original + 1 new `test_build_user_prompt_returns_tuple`).

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add core/llm.py tests/test_llm.py
git commit -m "feat: update build_user_prompt to return (prompt, warnings) with token budget truncation"
```

---

### Task 4: Update `tracing/logger.py` and `app.py`

**Files:**
- Modify: `tracing/logger.py`
- Modify: `tests/test_tracing.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing test for updated `build_trace_record`**

Add this test to `tests/test_tracing.py`:

```python
def test_build_trace_record_includes_truncation_warnings():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "{}", "model": "test", "tokens_input": 10, "tokens_output": 20, "latency_ms": 100},
        parsed_output=_sample_report(),
        status="success",
        error=None,
        truncation_warnings=["Patent A specification truncated"],
    )
    assert record["truncation_warnings"] == ["Patent A specification truncated"]


def test_build_trace_record_empty_truncation_warnings():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "{}", "model": "test", "tokens_input": 10, "tokens_output": 20, "latency_ms": 100},
        parsed_output=_sample_report(),
        status="success",
        error=None,
        truncation_warnings=[],
    )
    assert record["truncation_warnings"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tracing.py::test_build_trace_record_includes_truncation_warnings -v`
Expected: FAIL — `TypeError: build_trace_record() got an unexpected keyword argument 'truncation_warnings'`

- [ ] **Step 3: Update `tracing/logger.py`**

```python
# tracing/logger.py
import uuid
from datetime import datetime, timezone

from core.models import AnalysisReport, PatentInput


def build_trace_record(
    source_patent: PatentInput,
    target_patent: PatentInput,
    system_prompt: str,
    user_prompt: str,
    llm_response: dict,
    parsed_output: AnalysisReport | None,
    status: str,
    error: str | None,
    truncation_warnings: list[str] | None = None,
) -> dict:
    return {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "source_patent": {
                "label": source_patent.label,
                "independent_claim": source_patent.independent_claim,
                "specification": source_patent.specification,
            },
            "target_patent": {
                "label": target_patent.label,
                "independent_claim": target_patent.independent_claim,
                "specification": target_patent.specification,
            },
        },
        "prompt": {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        },
        "llm_response": llm_response,
        "parsed_output": parsed_output.model_dump() if parsed_output else None,
        "status": status,
        "error": error,
        "truncation_warnings": truncation_warnings or [],
    }
```

- [ ] **Step 4: Update `app.py`**

Replace lines 41-61 of `app.py` (the prompt-building and success-path trace) with:

```python
        system_prompt = build_system_prompt()
        user_prompt, truncation_warnings = build_user_prompt(source, target)

        with st.spinner("Analyzing patents — this may take a minute..."):
            llm_response = None
            report = None
            try:
                llm_response = call_groq(system_prompt, user_prompt)
                report = parse_llm_response(llm_response["raw_output"])

                trace = build_trace_record(
                    source_patent=source,
                    target_patent=target,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    llm_response=llm_response,
                    parsed_output=report,
                    status="success",
                    error=None,
                    truncation_warnings=truncation_warnings,
                )
                append_trace(trace)

            except Exception as e:
                trace = build_trace_record(
                    source_patent=source,
                    target_patent=target,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    llm_response=llm_response or {"raw_output": "", "model": "", "tokens_input": 0, "tokens_output": 0, "latency_ms": 0},
                    parsed_output=None,
                    status="error",
                    error=str(e),
                    truncation_warnings=truncation_warnings,
                )
                append_trace(trace)
                st.error(f"Analysis failed: {e}")
                st.stop()
```

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (previous 18 + 2 new tracing tests = 20 total).

- [ ] **Step 6: Commit**

```bash
git add tracing/logger.py tests/test_tracing.py app.py
git commit -m "feat: wire truncation_warnings through tracer and app"
```

---

### Task 5: End-to-End Verification

**Files:** No changes

- [ ] **Step 1: Run full test suite one final time**

Run: `python -m pytest tests/ -v`
Expected: All 20 tests PASS.

- [ ] **Step 2: Verify project structure**

Run: `python -c "from core.truncation import extract_keywords, smart_truncate_spec; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Start the app and run a real analysis**

Run: `python -m streamlit run app.py`

Paste a long specification (multiple paragraphs) for both patents and click Analyze. Verify:
1. No 413 error
2. Results display correctly
3. `traces/traces.jsonl` contains the `truncation_warnings` field — check with:

```bash
python -c "
import json
with open('traces/traces.jsonl') as f:
    last = json.loads(f.readlines()[-1])
print('Status:', last['status'])
print('Truncation warnings:', last['truncation_warnings'])
print('Input tokens:', last['llm_response']['tokens_input'])
"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push
```
