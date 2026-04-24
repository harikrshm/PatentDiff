# PatentDiff Annotation Tool — Design Specification

**Date:** 2026-04-24  
**Status:** Approved  
**Scope:** Phase 1 & 3 annotation tool for error analysis

---

## 1. Overview & Purpose

The annotation tool enables systematic error analysis of PatentDiff traces through qualitative coding:
- **Phase 1 (Open Coding):** Discover failure modes freely, annotate with unstructured labels
- **Phase 3 (Re-annotation):** Standardize labels using a refined taxonomy from Phase 2 clustering

This tool produces structured evaluation data that feeds into Phase 4 (judge building) and Phase 5 (scale evaluation).

**Success Criteria:**
- Annotate all 83 traces with element-level and overall-opinion judgments
- Capture multiple failure modes per trace with unified critique
- Export results for Phase 2 clustering analysis
- Support re-annotation with refined taxonomy

---

## 2. Architecture

### 2.1 Tech Stack
- **Framework:** Streamlit (matches existing PatentDiff app)
- **Language:** Python
- **Storage:** JSON Lines (traces_annotations.jsonl)

### 2.2 Components

**Single Streamlit App** (`app_annotation.py`) with two views:

1. **Annotation Interface** — per-trace judgment capture
   - Sidebar: trace navigator with search/filtering
   - Main panel: full trace display + annotation form
   
2. **Analysis Dashboard** — aggregate view of all traces
   - Tabular display with sorting, filtering
   - Frequency analysis by failure mode
   - Export to CSV

### 2.3 Persistent Storage

**File:** `traces_annotations.jsonl` (one JSON object per line)

```json
{
  "run_id": "16ff8d63-e84b-4ab7-9759-2acca62e69bb",
  "phase": 1,
  "element_judgments": [
    {
      "element_number": 1,
      "tool_novelty": true,
      "tool_inventive_step": true,
      "your_verdict": "PASS",
      "critique": "Correct correspondence and verdicts."
    },
    {
      "element_number": 2,
      "tool_novelty": false,
      "tool_inventive_step": true,
      "your_verdict": "FAIL",
      "critique": "Tool missed key distinction in claim language."
    }
  ],
  "overall_opinion_judgment": {
    "tool_verdict": "Patents are substantially similar...",
    "your_verdict": "FAIL",
    "critique": "Overall opinion contradicts element-level findings. Elements 1-3 pass, but tool concludes overall similarity."
  },
  "open_coded_failure_modes": ["hallucination", "truncation"],
  "failure_modes": null,
  "annotation": "Tool hallucinated correspondence in element 3. Also truncated spec causing missed context in element 2.",
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

### 3.1 Core Fields

| Field | Type | Phase 1 | Phase 3 | Notes |
|-------|------|---------|---------|-------|
| `run_id` | string | Required | Required | Links to trace in traces.jsonl |
| `phase` | int | 1 | 3 | Indicates coding phase |
| `element_judgments` | list | Required | Required | One judgment per element |
| `overall_opinion_judgment` | object | Required | Required | Verdict for full analysis |
| `open_coded_failure_modes` | list | Required | Optional | Free-form labels (Phase 1) |
| `failure_modes` | list | null | Required | Standardized categories (Phase 3) |
| `annotation` | string | Required | Required | Unified critique covering all modes |
| `reviewed` | bool | Required | Required | Completion flag |
| `timestamp` | string | Auto | Auto | ISO 8601 format |

### 3.2 Element Judgment Structure

```json
{
  "element_number": 1,
  "tool_novelty": true,
  "tool_inventive_step": false,
  "your_verdict": "PASS" | "FAIL",
  "critique": "Text explaining the verdict"
}
```

### 3.3 Overall Opinion Judgment Structure

```json
{
  "tool_verdict": "Full text of tool's opinion",
  "your_verdict": "PASS" | "FAIL",
  "critique": "Text explaining the verdict"
}
```

---

## 4. User Interface

### 4.1 Annotation Interface

**Layout:** Sidebar + Main panel

#### **Left Sidebar (Trace Navigator)**
- **Search bar:** Filter by run_id, annotation text
- **Filter options:**
  - Reviewed: [All | Reviewed | Unreviewed]
  - Phase: [All | Phase 1 | Phase 3]
  - Failure Mode: [dropdown of all existing modes]
- **Trace list:**
  - Clickable entries showing: run_id, source/target labels
  - Visual indicators:
    - ✅ reviewed
    - ⭕ open-coded (Phase 1)
    - 🔹 standardized (Phase 3)
  - Sorted by review status (unreviewed first)
- **Progress bar:** "Reviewed 23/83 traces"

#### **Right Panel (Annotation Form)**

**Section 1: Trace Metadata** (read-only)
```
Run ID: 16ff8d63-e84b-4ab7-9759-2acca62e69bb
Status: success | error
Source Patent: US20250225337A1 vs US9876543B1
Analysis Date: 2026-04-19T06:40:40
```

**Section 2: Trace Display** (scrollable, read-only)
- Source patent (label, independent claim, specification)
- Target patent (label, independent claim, specification)
- LLM response metadata (model, tokens, latency)
- Element mappings (table format)
- Overall opinion text

**Section 3: Element-Level Critique**
```
Element Selector: [Dropdown: 1, 2, 3, ...]

Element Text: [Read-only display]
Corresponding Text in Patent B: [Read-only display]

TOOL'S VERDICTS:
  Novelty: [Y/N]
  Inventive Step: [Y/N]
  Verdict: [Text display]

YOUR JUDGMENT:
  Pass/Fail: [PASS | FAIL] (radio buttons)
  Critique: [Text area]
  
[ ] Reviewed (checkbox)
```

**Section 4: Overall Opinion Critique**
```
TOOL'S VERDICT: [Full text display, scrollable]

YOUR JUDGMENT:
  Pass/Fail: [PASS | FAIL] (radio buttons)
  Critique: [Text area]
  
[ ] Reviewed (checkbox)
```

**Section 5: Phase-Specific Annotation**

**Phase 1 Mode:**
```
Open-Coded Failure Modes: [Text input]
  Format: "hallucination | truncation | claim_mismatch"
  
Annotation/Critique: [Text area]
  "Describe all failure modes found in this trace..."
```

**Phase 3 Mode:**
```
Failure Modes (from taxonomy): [Text input with delimiters]
  Format: "hallucination | truncation"
  
Annotation/Critique: [Text area]
  "Explain why these modes apply to this trace..."
```

**Section 6: Actions**
```
[← PREVIOUS] [NEXT →] [SAVE]
```

---

### 4.2 Analysis Dashboard

**Table View:**

| Run ID | Status | Source | Target | Open-Coded Modes | Standardized Modes | Your Verdict | Reviewed | Actions |
|--------|--------|--------|--------|------------------|--------------------|--------------|----------|---------|
| 16ff8d63... | success | US202... | US987... | hallucination, truncation | — | FAIL | ✅ | [Edit] |
| 2f7e9c4a... | error | US201... | US988... | claim_mismatch | — | FAIL | ❌ | [Edit] |

**Features:**
- Sortable columns (click header)
- Filterable by: status, verdict, reviewed, failure mode
- Clickable run_id → jumps to annotation interface
- Export button → CSV (selected or all rows)

**Frequency Panel** (collapsible):
```
FAILURE MODE BREAKDOWN:
  hallucination: 18 traces
  truncation: 12 traces
  claim_mismatch: 8 traces
  ...

VERDICT SUMMARY:
  PASS: 12 traces
  FAIL: 71 traces
```

---

## 5. Phase-Specific Behavior

### 5.1 Phase 1 (Open Coding)

**UI Mode:**
- Failure modes field: text input with delimiter (user discovers modes freely)
- Failure modes field label: "Open-Coded Failure Modes"
- No dropdown/taxonomy dependency

**Data Storage:**
- `open_coded_failure_modes`: list (parsed from delimited text)
- `failure_modes`: null
- `phase`: 1

**Workflow:**
1. Load traces (83 total)
2. Annotate each with element judgments + overall verdict
3. Tag with free-form failure modes (e.g., "hallucination | truncation")
4. Mark reviewed
5. Save → output: traces_annotations.jsonl

**Output Use:**
- Exported to Phase 2 (Jupyter notebook) for clustering
- Notebook clusters similar modes into refined taxonomy

### 5.2 Phase 3 (Re-annotation with Taxonomy)

**Startup Logic:**
- Check if `failure_taxonomy.json` exists
- If yes: enable Phase 3 mode, show dropdown
- If no: stay in Phase 1 mode

**UI Mode:**
- Failure modes field: text input with delimiter
- Failure modes field label: "Failure Modes (from taxonomy)"
- Modes are constrained to taxonomy entries
- Can use delimiters to assign multiple modes

**Data Storage:**
- `open_coded_failure_modes`: preserved (unchanged from Phase 1)
- `failure_modes`: list (parsed from delimited text, constrained to taxonomy)
- `phase`: 3

**Workflow:**
1. Load taxonomy from failure_taxonomy.json
2. Reload all traces_annotations.jsonl
3. For each trace: review Phase 1 annotation, re-tag with standardized modes
4. Mark reviewed
5. Save → output: updated traces_annotations.jsonl with Phase 3 data

---

## 6. Workflow & Data Flow

### 6.1 Full Analysis Pipeline (5 Phases)

```
Phase 1: Open Coding
  ↓ Output: traces_annotations.jsonl (open_coded_failure_modes)
Phase 2: Axial Coding (Jupyter)
  ↓ Output: failure_taxonomy.json
Phase 3: Re-annotation
  ↓ Output: traces_annotations.jsonl (failure_modes standardized)
Phase 4: Judge Building (Jupyter)
  ↓ Output: judge_prompt.txt, coded_evals.py
Phase 5: Scale Evaluation (Python script)
  ↓ Output: final_error_report.json
```

### 6.2 Annotation Interface Workflow (Phase 1)

1. User opens app → Annotation Interface view
2. Sidebar loads all traces from traces.jsonl
3. User clicks trace in sidebar
4. Main panel displays full trace (scrollable)
5. User reviews element mappings → judges each element (PASS/FAIL + critique)
6. User scrolls to overall opinion → judges final verdict
7. User enters failure modes (delimited text): "hallucination | truncation"
8. User enters annotation (unified critique)
9. User marks "Reviewed" checkbox
10. User clicks "SAVE" → writes to traces_annotations.jsonl
11. Next trace (click NEXT or sidebar)
12. Repeat for all 83 traces

---

## 7. Technical Considerations

### 7.1 Performance

- **Load Time:** Load traces.jsonl (91 records, ~36MB) into memory on startup
- **Pagination:** Not needed for 83 traces (acceptable to show all in sidebar)
- **Search:** Client-side filtering (Streamlit native)

### 7.2 Data Integrity

- **Append vs. Overwrite:** Each save appends/updates record in traces_annotations.jsonl
- **Backup:** Consider auto-backup of traces_annotations.jsonl before each session
- **Conflict:** If same trace edited in two sessions, last write wins

### 7.3 Phase Transitions

- **Phase 1 → Phase 2:** Export traces_annotations.jsonl, run Jupyter notebook separately
- **Phase 2 → Phase 3:** Notebook outputs failure_taxonomy.json → app detects and enables Phase 3 UI
- **Phase 3:** Existing annotations preserved; phase field incremented to 3

### 7.4 Error Handling

- **Missing trace:** If run_id not in traces.jsonl, show error in sidebar
- **Invalid JSON:** Graceful error on parse failure, skip malformed records
- **Filesystem:** Handle traces_annotations.jsonl missing on startup (create empty)

---

## 8. Success Criteria

- ✅ All 83 traces annotated with element-level and overall judgments
- ✅ Multiple failure modes per trace captured with unified critique
- ✅ Phase 1 output ready for Phase 2 clustering
- ✅ Phase 3 re-annotation with taxonomy works smoothly
- ✅ Analysis dashboard shows frequency of failure modes
- ✅ Export to CSV for external analysis

---

## 9. Out of Scope

- Phase 2 (Jupyter notebook for clustering) — separate tool
- Phase 4 (Judge building) — separate notebook
- Phase 5 (Scale evaluation script) — separate script
- User authentication — not needed for local tool
- Audit trail — not capturing edit history (Phase 3 overwrites Phase 1)

---

## 10. Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| Single Streamlit app vs. separate tools | Consistent with existing PatentDiff setup, simple to deploy |
| Sidebar navigator + main panel | Familiar dual-pane UI, efficient for browsing 83 traces |
| Delimiter-based multiple modes | Simple text input, no special UI needed, easy to parse |
| One critique per trace | Avoid redundancy; critique can reference multiple modes |
| Phase field in data | Tracks which coding round each annotation belongs to |
| Preserved open_coded_failure_modes in Phase 3 | Maintains traceability; can compare original vs. refined |
| Separate traces_annotations.jsonl | Keeps original traces.jsonl clean; annotations are mutable |

---
