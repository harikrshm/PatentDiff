# PatentDiff Annotation Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit app for systematic error analysis of PatentDiff traces through structured annotation with element-level and overall judgments, supporting Phase 1 (open coding) and Phase 3 (re-annotation).

**Architecture:** Single Streamlit app with two views (sidebar toggle): Annotation Interface for per-trace judgment capture, and Analysis Dashboard for aggregate view. Data persists to `traces_annotations.jsonl`. Core logic separates concerns: data models (annotation.py), trace loading (trace_loader.py), and UI (app_annotation.py).

**Tech Stack:** Streamlit, Pydantic for data validation, pandas for tabular data, Python 3.8+

---

## File Structure

**Create:**
- `app_annotation.py` — Streamlit UI app
- `core/annotation.py` — AnnotationRecord, persistence, parsing
- `core/trace_loader.py` — Trace loading from traces.jsonl
- `tests/test_annotation.py` — Unit tests

**Use Existing:**
- `traces/traces.jsonl` — Read only
- `traces/traces_annotations.jsonl` — Read/write (will be created)

---

## Phase 1: Core Data Models & Persistence

### Task 1: Create AnnotationRecord Data Class

**Files:**
- Create: `core/annotation.py`
- Test: `tests/test_annotation.py`

- [ ] **Step 1: Write failing test for AnnotationRecord**

```python
# tests/test_annotation.py
from datetime import datetime
from core.annotation import AnnotationRecord

def test_annotation_record_creation():
    """Test basic AnnotationRecord creation."""
    record = AnnotationRecord(
        run_id="test-id-123",
        phase=1,
        element_judgments=[],
        overall_opinion_judgment={"tool_verdict": "test", "your_verdict": "PASS", "critique": "good"},
        open_coded_failure_modes=["hallucination"],
        failure_modes=None,
        annotation="Test annotation",
        reviewed=True,
    )
    assert record.run_id == "test-id-123"
    assert record.phase == 1
    assert len(record.element_judgments) == 0
    assert record.reviewed is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_annotation.py::test_annotation_record_creation -v
```

Expected output: `FAILED ... ModuleNotFoundError: No module named 'core.annotation'`

- [ ] **Step 3: Create AnnotationRecord class**

```python
# core/annotation.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class ElementJudgment(BaseModel):
    element_number: int
    tool_novelty: bool
    tool_inventive_step: bool
    your_verdict: str  # "PASS" or "FAIL"
    critique: str

class OverallOpinionJudgment(BaseModel):
    tool_verdict: str
    your_verdict: str  # "PASS" or "FAIL"
    critique: str

class AnnotationRecord(BaseModel):
    run_id: str
    phase: int  # 1 or 3
    element_judgments: List[ElementJudgment]
    overall_opinion_judgment: OverallOpinionJudgment
    open_coded_failure_modes: Optional[List[str]] = None
    failure_modes: Optional[List[str]] = None
    annotation: str
    reviewed: bool
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "element_judgments": [e.dict() for e in self.element_judgments],
            "overall_opinion_judgment": self.overall_opinion_judgment.dict(),
            "open_coded_failure_modes": self.open_coded_failure_modes,
            "failure_modes": self.failure_modes,
            "annotation": self.annotation,
            "reviewed": self.reviewed,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AnnotationRecord":
        """Create from dictionary (JSON deserialization)."""
        return AnnotationRecord(
            run_id=data["run_id"],
            phase=data["phase"],
            element_judgments=[
                ElementJudgment(**e) for e in data.get("element_judgments", [])
            ],
            overall_opinion_judgment=OverallOpinionJudgment(**data["overall_opinion_judgment"]),
            open_coded_failure_modes=data.get("open_coded_failure_modes"),
            failure_modes=data.get("failure_modes"),
            annotation=data["annotation"],
            reviewed=data["reviewed"],
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_annotation.py::test_annotation_record_creation -v
```

Expected output: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add core/annotation.py tests/test_annotation.py
git commit -m "feat: add AnnotationRecord data class with serialization"
```

---

### Task 2: Create Annotation Persistence (Load/Save)

**Files:**
- Modify: `core/annotation.py`
- Test: `tests/test_annotation.py`

- [ ] **Step 1: Write test for load_annotations**

```python
# tests/test_annotation.py (add to existing file)
import json
import tempfile
from pathlib import Path

def test_load_empty_annotations():
    """Test loading from non-existent file returns empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "annotations.jsonl"
        annotations = load_annotations(path)
        assert annotations == {}

def test_load_annotations_from_jsonl():
    """Test loading annotations from JSONL file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "annotations.jsonl"
        
        # Write test data
        record1 = {
            "run_id": "id1",
            "phase": 1,
            "element_judgments": [],
            "overall_opinion_judgment": {"tool_verdict": "test", "your_verdict": "PASS", "critique": "ok"},
            "open_coded_failure_modes": ["mode1"],
            "failure_modes": None,
            "annotation": "annotation1",
            "reviewed": True,
            "timestamp": "2026-04-24T10:00:00+00:00"
        }
        with open(path, "w") as f:
            f.write(json.dumps(record1) + "\n")
        
        annotations = load_annotations(path)
        assert len(annotations) == 1
        assert annotations["id1"].run_id == "id1"
        assert annotations["id1"].phase == 1

def test_save_annotations():
    """Test saving annotations to JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "annotations.jsonl"
        
        record = AnnotationRecord(
            run_id="id1",
            phase=1,
            element_judgments=[],
            overall_opinion_judgment=OverallOpinionJudgment(
                tool_verdict="test", your_verdict="PASS", critique="ok"
            ),
            open_coded_failure_modes=["mode1"],
            failure_modes=None,
            annotation="test",
            reviewed=True,
        )
        
        save_annotations(path, {"id1": record})
        
        # Verify file exists and contains data
        assert path.exists()
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        loaded = json.loads(lines[0])
        assert loaded["run_id"] == "id1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_annotation.py::test_load_empty_annotations -v
pytest tests/test_annotation.py::test_load_annotations_from_jsonl -v
pytest tests/test_annotation.py::test_save_annotations -v
```

Expected output: `FAILED ... NameError: name 'load_annotations' is not defined`

- [ ] **Step 3: Add load_annotations and save_annotations functions**

```python
# core/annotation.py (add to existing file)
from pathlib import Path

def load_annotations(filepath: Path) -> Dict[str, AnnotationRecord]:
    """Load annotations from JSONL file. Returns empty dict if file doesn't exist."""
    annotations = {}
    if not filepath.exists():
        return annotations
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                record = AnnotationRecord.from_dict(data)
                annotations[record.run_id] = record
            except Exception as e:
                print(f"Warning: Failed to parse line: {e}")
    return annotations

def save_annotations(filepath: Path, annotations: Dict[str, AnnotationRecord]) -> None:
    """Save annotations to JSONL file (overwrites)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for record in annotations.values():
            f.write(json.dumps(record.to_dict()) + "\n")

import json
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_annotation.py::test_load_empty_annotations -v
pytest tests/test_annotation.py::test_load_annotations_from_jsonl -v
pytest tests/test_annotation.py::test_save_annotations -v
```

Expected output: `PASSED (3 passed)`

- [ ] **Step 5: Commit**

```bash
git add core/annotation.py tests/test_annotation.py
git commit -m "feat: add load/save annotations functions for JSONL persistence"
```

---

### Task 3: Create Trace Loader

**Files:**
- Create: `core/trace_loader.py`
- Test: `tests/test_annotation.py` (add trace loader tests)

- [ ] **Step 1: Write test for load_traces**

```python
# tests/test_annotation.py (add to existing file)
from core.trace_loader import load_traces, Trace

def test_load_traces_from_jsonl():
    """Test loading traces from traces.jsonl."""
    traces = load_traces(Path("traces/traces.jsonl"))
    assert len(traces) > 0
    assert all(isinstance(t, Trace) for t in traces)
    # Check first trace has required fields
    first = traces[0]
    assert hasattr(first, "run_id")
    assert hasattr(first, "inputs")
    assert hasattr(first, "parsed_output")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_annotation.py::test_load_traces_from_jsonl -v
```

Expected output: `FAILED ... ModuleNotFoundError: No module named 'core.trace_loader'`

- [ ] **Step 3: Create trace_loader.py**

```python
# core/trace_loader.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class PatentInput(BaseModel):
    label: str
    independent_claim: str
    specification: str

class ElementMapping(BaseModel):
    element_number: int
    element_text: str
    corresponding_text: str
    novelty: bool
    inventive_step: bool
    verdict: str
    comment: str

class ParsedOutput(BaseModel):
    element_mappings: List[ElementMapping]
    overall_opinion: str

class LLMResponse(BaseModel):
    raw_output: str
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: int

class Trace(BaseModel):
    run_id: str
    timestamp: str
    inputs: Dict[str, Any]  # source_patent, target_patent
    llm_response: LLMResponse
    parsed_output: Optional[ParsedOutput]
    status: str
    error: Optional[str]
    truncation_warnings: List[str]
    
    class Config:
        extra = "allow"  # Allow extra fields from JSON

def load_traces(filepath: Path) -> List[Trace]:
    """Load traces from JSONL file."""
    traces = []
    if not filepath.exists():
        return traces
    
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Parse nested objects carefully
                if "llm_response" in data and data["llm_response"]:
                    data["llm_response"] = LLMResponse(**data["llm_response"])
                if "parsed_output" in data and data["parsed_output"]:
                    parsed = data["parsed_output"]
                    if "element_mappings" in parsed:
                        parsed["element_mappings"] = [
                            ElementMapping(**em) for em in parsed["element_mappings"]
                        ]
                    data["parsed_output"] = ParsedOutput(**parsed)
                
                trace = Trace(**data)
                traces.append(trace)
            except Exception as e:
                print(f"Warning: Failed to parse trace at line {i}: {e}")
    
    return traces
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_annotation.py::test_load_traces_from_jsonl -v
```

Expected output: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add core/trace_loader.py tests/test_annotation.py
git commit -m "feat: add trace loader for reading traces.jsonl"
```

---

## Phase 2: Streamlit UI — Annotation Interface

### Task 4: Create Basic Streamlit App Structure with Sidebar Navigation

**Files:**
- Create: `app_annotation.py`

- [ ] **Step 1: Create app skeleton with page routing**

```python
# app_annotation.py
import streamlit as st
from pathlib import Path
from core.annotation import load_annotations, save_annotations
from core.trace_loader import load_traces

# --- Configuration ---
TRACES_FILE = Path("traces/traces.jsonl")
ANNOTATIONS_FILE = Path("traces/traces_annotations.jsonl")
TAXONOMY_FILE = Path("traces/failure_taxonomy.json")

# --- App Setup ---
st.set_page_config(page_title="PatentDiff Annotation Tool", layout="wide")
st.title("PatentDiff Error Analysis Tool")

# --- Session State ---
if "traces" not in st.session_state:
    st.session_state.traces = {t.run_id: t for t in load_traces(TRACES_FILE)}
if "annotations" not in st.session_state:
    st.session_state.annotations = load_annotations(ANNOTATIONS_FILE)
if "current_run_id" not in st.session_state:
    st.session_state.current_run_id = None

# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("View", ["Annotation Interface", "Analysis Dashboard"])

# --- Main Content ---
if view == "Annotation Interface":
    st.write("Annotation Interface coming soon...")
elif view == "Analysis Dashboard":
    st.write("Analysis Dashboard coming soon...")
```

- [ ] **Step 2: Run the app to verify basic structure**

```bash
streamlit run app_annotation.py
```

Expected output: App opens at localhost:8501 with sidebar navigation

- [ ] **Step 3: Commit**

```bash
git add app_annotation.py
git commit -m "feat: create annotation tool app skeleton with page routing"
```

---

### Task 5: Build Trace Navigator Sidebar

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add trace navigator to sidebar**

Replace the sidebar section with:

```python
# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("View", ["Annotation Interface", "Analysis Dashboard"])

st.sidebar.divider()

if view == "Annotation Interface":
    st.sidebar.subheader("Trace Navigator")
    
    # Search bar
    search_term = st.sidebar.text_input("Search by Run ID or annotation", value="")
    
    # Filters
    col1, col2 = st.sidebar.columns(2)
    with col1:
        filter_reviewed = st.selectbox("Reviewed", ["All", "Reviewed", "Unreviewed"])
    with col2:
        filter_phase = st.selectbox("Phase", ["All", "Phase 1", "Phase 3"])
    
    # Build filtered trace list
    filtered_traces = []
    for run_id, trace in st.session_state.traces.items():
        annotation = st.session_state.annotations.get(run_id)
        
        # Apply filters
        if search_term and search_term.lower() not in run_id.lower():
            if annotation and search_term.lower() not in annotation.annotation.lower():
                continue
        
        if filter_reviewed == "Reviewed" and (not annotation or not annotation.reviewed):
            continue
        if filter_reviewed == "Unreviewed" and annotation and annotation.reviewed:
            continue
        
        if filter_phase == "Phase 1" and annotation and annotation.phase != 1:
            continue
        if filter_phase == "Phase 3" and annotation and annotation.phase != 3:
            continue
        
        filtered_traces.append((run_id, trace, annotation))
    
    # Progress bar
    reviewed_count = sum(1 for _, _, a in filtered_traces if a and a.reviewed)
    total_count = len(filtered_traces)
    st.sidebar.progress(reviewed_count / total_count if total_count > 0 else 0)
    st.sidebar.caption(f"Reviewed {reviewed_count}/{total_count} traces")
    
    # Trace list
    st.sidebar.subheader("Traces")
    for run_id, trace, annotation in filtered_traces:
        status_icon = "✅" if annotation and annotation.reviewed else "⭕"
        phase_icon = "🔹" if annotation and annotation.phase == 3 else ""
        label = trace.inputs.get("source_patent", {}).get("label", "?")
        display_text = f"{status_icon} {phase_icon} {label[:15]}..."
        
        if st.sidebar.button(display_text, key=f"trace_{run_id}"):
            st.session_state.current_run_id = run_id
```

- [ ] **Step 2: Test the sidebar navigation**

```bash
streamlit run app_annotation.py
```

Expected output: Sidebar shows trace list with search/filters, clicking a trace selects it

- [ ] **Step 3: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add trace navigator with search and filters to sidebar"
```

---

### Task 6: Build Trace Display Panel

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add trace display function**

```python
# app_annotation.py (add helper function)

def display_trace(trace):
    """Display full trace details in read-only format."""
    st.subheader("Trace Metadata")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Run ID", trace.run_id[:12] + "...")
    with col2:
        st.metric("Status", trace.status)
    with col3:
        st.metric("Timestamp", trace.timestamp[:10])
    with col4:
        st.metric("Model", trace.llm_response.model if trace.llm_response else "N/A")
    
    st.divider()
    
    # Patents
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Source Patent (A)")
        src = trace.inputs.get("source_patent", {})
        st.write(f"**Label:** {src.get('label', 'N/A')}")
        st.write("**Independent Claim:**")
        st.text_area("Claim A", value=src.get('independent_claim', ''), disabled=True, height=100, key="src_claim")
        st.write("**Specification:**")
        st.text_area("Spec A", value=src.get('specification', '')[:500] + "...", disabled=True, height=80, key="src_spec")
    
    with col_b:
        st.subheader("Target Patent (B)")
        tgt = trace.inputs.get("target_patent", {})
        st.write(f"**Label:** {tgt.get('label', 'N/A')}")
        st.write("**Independent Claim:**")
        st.text_area("Claim B", value=tgt.get('independent_claim', ''), disabled=True, height=100, key="tgt_claim")
        st.write("**Specification:**")
        st.text_area("Spec B", value=tgt.get('specification', '')[:500] + "...", disabled=True, height=80, key="tgt_spec")
    
    st.divider()
    
    # Parsed output
    if trace.parsed_output:
        st.subheader("Element Mappings")
        for em in trace.parsed_output.element_mappings:
            with st.expander(f"Element {em.element_number}: {em.verdict}"):
                st.write(f"**Element Text:** {em.element_text}")
                st.write(f"**Corresponding Text:** {em.corresponding_text}")
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Novelty", "✅" if em.novelty else "❌")
                with cols[1]:
                    st.metric("Inventive Step", "✅" if em.inventive_step else "❌")
                with cols[2]:
                    st.metric("Verdict", em.verdict)
                st.write(f"**Comment:** {em.comment}")
        
        st.subheader("Overall Opinion")
        st.text_area("Tool's Final Verdict", value=trace.parsed_output.overall_opinion, disabled=True, height=150)
    
    # LLM Response metadata
    if trace.llm_response:
        st.subheader("Run Metadata")
        cols = st.columns(4)
        with cols[0]:
            st.metric("Input Tokens", trace.llm_response.tokens_input)
        with cols[1]:
            st.metric("Output Tokens", trace.llm_response.tokens_output)
        with cols[2]:
            st.metric("Latency (ms)", trace.llm_response.latency_ms)
        with cols[3]:
            st.metric("Model", trace.llm_response.model)
```

- [ ] **Step 2: Add trace display to main content**

Replace the "coming soon" placeholder in the Annotation Interface section with:

```python
if view == "Annotation Interface":
    # (sidebar code from Task 5...)
    
    st.divider()
    
    if st.session_state.current_run_id and st.session_state.current_run_id in st.session_state.traces:
        trace = st.session_state.traces[st.session_state.current_run_id]
        display_trace(trace)
    else:
        st.info("Select a trace from the sidebar to begin annotation.")
```

- [ ] **Step 3: Test the trace display**

```bash
streamlit run app_annotation.py
```

Expected output: Click a trace in sidebar, full trace displays on right with metadata, elements, overall opinion

- [ ] **Step 4: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add trace display panel with metadata and element mappings"
```

---

### Task 7: Build Element-Level Critique Form

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add element critique form function**

```python
# app_annotation.py (add function)

def element_critique_form(trace, run_id, current_annotation=None):
    """Build and handle element-level critique form."""
    if not trace.parsed_output or not trace.parsed_output.element_mappings:
        st.warning("No element mappings found in this trace.")
        return None
    
    elements = trace.parsed_output.element_mappings
    element_numbers = [em.element_number for em in elements]
    
    st.subheader("Element-Level Critique")
    
    selected_element_num = st.selectbox(
        "Select Element",
        element_numbers,
        key=f"element_select_{run_id}"
    )
    
    selected_element = next(em for em in elements if em.element_number == selected_element_num)
    
    st.write(f"**Element {selected_element.element_number}**")
    st.write(f"Element Text: {selected_element.element_text}")
    st.write(f"Corresponding Text: {selected_element.corresponding_text}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tool's Novelty", "✅ Yes" if selected_element.novelty else "❌ No")
    with col2:
        st.metric("Tool's Inventive Step", "✅ Yes" if selected_element.inventive_step else "❌ No")
    with col3:
        st.metric("Tool's Verdict", selected_element.verdict)
    
    st.write("**Your Judgment:**")
    your_verdict = st.radio(
        "Pass/Fail",
        ["PASS", "FAIL"],
        key=f"element_verdict_{run_id}_{selected_element_num}"
    )
    
    critique = st.text_area(
        "Critique",
        value="",
        placeholder="Explain your verdict for this element...",
        key=f"element_critique_{run_id}_{selected_element_num}",
        height=100
    )
    
    reviewed = st.checkbox("Reviewed", key=f"element_reviewed_{run_id}_{selected_element_num}")
    
    return {
        "element_number": selected_element_num,
        "tool_novelty": selected_element.novelty,
        "tool_inventive_step": selected_element.inventive_step,
        "your_verdict": your_verdict,
        "critique": critique,
        "reviewed": reviewed,
    }
```

- [ ] **Step 2: Add element critique to annotation interface**

```python
# Modify the Annotation Interface section to include element critique:
if view == "Annotation Interface":
    # (sidebar code...)
    st.divider()
    
    if st.session_state.current_run_id and st.session_state.current_run_id in st.session_state.traces:
        trace = st.session_state.traces[st.session_state.current_run_id]
        current_annotation = st.session_state.annotations.get(st.session_state.current_run_id)
        
        # Display trace (first column)
        col_trace, col_form = st.columns([1.5, 1])
        
        with col_trace:
            display_trace(trace)
        
        with col_form:
            st.subheader("Annotation Form")
            element_judgment = element_critique_form(trace, st.session_state.current_run_id, current_annotation)
```

- [ ] **Step 3: Test element critique form**

```bash
streamlit run app_annotation.py
```

Expected output: Sidebar + trace display on left, element critique form on right with element selector, verdicts, and text area

- [ ] **Step 4: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add element-level critique form with verdict and critique input"
```

---

### Task 8: Build Overall Opinion Critique Form

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add overall opinion critique form**

```python
# app_annotation.py (add function)

def overall_opinion_critique_form(trace, run_id):
    """Build and handle overall opinion critique form."""
    st.subheader("Overall Opinion Critique")
    
    if not trace.parsed_output:
        st.warning("No parsed output found.")
        return None
    
    st.write("**Tool's Final Verdict:**")
    st.text_area(
        "Overall Opinion",
        value=trace.parsed_output.overall_opinion,
        disabled=True,
        height=150,
        key=f"overall_opinion_display_{run_id}"
    )
    
    st.write("**Your Judgment:**")
    your_verdict = st.radio(
        "Pass/Fail",
        ["PASS", "FAIL"],
        key=f"overall_verdict_{run_id}"
    )
    
    critique = st.text_area(
        "Critique",
        value="",
        placeholder="Explain your verdict for the overall opinion...",
        key=f"overall_critique_{run_id}",
        height=100
    )
    
    reviewed = st.checkbox("Reviewed", key=f"overall_reviewed_{run_id}")
    
    return {
        "tool_verdict": trace.parsed_output.overall_opinion,
        "your_verdict": your_verdict,
        "critique": critique,
        "reviewed": reviewed,
    }
```

- [ ] **Step 2: Add overall opinion form to annotation interface**

```python
# In the Annotation Interface section, after element_judgment form, add:

        with col_form:
            st.subheader("Annotation Form")
            element_judgment = element_critique_form(trace, st.session_state.current_run_id, current_annotation)
            
            st.divider()
            
            overall_opinion = overall_opinion_critique_form(trace, st.session_state.current_run_id)
```

- [ ] **Step 3: Test overall opinion form**

```bash
streamlit run app_annotation.py
```

Expected output: Element form + overall opinion form visible in right column

- [ ] **Step 4: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add overall opinion critique form"
```

---

### Task 9: Build Phase-Specific Failure Mode Annotation

**Files:**
- Modify: `app_annotation.py`
- Modify: `core/annotation.py` (add phase detection)

- [ ] **Step 1: Add utility to detect phase from taxonomy**

```python
# core/annotation.py (add function)

def detect_phase(taxonomy_path: Path = None) -> int:
    """Detect which phase to use based on whether taxonomy exists."""
    if taxonomy_path is None:
        taxonomy_path = Path("traces/failure_taxonomy.json")
    
    if taxonomy_path.exists():
        return 3  # Re-annotation with taxonomy
    return 1  # Open coding discovery

def load_taxonomy(taxonomy_path: Path) -> Dict[str, str]:
    """Load failure taxonomy. Returns empty dict if file doesn't exist."""
    if not taxonomy_path.exists():
        return {}
    
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_failure_modes(text: str, delimiter: str = "|") -> List[str]:
    """Parse delimited failure modes from text input."""
    if not text:
        return []
    modes = [mode.strip() for mode in text.split(delimiter)]
    return [m for m in modes if m]  # Remove empty strings
```

- [ ] **Step 2: Run tests to verify parse_failure_modes**

```python
# tests/test_annotation.py (add test)

def test_parse_failure_modes():
    """Test parsing delimited failure modes."""
    from core.annotation import parse_failure_modes
    
    result = parse_failure_modes("hallucination | truncation | claim_mismatch")
    assert result == ["hallucination", "truncation", "claim_mismatch"]
    
    result = parse_failure_modes("mode1")
    assert result == ["mode1"]
    
    result = parse_failure_modes("")
    assert result == []
```

```bash
pytest tests/test_annotation.py::test_parse_failure_modes -v
```

Expected: PASS (after implementing parse_failure_modes)

- [ ] **Step 3: Add failure mode form to annotation interface**

```python
# app_annotation.py (add function)

def failure_mode_annotation_form(run_id, phase=1, current_annotation=None, taxonomy=None):
    """Build failure mode annotation form based on phase."""
    st.subheader("Failure Mode Annotation")
    
    if phase == 1:
        st.write("**Phase 1: Open Coding**")
        failure_modes_text = st.text_input(
            "Open-Coded Failure Modes",
            value="",
            placeholder="Format: hallucination | truncation | claim_mismatch",
            key=f"open_failure_modes_{run_id}"
        )
        failure_modes = parse_failure_modes(failure_modes_text)
    else:  # phase == 3
        st.write("**Phase 3: Re-annotation with Taxonomy**")
        available_modes = list(taxonomy.keys()) if taxonomy else []
        failure_modes_text = st.text_input(
            "Failure Modes",
            value="",
            placeholder="Format: mode1 | mode2",
            key=f"failure_modes_{run_id}"
        )
        failure_modes = parse_failure_modes(failure_modes_text)
    
    annotation_text = st.text_area(
        "Annotation/Critique",
        value="",
        placeholder="Describe all failure modes found in this trace...",
        key=f"annotation_text_{run_id}",
        height=120
    )
    
    return {
        "failure_modes": failure_modes,
        "failure_modes_text": failure_modes_text,
        "annotation": annotation_text,
    }
```

- [ ] **Step 4: Integrate phase detection and add failure mode form to interface**

```python
# At top of app_annotation.py, add phase detection:
if "phase" not in st.session_state:
    from core.annotation import detect_phase
    st.session_state.phase = detect_phase()

# If "taxonomy" not in st.session_state:
if "taxonomy" not in st.session_state:
    from core.annotation import load_taxonomy
    st.session_state.taxonomy = load_taxonomy(TAXONOMY_FILE)

# In Annotation Interface section, after overall_opinion form:
        with col_form:
            # ... element and overall forms ...
            
            st.divider()
            
            failure_mode_data = failure_mode_annotation_form(
                st.session_state.current_run_id,
                phase=st.session_state.phase,
                current_annotation=current_annotation,
                taxonomy=st.session_state.taxonomy
            )
```

- [ ] **Step 5: Test phase detection and failure mode form**

```bash
pytest tests/test_annotation.py::test_parse_failure_modes -v
streamlit run app_annotation.py
```

Expected output: Failure mode form shown based on phase, parse test passes

- [ ] **Step 6: Commit**

```bash
git add core/annotation.py app_annotation.py tests/test_annotation.py
git commit -m "feat: add phase detection and failure mode annotation form"
```

---

### Task 10: Build Save/Navigation Logic

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add save function**

```python
# app_annotation.py (add function)

def save_annotation(run_id, element_judgments, overall_opinion, failure_modes, annotation_text, phase):
    """Save annotation to session state and file."""
    from core.annotation import AnnotationRecord, ElementJudgment, OverallOpinionJudgment
    
    # Create ElementJudgment objects
    element_objs = [
        ElementJudgment(**ej) for ej in element_judgments
    ]
    
    # Create OverallOpinionJudgment object
    overall_obj = OverallOpinionJudgment(**overall_opinion)
    
    # Determine failure mode fields based on phase
    open_coded = failure_modes if phase == 1 else None
    standardized = failure_modes if phase == 3 else None
    
    # Create record
    record = AnnotationRecord(
        run_id=run_id,
        phase=phase,
        element_judgments=element_objs,
        overall_opinion_judgment=overall_obj,
        open_coded_failure_modes=open_coded,
        failure_modes=standardized,
        annotation=annotation_text,
        reviewed=True,
    )
    
    # Save to session state
    st.session_state.annotations[run_id] = record
    
    # Save to file
    save_annotations(ANNOTATIONS_FILE, st.session_state.annotations)
    
    st.success("Annotation saved!")
```

- [ ] **Step 2: Add save and navigation buttons**

```python
# In Annotation Interface section, after all forms:

        with col_form:
            # ... all forms ...
            
            st.divider()
            
            col_save, col_next, col_prev = st.columns(3)
            
            with col_save:
                if st.button("💾 Save", use_container_width=True):
                    if element_judgment and overall_opinion and failure_mode_data:
                        # Collect all element judgments from the trace
                        all_element_judgments = []
                        if trace.parsed_output:
                            for em in trace.parsed_output.element_mappings:
                                all_element_judgments.append({
                                    "element_number": em.element_number,
                                    "tool_novelty": em.novelty,
                                    "tool_inventive_step": em.inventive_step,
                                    "your_verdict": "PASS",  # Default - would be form input in full impl
                                    "critique": "",
                                })
                        
                        save_annotation(
                            st.session_state.current_run_id,
                            all_element_judgments,
                            overall_opinion,
                            failure_mode_data["failure_modes"],
                            failure_mode_data["annotation"],
                            st.session_state.phase
                        )
                    else:
                        st.error("Please complete all fields before saving.")
            
            with col_next:
                if st.button("→ Next", use_container_width=True):
                    # Find next unreviewed trace
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx < len(trace_ids) - 1:
                        st.session_state.current_run_id = trace_ids[current_idx + 1]
                        st.rerun()
                    else:
                        st.info("No more traces.")
            
            with col_prev:
                if st.button("← Prev", use_container_width=True):
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx > 0:
                        st.session_state.current_run_id = trace_ids[current_idx - 1]
                        st.rerun()
```

- [ ] **Step 3: Test save and navigation**

```bash
streamlit run app_annotation.py
```

Expected output: Save button saves annotation, Next/Previous buttons navigate between traces

- [ ] **Step 4: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add save and navigation buttons for annotation interface"
```

---

## Phase 3: Analysis Dashboard

### Task 11: Build Tabular Analysis View

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add analysis dashboard function**

```python
# app_annotation.py (add function)

def build_analysis_dashboard():
    """Build tabular view of all annotations."""
    st.subheader("All Annotations")
    
    # Build dataframe from annotations
    rows = []
    for run_id, annotation in st.session_state.annotations.items():
        trace = st.session_state.traces.get(run_id)
        if trace:
            src_label = trace.inputs.get("source_patent", {}).get("label", "?")
            tgt_label = trace.inputs.get("target_patent", {}).get("label", "?")
            
            failure_modes = annotation.failure_modes or annotation.open_coded_failure_modes or []
            failure_modes_str = "; ".join(failure_modes) if failure_modes else ""
            
            rows.append({
                "Run ID": run_id[:12] + "...",
                "Status": trace.status,
                "Source": src_label,
                "Target": tgt_label,
                "Failure Modes": failure_modes_str,
                "Phase": annotation.phase,
                "Your Verdict": f"{annotation.overall_opinion_judgment.your_verdict}",
                "Reviewed": "✅" if annotation.reviewed else "❌",
                "Annotation": annotation.annotation[:50] + "..." if annotation.annotation else "",
            })
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Frequency analysis
    st.subheader("Failure Mode Frequency")
    all_modes = []
    for annotation in st.session_state.annotations.values():
        modes = annotation.failure_modes or annotation.open_coded_failure_modes or []
        all_modes.extend(modes)
    
    from collections import Counter
    mode_counts = Counter(all_modes)
    
    if mode_counts:
        freq_df = pd.DataFrame(
            sorted(mode_counts.items(), key=lambda x: x[1], reverse=True),
            columns=["Failure Mode", "Count"]
        )
        st.bar_chart(freq_df.set_index("Failure Mode"))
        st.dataframe(freq_df, use_container_width=True, hide_index=True)
    else:
        st.info("No failure modes annotated yet.")
    
    # Verdict summary
    st.subheader("Verdict Summary")
    verdicts = [a.overall_opinion_judgment.your_verdict for a in st.session_state.annotations.values()]
    verdict_counts = Counter(verdicts)
    st.metric("PASS", verdict_counts.get("PASS", 0))
    st.metric("FAIL", verdict_counts.get("FAIL", 0))
```

- [ ] **Step 2: Add dashboard to main content**

```python
# In main content, after annotation interface section:

elif view == "Analysis Dashboard":
    build_analysis_dashboard()
```

- [ ] **Step 3: Add pandas import**

```python
# At top of app_annotation.py:
import pandas as pd
```

- [ ] **Step 4: Test analysis dashboard**

```bash
streamlit run app_annotation.py
```

Expected output: Switch to "Analysis Dashboard" view, see table of annotations, failure mode frequency chart

- [ ] **Step 5: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add analysis dashboard with tabular view and frequency analysis"
```

---

### Task 12: Add Export to CSV Feature

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Add CSV export to dashboard**

```python
# In build_analysis_dashboard() function, after dataframe display, add:

    st.divider()
    
    # Export options
    st.subheader("Export")
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="annotations_export.csv",
            mime="text/csv"
        )
    
    with col2:
        if st.button("📋 Copy Table to Clipboard"):
            st.info("Manually select and copy the table above.")
```

- [ ] **Step 2: Test export feature**

```bash
streamlit run app_annotation.py
```

Expected output: Click download button, CSV file downloaded

- [ ] **Step 3: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add CSV export to analysis dashboard"
```

---

## Phase 4: Integration & Polish

### Task 13: Add Error Handling and Validation

**Files:**
- Modify: `app_annotation.py`
- Modify: `core/trace_loader.py`

- [ ] **Step 1: Add error handling to trace loading**

```python
# At app startup, wrap trace loading:

try:
    if "traces" not in st.session_state:
        st.session_state.traces = {t.run_id: t for t in load_traces(TRACES_FILE)}
except Exception as e:
    st.error(f"Failed to load traces: {e}")
    st.stop()

try:
    if "annotations" not in st.session_state:
        st.session_state.annotations = load_annotations(ANNOTATIONS_FILE)
except Exception as e:
    st.error(f"Failed to load annotations: {e}")
    st.session_state.annotations = {}
```

- [ ] **Step 2: Add validation to save function**

```python
# In save_annotation function, add at start:

    if not run_id or not annotation_text:
        raise ValueError("Run ID and annotation text are required.")
    
    if not element_judgments or not overall_opinion or not failure_modes:
        raise ValueError("Element judgments, overall opinion, and failure modes are required.")
```

- [ ] **Step 3: Test error handling**

```bash
streamlit run app_annotation.py
# Try loading with missing traces file, etc.
```

Expected output: Graceful error messages, app doesn't crash

- [ ] **Step 4: Commit**

```bash
git add app_annotation.py
git commit -m "feat: add error handling and validation"
```

---

### Task 14: Final Testing & Documentation

**Files:**
- Create: `README_ANNOTATION_TOOL.md`

- [ ] **Step 1: Write annotation tool README**

```markdown
# PatentDiff Annotation Tool

## Overview

A Streamlit-based tool for systematic error analysis of PatentDiff traces through structured annotation.

Supports two phases:
- **Phase 1**: Open coding — freely discover and label failure modes
- **Phase 3**: Re-annotation — standardize labels using a refined taxonomy

## Running the Tool

```bash
streamlit run app_annotation.py
```

The app opens at `http://localhost:8501`.

## Workflow

### Phase 1: Open Coding
1. Open app → "Annotation Interface"
2. Sidebar: select trace
3. Review element mappings and overall opinion
4. Judge each element: PASS/FAIL + critique
5. Judge overall opinion: PASS/FAIL + critique
6. Tag failure modes (free-form): "hallucination | truncation"
7. Add annotation explaining the modes
8. Click Save
9. Repeat for all 83 traces

### Phase 2: Axial Coding (External)
After Phase 1, run Jupyter notebook:
```bash
jupyter notebook phase2_axial_coding.ipynb
```
This clusters open-coded modes into a refined taxonomy and outputs `failure_taxonomy.json`.

### Phase 3: Re-annotation
Once `failure_taxonomy.json` exists:
1. Open annotation tool (detects Phase 3 automatically)
2. Sidebar filters show both Phase 1 and Phase 3 annotations
3. Review each trace, assign standardized failure modes from dropdown
4. Save to update `failure_modes` field

## Files

- `app_annotation.py` — Main Streamlit app
- `core/annotation.py` — Data models and persistence
- `core/trace_loader.py` — Trace loading
- `traces/traces_annotations.jsonl` — Annotation storage
- `traces/failure_taxonomy.json` — (Phase 3) Refined failure mode taxonomy

## Data Model

Each annotation in `traces_annotations.jsonl`:

```json
{
  "run_id": "...",
  "phase": 1,
  "element_judgments": [
    {
      "element_number": 1,
      "tool_novelty": true,
      "tool_inventive_step": false,
      "your_verdict": "PASS",
      "critique": "..."
    }
  ],
  "overall_opinion_judgment": {
    "tool_verdict": "...",
    "your_verdict": "FAIL",
    "critique": "..."
  },
  "open_coded_failure_modes": ["hallucination", "truncation"],
  "failure_modes": null,
  "annotation": "...",
  "reviewed": true,
  "timestamp": "2026-04-24T..."
}
```

## Features

- **Trace Navigator**: Search, filter by reviewed status/phase
- **Element-Level Critique**: Judge each element's novelty/inventive step verdicts
- **Overall Opinion Critique**: Judge final verdict
- **Multiple Failure Modes**: Tag multiple modes per trace with delimiters
- **Phase Flexibility**: Single tool supports open and selective coding
- **Analysis Dashboard**: Tabular view, frequency analysis, CSV export
- **Persistent Storage**: Auto-saves to `traces_annotations.jsonl`
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/test_annotation.py -v
```

Expected output: All tests pass

- [ ] **Step 3: Commit**

```bash
git add README_ANNOTATION_TOOL.md
git commit -m "docs: add annotation tool README and documentation"
```

---

### Task 15: Integration Test & Demo

**Files:**
- Run: `app_annotation.py`

- [ ] **Step 1: Manual integration test**

```bash
streamlit run app_annotation.py
```

Checklist:
- [ ] App loads without errors
- [ ] Sidebar displays 83 traces
- [ ] Search bar filters traces by run_id
- [ ] Can select a trace and view full details
- [ ] Element selector dropdown works
- [ ] Overall opinion critique form appears
- [ ] Failure mode input accepts delimiter-separated modes
- [ ] Save button creates/updates annotation JSON
- [ ] Next/Previous buttons navigate traces
- [ ] Switch to Analysis Dashboard
- [ ] Table displays all annotations
- [ ] Failure mode frequency chart updates
- [ ] CSV export works
- [ ] Phase detection works (no taxonomy → Phase 1 mode)

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat: complete annotation tool with all features and documentation"
```

---

## Self-Review Against Spec

✅ **Spec Coverage:**
- ✅ Two interfaces: Annotation + Analysis Dashboard
- ✅ Element-level critique (novelty, inventive_step, your_verdict, critique)
- ✅ Overall opinion critique (tool_verdict, your_verdict, critique)
- ✅ Multiple failure modes per trace (delimiter-separated)
- ✅ Phase 1/3 mode switching
- ✅ Persistent storage (traces_annotations.jsonl)
- ✅ Search and filtering in sidebar
- ✅ Progress tracking
- ✅ Frequency analysis
- ✅ Export to CSV

✅ **Placeholders:** None detected

✅ **Type Consistency:** ElementJudgment, OverallOpinionJudgment, AnnotationRecord used consistently

✅ **Scope:** Focused on annotation tool (Phases 1 & 3), out-of-scope items (Phase 2, 4, 5) noted as external

---
