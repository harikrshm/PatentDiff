# PatentDiff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit-based patent claim analysis tool that uses Groq's LLM to evaluate novelty and inventive step of a source patent's claim elements against a target patent, with full tracing for eval framework development.

**Architecture:** Modular Python project — `core/` for data models, LLM prompt construction, and response parsing; `tracing/` for structured JSONL logging; `app.py` as the Streamlit UI. Single Groq API call per analysis. Every run produces a trace record.

**Tech Stack:** Python 3.11+, Streamlit, Groq Python SDK, Pydantic

---

## File Structure

| File | Responsibility |
|------|---------------|
| `core/models.py` | Pydantic models for PatentInput, AnalysisRequest, ElementMapping, AnalysisReport |
| `core/llm.py` | System/user prompt construction, Groq API call, JSON response extraction |
| `core/report.py` | Parse raw LLM JSON string into AnalysisReport model |
| `tracing/logger.py` | Build TraceRecord from inputs, prompts, LLM response, parsed output |
| `tracing/store.py` | Append TraceRecord as JSON line to traces/traces.jsonl |
| `app.py` | Streamlit UI — input form, orchestration, results display |
| `requirements.txt` | Dependencies: streamlit, groq, pydantic |
| `tests/test_models.py` | Tests for data models |
| `tests/test_report.py` | Tests for JSON parsing into AnalysisReport |
| `tests/test_tracing.py` | Tests for trace logging and JSONL storage |
| `tests/test_llm.py` | Tests for prompt construction (no live API calls) |

---

### Task 1: Project Setup and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `core/__init__.py`
- Create: `tracing/__init__.py`
- Create: `tests/__init__.py`
- Create: `traces/.gitkeep`

- [ ] **Step 1: Create requirements.txt**

```
streamlit==1.45.1
groq==0.25.0
pydantic==2.11.3
pytest==8.3.5
```

- [ ] **Step 2: Create package directories with __init__.py files**

Create empty `core/__init__.py`, `tracing/__init__.py`, `tests/__init__.py`, and `traces/.gitkeep`.

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 4: Verify installation**

Run: `python -c "import streamlit; import groq; import pydantic; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt core/__init__.py tracing/__init__.py tests/__init__.py traces/.gitkeep
git commit -m "feat: project setup with dependencies"
```

---

### Task 2: Data Models

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for data models**

```python
# tests/test_models.py
from core.models import PatentInput, AnalysisRequest, ElementMapping, AnalysisReport


def test_patent_input_creation():
    p = PatentInput(
        label="US10,123,456",
        independent_claim="A system comprising: a processor; and a memory.",
        specification="The processor executes instructions stored in memory.",
    )
    assert p.label == "US10,123,456"
    assert "processor" in p.independent_claim
    assert "processor" in p.specification


def test_analysis_request_creation():
    source = PatentInput(
        label="Patent A",
        independent_claim="A method comprising step X.",
        specification="Step X involves computing a hash.",
    )
    target = PatentInput(
        label="Patent B",
        independent_claim="A method comprising step Y.",
        specification="Step Y involves computing a checksum.",
    )
    req = AnalysisRequest(source_patent=source, target_patent=target)
    assert req.source_patent.label == "Patent A"
    assert req.target_patent.label == "Patent B"


def test_element_mapping_creation():
    em = ElementMapping(
        element_number=1,
        element_text="at least one computer processor",
        corresponding_text="a processing unit configured to execute instructions",
        novelty="Y",
        inventive_step="Y",
        verdict="Y",
        comment="Patent B discloses a processing unit that is functionally equivalent.",
    )
    assert em.element_number == 1
    assert em.novelty == "Y"
    assert em.verdict == "Y"


def test_element_mapping_verdict_novel():
    em = ElementMapping(
        element_number=2,
        element_text="a quantum entanglement module",
        corresponding_text="",
        novelty="N",
        inventive_step="N",
        verdict="N",
        comment="No corresponding disclosure found in Patent B.",
    )
    assert em.verdict == "N"
    assert em.corresponding_text == ""


def test_analysis_report_creation():
    mappings = [
        ElementMapping(
            element_number=1,
            element_text="a processor",
            corresponding_text="a CPU",
            novelty="Y",
            inventive_step="Y",
            verdict="Y",
            comment="Equivalent.",
        ),
        ElementMapping(
            element_number=2,
            element_text="a novel module",
            corresponding_text="",
            novelty="N",
            inventive_step="N",
            verdict="N",
            comment="Not found.",
        ),
    ]
    report = AnalysisReport(
        element_mappings=mappings,
        overall_opinion="Patent A's claim 1 contains a novel element (element 2) not disclosed in Patent B.",
    )
    assert len(report.element_mappings) == 2
    assert report.overall_opinion.startswith("Patent A")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.models'`

- [ ] **Step 3: Implement the models**

```python
# core/models.py
from pydantic import BaseModel


class PatentInput(BaseModel):
    label: str
    independent_claim: str
    specification: str


class AnalysisRequest(BaseModel):
    source_patent: PatentInput
    target_patent: PatentInput


class ElementMapping(BaseModel):
    element_number: int
    element_text: str
    corresponding_text: str
    novelty: str
    inventive_step: str
    verdict: str
    comment: str


class AnalysisReport(BaseModel):
    element_mappings: list[ElementMapping]
    overall_opinion: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add Pydantic data models for patent inputs and analysis outputs"
```

---

### Task 3: Report Parsing

**Files:**
- Create: `core/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write failing tests for report parsing**

```python
# tests/test_report.py
import json

from core.models import AnalysisReport
from core.report import parse_llm_response


def test_parse_valid_json():
    raw = json.dumps({
        "element_mappings": [
            {
                "element_number": 1,
                "element_text": "a processor",
                "corresponding_text": "a CPU",
                "novelty": "Y",
                "inventive_step": "Y",
                "verdict": "Y",
                "comment": "Functionally equivalent.",
            }
        ],
        "overall_opinion": "Patent A lacks novelty for this element.",
    })
    report = parse_llm_response(raw)
    assert isinstance(report, AnalysisReport)
    assert len(report.element_mappings) == 1
    assert report.element_mappings[0].verdict == "Y"
    assert report.overall_opinion == "Patent A lacks novelty for this element."


def test_parse_multiple_elements():
    raw = json.dumps({
        "element_mappings": [
            {
                "element_number": 1,
                "element_text": "element A",
                "corresponding_text": "text A",
                "novelty": "Y",
                "inventive_step": "Y",
                "verdict": "Y",
                "comment": "Found.",
            },
            {
                "element_number": 2,
                "element_text": "element B",
                "corresponding_text": "",
                "novelty": "N",
                "inventive_step": "N",
                "verdict": "N",
                "comment": "Not found.",
            },
        ],
        "overall_opinion": "Mixed results.",
    })
    report = parse_llm_response(raw)
    assert len(report.element_mappings) == 2
    assert report.element_mappings[0].verdict == "Y"
    assert report.element_mappings[1].verdict == "N"


def test_parse_json_embedded_in_markdown():
    raw = '```json\n{"element_mappings": [{"element_number": 1, "element_text": "a processor", "corresponding_text": "a CPU", "novelty": "Y", "inventive_step": "Y", "verdict": "Y", "comment": "Match."}], "overall_opinion": "Lacks novelty."}\n```'
    report = parse_llm_response(raw)
    assert isinstance(report, AnalysisReport)
    assert len(report.element_mappings) == 1


def test_parse_invalid_json_raises():
    import pytest

    with pytest.raises(ValueError, match="Failed to parse"):
        parse_llm_response("this is not json at all")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.report'`

- [ ] **Step 3: Implement report parsing**

```python
# core/report.py
import json
import re

from core.models import AnalysisReport


def parse_llm_response(raw_output: str) -> AnalysisReport:
    """Parse the raw LLM output string into an AnalysisReport.

    Handles both plain JSON and JSON wrapped in markdown code fences.
    Raises ValueError if parsing fails.
    """
    text = raw_output.strip()

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

    return AnalysisReport.model_validate(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/report.py tests/test_report.py
git commit -m "feat: add LLM response parser with markdown fence handling"
```

---

### Task 4: LLM Prompt Construction and Groq API Call

**Files:**
- Create: `core/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests for prompt construction**

```python
# tests/test_llm.py
from core.llm import build_system_prompt, build_user_prompt
from core.models import PatentInput


def test_build_system_prompt_contains_role():
    prompt = build_system_prompt()
    assert "patent" in prompt.lower()
    assert "novelty" in prompt.lower()
    assert "inventive step" in prompt.lower()


def test_build_system_prompt_contains_json_schema():
    prompt = build_system_prompt()
    assert "element_mappings" in prompt
    assert "overall_opinion" in prompt
    assert "element_number" in prompt
    assert "verdict" in prompt


def test_build_system_prompt_contains_weighting_guidance():
    prompt = build_system_prompt()
    assert "technical advancement" in prompt.lower() or "technical improvement" in prompt.lower()


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
    prompt = build_user_prompt(source, target)
    assert "US-PATENT-A" in prompt
    assert "US-PATENT-B" in prompt
    assert "A method comprising step X." in prompt
    assert "A method comprising step Y." in prompt
    assert "Step X does something." in prompt
    assert "Step Y does something else." in prompt


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
    prompt = build_user_prompt(source, target)
    # Should clearly label which is source and which is target
    assert "source" in prompt.lower() or "patent a" in prompt.lower()
    assert "target" in prompt.lower() or "patent b" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.llm'`

- [ ] **Step 3: Implement prompt construction and Groq API call**

```python
# core/llm.py
import json
import os
import time

from groq import Groq

from core.models import PatentInput


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


def build_user_prompt(source: PatentInput, target: PatentInput) -> str:
    return f"""## SOURCE PATENT (Patent A) — The patent being assessed for validity

**Label:** {source.label}

**Independent Claim:**
{source.independent_claim}

**Specification Support:**
{source.specification}

---

## TARGET PATENT (Patent B) — Prior art reference

**Label:** {target.label}

**Independent Claim:**
{target.independent_claim}

**Specification Support:**
{target.specification}"""


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
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model_name = model or os.environ.get("PATENTDIFF_MODEL", "deepseek-r1-distill-llama-70b")

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/llm.py tests/test_llm.py
git commit -m "feat: add LLM prompt construction and Groq API call"
```

---

### Task 5: Tracing — Logger and JSONL Store

**Files:**
- Create: `tracing/logger.py`
- Create: `tracing/store.py`
- Create: `tests/test_tracing.py`

- [ ] **Step 1: Write failing tests for tracing**

```python
# tests/test_tracing.py
import json
import os
import tempfile

from core.models import AnalysisReport, ElementMapping, PatentInput
from tracing.logger import build_trace_record
from tracing.store import append_trace


def _sample_inputs():
    return {
        "source_patent": PatentInput(
            label="Patent A",
            independent_claim="A method comprising step X.",
            specification="Step X does something.",
        ),
        "target_patent": PatentInput(
            label="Patent B",
            independent_claim="A method comprising step Y.",
            specification="Step Y does something else.",
        ),
    }


def _sample_report():
    return AnalysisReport(
        element_mappings=[
            ElementMapping(
                element_number=1,
                element_text="step X",
                corresponding_text="step Y",
                novelty="Y",
                inventive_step="N",
                verdict="N",
                comment="Novel technical improvement.",
            )
        ],
        overall_opinion="Patent A has inventive step.",
    )


def test_build_trace_record_success():
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
    )
    assert record["status"] == "success"
    assert record["run_id"] is not None
    assert record["timestamp"] is not None
    assert record["inputs"]["source_patent"]["label"] == "Patent A"
    assert record["prompt"]["system_prompt"] == "sys"
    assert record["llm_response"]["model"] == "test"
    assert record["parsed_output"]["overall_opinion"] == "Patent A has inventive step."
    assert record["error"] is None


def test_build_trace_record_error():
    inputs = _sample_inputs()
    record = build_trace_record(
        source_patent=inputs["source_patent"],
        target_patent=inputs["target_patent"],
        system_prompt="sys",
        user_prompt="usr",
        llm_response={"raw_output": "broken", "model": "test", "tokens_input": 10, "tokens_output": 0, "latency_ms": 50},
        parsed_output=None,
        status="error",
        error="JSON parse failed",
    )
    assert record["status"] == "error"
    assert record["error"] == "JSON parse failed"
    assert record["parsed_output"] is None


def test_append_trace_creates_file_and_appends():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "traces.jsonl")
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
        )
        append_trace(record, filepath)
        append_trace(record, filepath)

        with open(filepath, "r") as f:
            lines = f.readlines()
        assert len(lines) == 2
        parsed = json.loads(lines[0])
        assert parsed["status"] == "success"
        assert parsed["inputs"]["source_patent"]["label"] == "Patent A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tracing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tracing.logger'`

- [ ] **Step 3: Implement the trace logger**

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
) -> dict:
    return {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "source_patent": {
                "label": source_patent.label,
                "claim": source_patent.independent_claim,
                "specification": source_patent.specification,
            },
            "target_patent": {
                "label": target_patent.label,
                "claim": target_patent.independent_claim,
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
    }
```

- [ ] **Step 4: Implement the JSONL store**

```python
# tracing/store.py
import json
import os


def append_trace(record: dict, filepath: str = "traces/traces.jsonl") -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "a") as f:
        f.write(json.dumps(record) + "\n")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_tracing.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tracing/logger.py tracing/store.py tests/test_tracing.py
git commit -m "feat: add trace logger and JSONL store for eval framework"
```

---

### Task 6: Streamlit UI

**Files:**
- Create: `app.py`

- [ ] **Step 1: Implement the Streamlit app**

```python
# app.py
import streamlit as st
import pandas as pd

from core.llm import build_system_prompt, build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response
from tracing.logger import build_trace_record
from tracing.store import append_trace

st.set_page_config(page_title="PatentDiff", layout="wide")
st.title("PatentDiff — Patent Claim Analysis")

# --- Input Area ---
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Patent A (Source)")
    label_a = st.text_input("Label", key="label_a", placeholder="e.g., US10,123,456")
    claim_a = st.text_area("Independent Claim", key="claim_a", height=200)
    spec_a = st.text_area("Specification Support", key="spec_a", height=200)

with col_b:
    st.subheader("Patent B (Target / Prior Art)")
    label_b = st.text_input("Label", key="label_b", placeholder="e.g., US9,876,543")
    claim_b = st.text_area("Independent Claim", key="claim_b", height=200)
    spec_b = st.text_area("Specification Support", key="spec_b", height=200)

analyze = st.button("Analyze", use_container_width=True)

# --- Analysis ---
if analyze:
    if not all([label_a, claim_a, spec_a, label_b, claim_b, spec_b]):
        st.error("Please fill in all fields for both patents.")
    else:
        source = PatentInput(label=label_a, independent_claim=claim_a, specification=spec_a)
        target = PatentInput(label=label_b, independent_claim=claim_b, specification=spec_b)

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(source, target)

        with st.spinner("Analyzing patents — this may take a minute..."):
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
                )
                append_trace(trace)

            except Exception as e:
                # Log failed run
                trace = build_trace_record(
                    source_patent=source,
                    target_patent=target,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    llm_response=llm_response if "llm_response" in dir() else {"raw_output": "", "model": "", "tokens_input": 0, "tokens_output": 0, "latency_ms": 0},
                    parsed_output=None,
                    status="error",
                    error=str(e),
                )
                append_trace(trace)
                st.error(f"Analysis failed: {e}")
                st.stop()

        # --- Results Area ---
        st.divider()
        st.subheader("Element Mapping")

        rows = []
        for em in report.element_mappings:
            rows.append({
                "Element #": em.element_number,
                "Patent A Element": em.element_text,
                "Patent B Corresponding Text": em.corresponding_text,
                "Novelty": em.novelty,
                "Inventive Step": em.inventive_step,
                "Verdict": em.verdict,
                "Comment": em.comment,
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Overall Opinion")
        st.write(report.overall_opinion)

        # Show metadata
        with st.expander("Run Metadata"):
            st.write(f"**Model:** {llm_response['model']}")
            st.write(f"**Input tokens:** {llm_response['tokens_input']}")
            st.write(f"**Output tokens:** {llm_response['tokens_output']}")
            st.write(f"**Latency:** {llm_response['latency_ms']}ms")
            st.write(f"**Run ID:** {trace['run_id']}")
```

- [ ] **Step 2: Run the app to verify it loads**

Run: `streamlit run app.py`
Expected: Browser opens, shows the two-column input form with all fields and the Analyze button. No errors in the terminal.

- [ ] **Step 3: Test with sample data (requires GROQ_API_KEY)**

Enter sample patent claim text in both sides, click Analyze. Verify:
- Spinner appears during analysis
- Element mapping table displays with correct columns
- Overall opinion displays below the table
- Run metadata is available in the expander
- `traces/traces.jsonl` contains a new line with the trace record

- [ ] **Step 4: Test error handling**

Temporarily set an invalid API key and click Analyze. Verify:
- Error message displays in the UI
- `traces/traces.jsonl` contains an error trace record

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit UI with patent input, analysis, and results display"
```

---

### Task 7: Run All Tests and Final Verification

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (models: 5, report: 4, tracing: 3, llm: 5 = 17 total).

- [ ] **Step 2: Verify project structure**

Run: `find . -type f -not -path './.git/*' | sort`
Expected output:
```
./app.py
./core/__init__.py
./core/llm.py
./core/models.py
./core/report.py
./docs/superpowers/plans/2026-04-19-patent-diff.md
./docs/superpowers/specs/2026-04-19-patent-diff-design.md
./README.md
./requirements.txt
./tests/__init__.py
./tests/test_llm.py
./tests/test_models.py
./tests/test_report.py
./tests/test_tracing.py
./tracing/__init__.py
./tracing/logger.py
./tracing/store.py
./traces/.gitkeep
```

- [ ] **Step 3: End-to-end manual test**

Run `streamlit run app.py` with a valid `GROQ_API_KEY`. Enter real patent text for both patents. Verify:
1. Element mapping table renders correctly
2. Overall opinion reads like a patent professional's assessment
3. `traces/traces.jsonl` has a valid JSON line with all fields populated
4. The trace is loadable: `python -c "import pandas as pd; print(pd.read_json('traces/traces.jsonl', lines=True).columns.tolist())"`

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: final adjustments from end-to-end testing"
```
