# PatentDiff Annotation Tool

A tool for systematic error analysis of PatentDiff traces through structured annotation.

## Overview

Supports two phases:
- **Phase 1**: Open coding — freely discover and label failure modes
- **Phase 3**: Re-annotation — standardize labels using a refined taxonomy

## Running the Tool

```bash
python -m app_unified.app   # then open http://127.0.0.1:8050/
```

Navigate to `/eval/traces` for the annotation interface.

## Features

- **Trace Navigator**: Search, filter by status/phase, progress tracking
- **Element-Level Critique**: Judge element novelty/inventive step verdicts
- **Overall Opinion Critique**: Judge final verdict
- **Multiple Failure Modes**: Tag traces with delimiter-separated modes
- **Analysis Dashboard**: Tabular view, frequency analysis, CSV export
- **Persistent Storage**: Auto-saves to traces/traces_annotations.jsonl

## Workflow

### Phase 1: Open Coding
1. Open app → Annotation Interface
2. Click trace in sidebar
3. Review element mappings and overall opinion  
4. Judge each element: PASS/FAIL + critique
5. Judge overall opinion: PASS/FAIL + critique
6. Tag failure modes: "hallucination | truncation"
7. Add annotation and click Save
8. Repeat for all 83 traces

### Phase 3: Re-annotation
Once failure_taxonomy.json exists:
1. Open annotation tool (auto-detects Phase 3)
2. Review traces with standardized modes from taxonomy
3. Save to update failure_modes field

## Files

- `app_unified/` — Unified Dash app (entry: `python -m app_unified.app`)
- `core/annotation.py` — Data models and persistence
- `core/trace_loader.py` — Trace loading
- `traces/traces_annotations.jsonl` — Annotation storage
- `traces/failure_taxonomy.json` — Refined modes (Phase 3)

## Data Model

Annotations stored in traces_annotations.jsonl:

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
