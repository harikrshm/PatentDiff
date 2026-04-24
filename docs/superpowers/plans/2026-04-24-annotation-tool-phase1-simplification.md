# Phase 1 Annotation Tool Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the annotation tool to focus on Phase 1 failure mode discovery by removing all verdict judgment sections and streamlining the form to just PASS/FAIL, failure modes, and comment.

**Architecture:** Remove element-level and overall-opinion critique sections from the UI. Simplify AnnotationRecord data model by removing ElementJudgment and OverallOpinionJudgment classes. Update app_annotation.py to show only failure modes annotation form. Simplify analysis dashboard to focus on failure mode frequency.

**Tech Stack:** Streamlit, Pydantic, Pandas

---

## File Structure

**Files to Modify:**
- `core/annotation.py` — Remove ElementJudgment, OverallOpinionJudgment; update AnnotationRecord
- `tests/test_annotation.py` — Update tests for simplified model
- `app_annotation.py` — Remove critique forms, add PASS/FAIL verdict, simplify form and dashboard

**No new files needed.**

---

## Phase 1: Data Model Simplification

### Task 1: Update AnnotationRecord and Remove Unused Classes

**Files:**
- Modify: `core/annotation.py`
- Modify: `tests/test_annotation.py`

- [ ] **Step 1: Write test for simplified AnnotationRecord**

```python
# tests/test_annotation.py (add new test)
from core.annotation import AnnotationRecord

def test_annotation_record_simplified():
    """Test simplified AnnotationRecord with verdict and comment."""
    record = AnnotationRecord(
        run_id="test-id-123",
        phase=1,
        open_coded_failure_modes=["hallucination", "truncation"],
        verdict="FAIL",
        comment="Tool hallucinated correspondence in element 3.",
        reviewed=True,
    )
    assert record.run_id == "test-id-123"
    assert record.verdict == "FAIL"
    assert len(record.open_coded_failure_modes) == 2
    assert record.comment == "Tool hallucinated correspondence in element 3."
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_annotation.py::test_annotation_record_simplified -v
```

Expected: FAIL with "TypeError: __init__() missing required positional argument 'verdict'"

- [ ] **Step 3: Update AnnotationRecord class in core/annotation.py**

Replace the entire AnnotationRecord class definition with:

```python
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class AnnotationRecord(BaseModel):
    run_id: str
    phase: int  # 1 or 3
    open_coded_failure_modes: Optional[List[str]] = None
    verdict: str  # "PASS" or "FAIL"
    comment: str
    reviewed: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "open_coded_failure_modes": self.open_coded_failure_modes,
            "verdict": self.verdict,
            "comment": self.comment,
            "reviewed": self.reviewed,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AnnotationRecord":
        """Create from dictionary (JSON deserialization)."""
        return AnnotationRecord(
            run_id=data["run_id"],
            phase=data["phase"],
            open_coded_failure_modes=data.get("open_coded_failure_modes"),
            verdict=data["verdict"],
            comment=data["comment"],
            reviewed=data.get("reviewed", False),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
```

- [ ] **Step 4: Delete ElementJudgment and OverallOpinionJudgment classes**

Find and remove these class definitions from core/annotation.py:
- `class ElementJudgment(BaseModel): ...`
- `class OverallOpinionJudgment(BaseModel): ...`

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_annotation.py::test_annotation_record_simplified -v
```

Expected: PASS

- [ ] **Step 6: Run all annotation tests**

```bash
pytest tests/test_annotation.py -v
```

Expected: Some existing tests may fail (element/overall judgments removed). That's OK for now.

- [ ] **Step 7: Commit**

```bash
git add core/annotation.py tests/test_annotation.py
git commit -m "refactor: simplify AnnotationRecord - remove ElementJudgment and OverallOpinionJudgment"
```

---

### Task 2: Update Existing Tests for New Data Model

**Files:**
- Modify: `tests/test_annotation.py`

- [ ] **Step 1: Update test_annotation_to_dict**

Replace the existing `test_annotation_to_dict` function with:

```python
def test_annotation_to_dict_simplified():
    """Test simplified AnnotationRecord serialization to dict."""
    record = AnnotationRecord(
        run_id="id1",
        phase=1,
        open_coded_failure_modes=["hallucination"],
        verdict="FAIL",
        comment="Tool hallucinated",
        reviewed=True,
    )
    
    d = record.to_dict()
    assert d["run_id"] == "id1"
    assert d["phase"] == 1
    assert d["verdict"] == "FAIL"
    assert d["comment"] == "Tool hallucinated"
    assert d["open_coded_failure_modes"] == ["hallucination"]
```

- [ ] **Step 2: Update test_annotation_from_dict**

Replace the existing `test_annotation_from_dict` function with:

```python
def test_annotation_from_dict_simplified():
    """Test simplified AnnotationRecord deserialization from dict."""
    data = {
        "run_id": "id1",
        "phase": 1,
        "open_coded_failure_modes": ["hallucination"],
        "verdict": "FAIL",
        "comment": "Tool hallucinated",
        "reviewed": True,
        "timestamp": "2026-04-24T10:00:00+00:00"
    }
    
    record = AnnotationRecord.from_dict(data)
    assert record.run_id == "id1"
    assert record.verdict == "FAIL"
    assert record.comment == "Tool hallucinated"
```

- [ ] **Step 3: Remove obsolete tests**

Delete these test functions (they test removed classes):
- `test_element_judgment_creation`

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_annotation.py -v
```

Expected: 8 tests pass (removed one, added/updated others)

- [ ] **Step 5: Commit**

```bash
git add tests/test_annotation.py
git commit -m "test: update tests for simplified AnnotationRecord"
```

---

## Phase 2: UI Simplification

### Task 3: Remove Critique Forms and Add PASS/FAIL Verdict

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Remove element_critique_form function**

Delete the entire `element_critique_form()` function from app_annotation.py (approximately 40 lines).

- [ ] **Step 2: Remove overall_opinion_critique_form function**

Delete the entire `overall_opinion_critique_form()` function from app_annotation.py (approximately 30 lines).

- [ ] **Step 3: Create simplified annotation_form function**

Add this new function to app_annotation.py:

```python
def annotation_form(run_id):
    """Build simplified annotation form for Phase 1 (verdict + failure modes + comment)."""
    st.subheader("Annotation Form")
    
    st.write("**Trace Quality Verdict:**")
    verdict = st.radio(
        "Pass/Fail",
        ["PASS", "FAIL"],
        key=f"verdict_{run_id}",
        horizontal=True
    )
    
    st.write("**Failure Modes:**")
    failure_modes_text = st.text_input(
        "Delimited failure modes",
        value="",
        placeholder="Format: hallucination | truncation | claim_mismatch",
        key=f"failure_modes_{run_id}"
    )
    failure_modes = parse_failure_modes(failure_modes_text)
    
    st.write("**Comment:**")
    comment = st.text_area(
        "Explain the failure modes",
        value="",
        placeholder="Describe what failure modes you found and why...",
        key=f"comment_{run_id}",
        height=150
    )
    
    reviewed = st.checkbox("Reviewed", key=f"reviewed_{run_id}")
    
    return {
        "verdict": verdict,
        "failure_modes": failure_modes,
        "comment": comment,
        "reviewed": reviewed,
    }
```

- [ ] **Step 4: Update save_annotation function**

Replace the existing `save_annotation()` function with:

```python
def save_annotation(run_id, verdict, failure_modes, comment, reviewed):
    """Save annotation to session state and file."""
    if not comment:
        st.error("Comment is required.")
        return False
    
    if verdict == "FAIL" and not failure_modes:
        st.warning("FAIL verdict but no failure modes noted. Please add at least one mode or mark as PASS.")
        return False
    
    record = AnnotationRecord(
        run_id=run_id,
        phase=1,
        open_coded_failure_modes=failure_modes,
        verdict=verdict,
        comment=comment,
        reviewed=reviewed,
    )
    
    st.session_state.annotations[run_id] = record
    save_annotations(ANNOTATIONS_FILE, st.session_state.annotations)
    st.success("Annotation saved!")
    return True
```

- [ ] **Step 5: Update Annotation Interface main content**

In the Annotation Interface section, replace all the form handling code (element critique, overall opinion, etc.) with:

```python
if view == "Annotation Interface":
    st.sidebar.subheader("Trace Navigator")
    
    search_term = st.sidebar.text_input("Search by Run ID or comment", value="")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        filter_verdict = st.selectbox("Verdict", ["All", "PASS", "FAIL"])
    with col2:
        filter_reviewed = st.selectbox("Reviewed", ["All", "Reviewed", "Unreviewed"])
    
    # Build filtered trace list
    filtered_traces = []
    for run_id, trace in st.session_state.traces.items():
        annotation = st.session_state.annotations.get(run_id)
        
        if search_term:
            if search_term.lower() not in run_id.lower():
                if not annotation or search_term.lower() not in annotation.comment.lower():
                    continue
        
        if filter_verdict != "All" and annotation and annotation.verdict != filter_verdict:
            continue
        
        if filter_reviewed == "Reviewed" and (not annotation or not annotation.reviewed):
            continue
        if filter_reviewed == "Unreviewed" and annotation and annotation.reviewed:
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
        label = trace.inputs.get("source_patent", {}).get("label", "?")
        display_text = f"{status_icon} {label[:15]}..."
        
        if st.sidebar.button(display_text, key=f"trace_{run_id}", use_container_width=True):
            st.session_state.current_run_id = run_id
    
    st.divider()
    
    if st.session_state.current_run_id and st.session_state.current_run_id in st.session_state.traces:
        trace = st.session_state.traces[st.session_state.current_run_id]
        
        col_trace, col_form = st.columns([1.5, 1])
        
        with col_trace:
            display_trace(trace)
        
        with col_form:
            form_data = annotation_form(st.session_state.current_run_id)
            
            st.divider()
            
            col_save, col_next, col_prev = st.columns(3)
            
            with col_save:
                if st.button("💾 Save", use_container_width=True):
                    if save_annotation(
                        st.session_state.current_run_id,
                        form_data["verdict"],
                        form_data["failure_modes"],
                        form_data["comment"],
                        form_data["reviewed"]
                    ):
                        pass  # Success message already shown
            
            with col_next:
                if st.button("→ Next", use_container_width=True):
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx < len(trace_ids) - 1:
                        st.session_state.current_run_id = trace_ids[current_idx + 1]
                        st.rerun()
            
            with col_prev:
                if st.button("← Prev", use_container_width=True):
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx > 0:
                        st.session_state.current_run_id = trace_ids[current_idx - 1]
                        st.rerun()
    else:
        st.info("Select a trace from the sidebar to begin annotation.")
```

- [ ] **Step 6: Remove old failure_mode_annotation_form function**

Delete the `failure_mode_annotation_form()` function (replace by new `annotation_form()`).

- [ ] **Step 7: Update imports if needed**

Verify imports at top of app_annotation.py. Remove any unused imports from deleted code.

- [ ] **Step 8: Test the app**

```bash
streamlit run app_annotation.py 2>&1 | head -30
```

Expected: App starts without errors, loads 91 traces, sidebar shows navigation

- [ ] **Step 9: Commit**

```bash
git add app_annotation.py
git commit -m "refactor: remove critique forms, add PASS/FAIL verdict, simplify annotation form"
```

---

### Task 4: Simplify Analysis Dashboard

**Files:**
- Modify: `app_annotation.py`

- [ ] **Step 1: Replace build_analysis_dashboard function**

Find and replace the entire `build_analysis_dashboard()` function with:

```python
def build_analysis_dashboard():
    """Build simplified analysis dashboard for Phase 1."""
    st.subheader("All Annotations")
    
    if not st.session_state.annotations:
        st.info("No annotations yet. Start with Annotation Interface to annotate traces.")
        return
    
    # Build dataframe
    rows = []
    for run_id, annotation in st.session_state.annotations.items():
        trace = st.session_state.traces.get(run_id)
        if trace:
            src_label = trace.inputs.get("source_patent", {}).get("label", "?")
            tgt_label = trace.inputs.get("target_patent", {}).get("label", "?")
            failure_modes = annotation.open_coded_failure_modes or []
            failure_modes_str = "; ".join(failure_modes) if failure_modes else "none"
            
            rows.append({
                "Run ID": run_id[:12] + "...",
                "Status": trace.status,
                "Source": src_label,
                "Target": tgt_label,
                "Verdict": annotation.verdict,
                "Failure Modes": failure_modes_str,
                "Comment": annotation.comment[:50] + "..." if annotation.comment else "",
                "Reviewed": "✅" if annotation.reviewed else "❌",
            })
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Failure mode frequency
    st.subheader("Failure Mode Frequency")
    all_modes = []
    for annotation in st.session_state.annotations.values():
        modes = annotation.open_coded_failure_modes or []
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
    verdicts = [a.verdict for a in st.session_state.annotations.values()]
    verdict_counts = Counter(verdicts)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("PASS", verdict_counts.get("PASS", 0))
    with col2:
        st.metric("FAIL", verdict_counts.get("FAIL", 0))
    
    # Export
    st.divider()
    st.subheader("Export")
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name="annotations_export.csv",
        mime="text/csv"
    )
```

- [ ] **Step 2: Verify dashboard is called**

Ensure the Analysis Dashboard view calls `build_analysis_dashboard()`:

```python
elif view == "Analysis Dashboard":
    build_analysis_dashboard()
```

- [ ] **Step 3: Test the app**

```bash
streamlit run app_annotation.py 2>&1 | head -30
```

Expected: App loads, both views accessible, no errors

- [ ] **Step 4: Commit**

```bash
git add app_annotation.py
git commit -m "refactor: simplify analysis dashboard for Phase 1 (failure modes + verdict)"
```

---

## Phase 3: Final Integration & Testing

### Task 5: Integration Test and Final Verification

**Files:**
- All files (read-only for testing)

- [ ] **Step 1: Run all tests**

```bash
pytest tests/test_annotation.py -v
```

Expected: 8 tests pass

- [ ] **Step 2: Verify app structure**

```bash
python -c "from app_annotation import *" && echo "App imports successfully"
```

Expected: No errors

- [ ] **Step 3: Manual checklist**

Verify in code (no need to run the app):
- [ ] `annotation_form()` function creates verdict, failure modes, comment inputs
- [ ] `save_annotation()` validates comment is required
- [ ] `build_analysis_dashboard()` shows failure mode frequency chart
- [ ] Sidebar filters work (PASS/FAIL, Reviewed/Unreviewed)
- [ ] Trace display shows full details
- [ ] CSV export available

- [ ] **Step 4: Verify data model**

Check in code:
- [ ] AnnotationRecord has: run_id, phase, open_coded_failure_modes, verdict, comment, reviewed, timestamp
- [ ] ElementJudgment removed
- [ ] OverallOpinionJudgment removed
- [ ] to_dict() and from_dict() only handle new fields

- [ ] **Step 5: Final commit summary**

```bash
git log --oneline -5
```

Expected: 3 commits from this task set:
1. "refactor: simplify AnnotationRecord - remove ElementJudgment and OverallOpinionJudgment"
2. "test: update tests for simplified AnnotationRecord"
3. "refactor: remove critique forms, add PASS/FAIL verdict, simplify annotation form"
4. "refactor: simplify analysis dashboard for Phase 1 (failure modes + verdict)"

- [ ] **Step 6: Create summary**

The Phase 1 annotation tool is now simplified:
- ✅ Data model: 7 fields (removed 2 classes)
- ✅ Annotation form: 3 inputs (verdict + failure modes + comment)
- ✅ Dashboard: failure mode frequency + verdict counts
- ✅ All tests passing
- ✅ Ready for local testing with Streamlit

---

## Spec Coverage Check

✅ **Section 1 (Overview):** Phase 1 focused on failure mode discovery - DONE (Task 3, 4)  
✅ **Section 3 (Data Model):** AnnotationRecord simplified, fields removed - DONE (Task 1, 2)  
✅ **Section 4 (Annotation Interface):** PASS/FAIL + failure modes + comment form - DONE (Task 3)  
✅ **Section 5 (Analysis Dashboard):** Failure mode frequency, verdict counts - DONE (Task 4)  
✅ **Testing:** Updated tests for new model - DONE (Task 2)  

---
