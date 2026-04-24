# PatentDiff Annotation Tool — Phase 1 Simplified Design

**Date:** 2026-04-24  
**Status:** Approved  
**Scope:** Phase 1 annotation tool for failure mode discovery (simplified)

---

## 1. Overview & Purpose

**Phase 1 Focus:** Discover and label failure modes from traces through open coding.

The simplified annotation tool enables systematic exploration of PatentDiff traces to identify what failure modes exist. Annotators read traces and mark failure modes without evaluating tool performance.

**Workflow:**
1. Read a trace (view full details)
2. Identify failure modes present
3. Mark PASS (correct) or FAIL (has issues)
4. Add a comment explaining the failure modes
5. Save and move to next trace

**Success Criteria:**
- Annotate all 83 traces with failure modes discovered through reading
- Identify patterns in failure modes for later taxonomy building
- Support simple PASS/FAIL quality assessment
- Export results for Phase 2 clustering analysis

---

## 2. Architecture

### 2.1 Tech Stack
- **Framework:** Streamlit (existing setup)
- **Language:** Python
- **Storage:** JSON Lines (traces_annotations.jsonl)

### 2.2 Components

**Single Streamlit App** (`app_annotation.py`) with two views:

1. **Annotation Interface** — per-trace failure mode discovery
   - Sidebar: trace navigator with search/filtering
   - Main panel: full trace display + simplified annotation form
   
2. **Analysis Dashboard** — aggregate view of failure modes
   - Trace list with failure modes and verdicts
   - Failure mode frequency analysis
   - Export to CSV

### 2.3 Data Persistence

**File:** `traces_annotations.jsonl` (one JSON object per line)

```json
{
  "run_id": "16ff8d63-e84b-4ab7-9759-2acca62e69bb",
  "phase": 1,
  "open_coded_failure_modes": ["hallucination", "truncation"],
  "verdict": "FAIL",
  "comment": "Tool hallucinated correspondence in element 3. Also truncated spec causing missed context.",
  "reviewed": true,
  "timestamp": "2026-04-24T10:30:45.123456+00:00"
}
```

**Read/Write Strategy:**
- On app startup: load traces_annotations.jsonl into memory (dict keyed by run_id)
- On save: write updated record back to file, append if new
- On delete: remove from file

---

## 3. Data Model

### 3.1 AnnotationRecord (Simplified)

```python
class AnnotationRecord:
    run_id: str                          # Links to trace in traces.jsonl
    phase: int = 1                       # Phase identifier
    open_coded_failure_modes: List[str]  # Free-form failure mode labels
    verdict: str                         # "PASS" or "FAIL" (trace quality)
    comment: str                         # Explanation of failure modes
    reviewed: bool = False               # Completion flag
    timestamp: str                       # ISO 8601 format
```

### 3.2 Removed Fields (vs. Original Design)

The following fields have been removed for Phase 1 simplicity:

- `element_judgments` — no element-level critiques needed
- `overall_opinion_judgment` — not evaluating tool verdicts in Phase 1
- `failure_modes` — reserved for Phase 3 (standardized taxonomy)
- `annotation` — renamed to `comment` for clarity

### 3.3 Verdict Semantics

- **PASS:** Trace is correct, tool performed well (may still have minor failure modes to note)
- **FAIL:** Trace has issues, tool made mistakes or failed in some way

Note: Annotators can mark PASS with failure modes if issues are minor and don't affect overall correctness.

---

## 4. Annotation Interface

### 4.1 Layout

Two-column layout:
- **Left:** Trace navigator sidebar (scrollable)
- **Right:** Trace display + annotation form

### 4.2 Sidebar (Trace Navigator)

**Search & Filter Section:**
- Search bar: filter by run_id or comment text
- Verdict filter: [All | PASS | FAIL]
- Reviewed filter: [All | Reviewed | Unreviewed]

**Progress Tracking:**
- Progress bar: visual representation of completion
- Caption: "Reviewed 23/83 traces"

**Trace List:**
- Clickable entries showing: status icon (✅/⭕), source patent label
- Sorted by review status (unreviewed first)
- Visual feedback on selection

### 4.3 Main Panel (Annotation Form)

**Section 1: Trace Metadata** (read-only)
```
Run ID: 16ff8d63-e84b-4ab7...
Status: success | error
Source: US20250225337A1 vs US9876543B1
Timestamp: 2026-04-19
```

**Section 2: Trace Display** (read-only, scrollable)
- Source patent (label, independent claim, specification preview)
- Target patent (label, independent claim, specification preview)
- Element mappings (expandable sections showing novelty/inventive step verdicts)
- Overall opinion (full text)
- Run metadata (model, tokens, latency)

**Section 3: Annotation Form**

```
TRACE QUALITY VERDICT:
  ⭕ PASS    ⭕ FAIL

FAILURE MODES:
  [Text input]
  Format: "hallucination | truncation | claim_mismatch"

COMMENT:
  [Text area, 150px height]
  "Explain what failure modes you found and why..."

[✓] Reviewed

[← PREVIOUS] [SAVE] [NEXT →]
```

### 4.4 Form Behavior

- **Failure Modes:** Delimiter-separated text (pipe character |)
  - Parsed on save: split by |, trim whitespace, remove empty strings
  - Stored as list in JSON

- **Comment:** Free-form text explaining all failure modes found

- **Reviewed:** Checkbox indicating completion

- **Navigation:**
  - Save: commits annotation to file, shows success message
  - Next: saves current, navigates to next unreviewed trace
  - Previous: saves current, navigates to previous trace

- **Error Handling:**
  - If comment is empty: show error "Please add a comment"
  - If no failure modes and verdict is FAIL: warn "FAIL verdict but no failure modes noted?"
  - If save fails: show error message, don't navigate

---

## 5. Analysis Dashboard

### 5.1 Tabular View

**Columns:**
- Run ID (first 12 chars + ...)
- Status (success/error)
- Source Label
- Target Label
- Failure Modes (delimited list or "none")
- Verdict (PASS/FAIL)
- Comment (preview, first 50 chars + ...)
- Reviewed (✅/❌)

**Features:**
- Sortable by any column
- Filterable by: verdict (PASS/FAIL), reviewed status
- Clickable run_id → jumps to annotation interface

### 5.2 Failure Mode Frequency Analysis

**Bar Chart:**
- X-axis: Failure mode names
- Y-axis: Count of traces with that mode
- Sorted descending by count

**Table:**
- Columns: Failure Mode, Count
- Shows all modes discovered across all traces

### 5.3 Verdict Summary

**Metrics:**
- PASS: [count]
- FAIL: [count]

### 5.4 Export

**CSV Download:**
- Exports current table (filtered/sorted as shown)
- Filename: `annotations_export.csv`
- Includes all columns

---

## 6. Phase Detection & Compatibility

**Phase 1 Mode:**
- Always runs in Phase 1 (no taxonomy.json check needed for Phase 1)
- Data model is simplified (no element/overall judgments)
- UI shows only failure modes + comment form

**Future Phase 3:**
- Will use different data model/UI (separate implementation)
- Will load taxonomy.json and offer standardized mode dropdown
- Will re-annotate traces with refined categories

**No cross-phase concerns in Phase 1 implementation.**

---

## 7. Error Handling & Validation

**On App Startup:**
- Try/catch around trace loading — graceful error if traces.jsonl missing
- Try/catch around annotation loading — default to empty dict if file missing
- Show user-friendly error messages, don't crash

**On Save:**
- Validate comment is not empty (required)
- Validate failure modes input (can be empty, but warn if FAIL verdict with no modes)
- Catch file I/O errors and show message
- Commit timestamp on save

**On Navigation:**
- Handle edge cases (first/last trace)
- Show info message if no more traces ahead/behind
- Gracefully handle missing trace data

---

## 8. Success Criteria Validation

✅ **All 83 traces annotatable:** Simple form with low friction  
✅ **Failure mode discovery:** Text input with delimiter parsing allows flexible discovery  
✅ **Pattern identification:** Frequency analysis shows which modes are common  
✅ **Quality assessment:** PASS/FAIL verdict provides simple quality signal  
✅ **Export for Phase 2:** CSV export ready for clustering analysis  

---

## 9. Out of Scope

- Phase 2 (Jupyter notebook for clustering) — separate tool
- Phase 3 (re-annotation with taxonomy) — separate implementation
- Phase 4 (judge building) — separate notebook
- User authentication — local tool only
- Audit trail/edit history — not tracking changes

---

## 10. Implementation Notes

**Data Model Changes:**
- Simplify AnnotationRecord: remove ElementJudgment, OverallOpinionJudgment
- Update from_dict/to_dict serialization
- Update tests for simplified model

**UI Changes:**
- Remove element critique form (entire section gone)
- Remove overall opinion critique form (entire section gone)
- Add PASS/FAIL verdict radio/toggle
- Rename `annotation` field to `comment` in form label
- Simplify annotation form to 3 fields: verdict, failure modes, comment

**Dashboard Changes:**
- Remove PASS/FAIL verdict counts (just show as metric)
- Simplify table columns
- Keep frequency analysis (main insight)
- Keep CSV export

---
