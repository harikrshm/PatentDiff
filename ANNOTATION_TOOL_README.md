# PatentDiff Annotation Tool

**Phase 1: Open Coding for Failure Mode Discovery**

A Streamlit-based web application for systematically annotating PatentDiff traces to discover and label failure modes through qualitative coding analysis.

## Overview

The annotation tool enables error analysis of PatentDiff traces through open coding:
- **Read** full trace details (source/target patents, claims, specifications, element mappings)
- **Identify** failure modes present in the trace
- **Mark** trace quality (PASS/FAIL) with justification
- **Analyze** patterns across all traces

This Phase 1 tool focuses on **failure mode discovery** without evaluating tool verdicts. Annotators read traces and mark what went wrong, providing the foundation for Phase 2 (clustering) and Phase 3 (standardized taxonomy).

## Quick Start

### Run the App

```bash
python -m streamlit run app_annotation.py
```

The app will open at `http://localhost:8501` with two views:
1. **Annotation Interface** — Annotate individual traces
2. **Analysis Dashboard** — View aggregate results

### Stop the App

Press `Ctrl+C` in the terminal.

## How to Use

### Annotation Interface

1. **Browse traces** in the sidebar:
   - Search by Run ID or comment text
   - Filter by Verdict (PASS/FAIL) or Reviewed status
   - Click a trace to load it

2. **Review the trace**:
   - **Left panel**: Full trace display
     - Source/Target patent claims and specifications (scrollable)
     - Element mappings (what the tool found)
     - Overall opinion (tool's conclusion)
   - Read everything carefully to understand what the tool did

3. **Annotate**:
   - **Verdict**: Mark PASS (correct) or FAIL (has issues)
   - **Failure Modes**: Enter failure modes separated by `|` (e.g., `hallucination | truncation | claim_mismatch`)
   - **Comment**: Explain the failure modes you identified
   - **Reviewed**: Check to mark as complete

4. **Save**: Click Save to store the annotation
   - Comment is required
   - FAIL verdicts should have at least one failure mode (warning if missing)

5. **Navigate**: Use Previous/Next buttons to move through traces

### Analysis Dashboard

View aggregate results across all annotated traces:

1. **Table**: All annotations with Run ID, Status, Patents, Verdict, Failure Modes, Comment
2. **Failure Mode Frequency**: Bar chart showing most common failure modes
3. **Verdict Summary**: Count of PASS vs FAIL traces
4. **Export**: Download as CSV for external analysis

## Data Model

### AnnotationRecord (7 fields)

```python
{
  "run_id": "16ff8d63-e84b-4ab7-9759-2acca62e69bb",
  "phase": 1,
  "open_coded_failure_modes": ["hallucination", "truncation"],
  "verdict": "FAIL",
  "comment": "Tool hallucinated correspondence in element 3. Also truncated spec causing missed context.",
  "reviewed": true,
  "timestamp": "2026-04-24T10:30:45+00:00"
}
```

**Fields:**
- `run_id`: Links to trace in traces.jsonl
- `phase`: 1 (Phase 1 open coding) or 3 (Phase 3 re-annotation)
- `open_coded_failure_modes`: List of discovered failure mode labels (free-form text)
- `verdict`: "PASS" or "FAIL" — trace quality assessment
- `comment`: Explanation of failure modes and verdict
- `reviewed`: Boolean — completion flag
- `timestamp`: ISO 8601 format, auto-generated on save

### Verdict Semantics

- **PASS**: Trace is correct overall. Tool performed as intended (may still have minor issues to note)
- **FAIL**: Trace has problems. Tool made mistakes or failed in meaningful ways

You can mark **PASS with failure modes** if minor issues don't affect overall correctness.

## File Structure

```
patentdiff/
├── app_annotation.py          # Main Streamlit app
├── core/
│   └── annotation.py          # Data model (AnnotationRecord)
├── traces.jsonl               # Input traces (read-only)
├── traces_annotations.jsonl   # Output annotations (created by app)
├── tests/
│   └── test_annotation.py     # Unit tests
└── ANNOTATION_TOOL_README.md  # This file
```

## Key Features

### Trace Display
- **Full specification text** with scrollable text areas
- **Independent claims** for both patents
- **Element mappings** showing what tool evaluated
- **Overall opinion** with tool's final verdict
- **Run metadata** (model, tokens, latency)

### Annotation Form
- **Verdict radio** (PASS/FAIL)
- **Failure modes input** with pipe delimiter (e.g., `hallucination | truncation`)
- **Comment textarea** for detailed explanation
- **Reviewed checkbox** for progress tracking

### Dashboard Analysis
- **Annotated traces table** with filtering and sorting
- **Failure mode frequency** visualization
- **Verdict breakdown** (PASS/FAIL counts)
- **CSV export** for downstream analysis

### Sidebar Navigation
- **Search** by run ID or comment text
- **Filters**: Verdict (All/PASS/FAIL), Reviewed (All/Reviewed/Unreviewed)
- **Progress bar** showing completion rate
- **Clickable trace list** sorted by review status

## Common Failure Modes

Examples to look for during annotation:

- **hallucination**: Tool claimed correspondence that doesn't exist
- **truncation**: Tool cut off important context (specification, claim text)
- **claim_mismatch**: Tool misread or misinterpreted claim language
- **missing_elements**: Tool failed to map all elements present
- **incorrect_verdict**: Tool marked novelty/inventive step wrong
- **incomplete_analysis**: Tool's reasoning was incomplete or superficial

Add your own as you discover patterns!

## Workflow

```
Phase 1: Open Coding (This Tool)
  ↓ Outputs: traces_annotations.jsonl with open_coded_failure_modes
Phase 2: Axial Coding (Jupyter Notebook)
  ↓ Clusters similar modes, produces failure_taxonomy.json
Phase 3: Re-annotation (This Tool, Phase 3 Mode)
  ↓ Re-annotate with standardized categories
Phase 4: Judge Building (Jupyter Notebook)
  ↓ Build evaluator prompt and coded judgments
Phase 5: Scale Evaluation (Python Script)
  ↓ Evaluate entire dataset with judge
```

## Technical Details

### Technology Stack
- **Framework**: Streamlit 1.28+
- **Data Model**: Pydantic BaseModel
- **Persistence**: JSON Lines format (one JSON object per line)
- **Storage**: traces_annotations.jsonl (created on first save)

### Data Persistence
- On app load: Reads traces_annotations.jsonl into memory
- On save: Appends/updates annotation record to file
- On delete: Removes from file
- Thread-safe: Session state prevents race conditions

### Performance
- Loads 83 traces on startup (~36MB traces.jsonl)
- Client-side filtering (search, verdict, reviewed status)
- No pagination needed for 83 traces

## Testing

Run unit tests:

```bash
python -m pytest tests/test_annotation.py -v
```

Expected: 7 tests pass
- test_load_empty_annotations
- test_load_annotations_from_jsonl
- test_load_traces_from_jsonl
- test_annotation_record_simplified
- test_parse_failure_modes
- test_annotation_to_dict_simplified
- test_annotation_from_dict_simplified

## Troubleshooting

### App won't start
```bash
python -m streamlit run app_annotation.py
```
(Not `python app_annotation.py`)

### No traces loading
Check that `traces.jsonl` exists in the project directory with valid JSON Lines format.

### Annotations not saving
Verify write permissions to the project directory. The app creates `traces_annotations.jsonl` on first save.

### Specification text not fully visible
Use the scrollbar in the specification text area to view full text. Height is 250px with scrolling enabled.

## Success Criteria (Phase 1)

- ✅ Annotate all 83 traces with verdict and failure modes
- ✅ Identify patterns in discovered failure modes
- ✅ Support simple PASS/FAIL quality assessment
- ✅ Export results for Phase 2 clustering
- ✅ All tests passing
- ✅ Ready for Streamlit deployment

## Next Steps

1. **Local Testing**: Run the app and annotate a few traces
2. **Phase 2**: Once Phase 1 complete, run Jupyter notebook for clustering
3. **Phase 3**: Use refined taxonomy for re-annotation
4. **Phase 4-5**: Build judge and scale to full dataset

## Questions?

Refer to the spec: `docs/superpowers/specs/2026-04-24-annotation-tool-phase1-simplified.md`

For implementation details, see: `docs/superpowers/plans/2026-04-24-annotation-tool-phase1-simplification.md`
