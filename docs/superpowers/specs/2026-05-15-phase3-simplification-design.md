# Phase 3 Re-annotation Simplification Design
**Date:** 2026-05-15  
**Author:** Claude Code  
**Status:** Approved

## Context & Motivation

The Phase 3 taxonomy currently has 5 failure modes, but based on analysis and feedback, only 2 are critical for the re-annotation effort:
1. **Absent PHOSITA Reasoning** - Captures weak mental model of person skilled in the art
2. **Citation Text** - Captures tool's tendency to summarize rather than quote verbatim

Starting fresh allows the team to focus exclusively on these 2 failure modes without noise from the other 3. This requires:
- Updating the taxonomy to 2 modes only
- Clearing all existing Phase 3 annotations
- Preserving old annotations as backup
- Updating the annotation UI to show only 2 failure modes
- Updating the dashboard to reflect the simplified taxonomy

## Design Overview

### 1. Taxonomy Update

**File:** `failure_taxonomy.json`

Replace current 5-mode taxonomy with 2-mode taxonomy:

```json
{
  "phase": 3,
  "date_created": "2026-05-15",
  "methodology": "Axial Coding - 2-Category Focused Taxonomy",
  "failure_categories": [
    {
      "id": "absent_phosita_reasoning",
      "name": "Absent PHOSITA Reasoning",
      "description": "Mental model of person skilled in the art is weak"
    },
    {
      "id": "citation_text",
      "name": "Citation Text",
      "description": "Tool summarizes prior art instead of quoting verbatim"
    }
  ]
}
```

**Removed categories:**
- Failed Claim Construction (id: failed_claim_construction)
- Inconsistent Verdict Logic (id: inconsistent_verdict)
- Claim Elements Evaluated Unnecessarily (id: unnecessary_evaluation)

### 2. Data Migration & Fresh Start

**Files affected:**
- `traces_annotations.jsonl` (cleared for fresh start)
- `traces_annotations.jsonl.backup.2026-05-15` (archival backup)

**Migration steps:**
1. Create timestamped backup: `traces_annotations.jsonl` → `traces_annotations.jsonl.backup.2026-05-15`
2. Create fresh empty `traces_annotations.jsonl`
3. New annotations will be added to fresh file as annotators work

**AnnotationRecord structure (unchanged):**
```python
class AnnotationRecord(BaseModel):
    run_id: str
    phase: int  # 3
    failure_modes: Optional[List[str]] = None  # Will only contain 2 possible IDs
    verdict: str  # "PASS" or "FAIL"
    comment: str  # Starts empty, filled by annotators
    reviewed: bool = False  # Kept for marking reviewed traces
    timestamp: str  # Auto-generated
    dimensions: Optional[Dict[str, str]]
```

No model changes needed—validation naturally works with 2-mode list.

### 3. Annotation Interface Updates

**File:** `app_annotation.py` - `annotation_form()` function (Phase 3 branch)

**Form changes:**
1. When verdict = PASS:
   - Show message: "✓ PASS verdict: no failure modes applicable"
   - Comment box (optional)
   - Reviewed checkbox

2. When verdict = FAIL:
   - Display 2-mode multi-select (required, at least 1 must be selected):
     - ☐ Absent PHOSITA Reasoning
     - ☐ Citation Text
   - Comment box (for critique/explanation)
   - Reviewed checkbox
   - Show warning if FAIL selected but no modes chosen

**Validation logic:**
- PASS → no failure modes allowed
- FAIL → require at least 1 of 2 failure modes
- Comment field optional for both, but recommended for FAIL

**Code removals:**
- Remove references to 3 old failure modes
- Remove conditional logic for old categories
- Keep reviewed field and button (NOT removed)

### 4. Analysis Dashboard Updates

**File:** `app_annotation.py` - `build_analysis_dashboard()` function

**Dashboard displays (fresh start):**

1. **Annotations Table:**
   - Run ID (truncated)
   - Status (success/error from trace)
   - Verdict (PASS/FAIL)
   - Failure Modes (shows selected modes: "absent_phosita_reasoning; citation_text" or "none")
   - Comment preview (first 50 chars)
   - Reviewed status (✅/❌)

2. **Failure Mode Frequency Chart:**
   - Bar chart showing only 2 modes (initially empty)
   - Updates as annotations are added
   - Shows count for each mode across all FAIL verdicts

3. **Verdict Summary:**
   - Metric: PASS count
   - Metric: FAIL count
   - Progress indicator: % of traces reviewed

4. **Export:**
   - CSV download of all annotations (with 2 modes only)

**Initial state (fresh start):**
- 0 PASS / 0 FAIL
- No data in frequency chart
- Empty table (no annotations yet)
- Dashboard populates dynamically as annotators save

## Implementation Scope

**Files to modify:**
1. `failure_taxonomy.json` - replace content
2. `traces_annotations.jsonl` - create backup, start fresh
3. `app_annotation.py` - update Phase 3 form & dashboard logic

**Files unchanged:**
- `core/annotation.py` - no model changes needed
- `core/trace_loader.py` - no changes
- Phase 1 annotation flow - completely unchanged

**New artifacts:**
- `traces_annotations.jsonl.backup.2026-05-15` - archival backup

## Testing & Verification

1. **Taxonomy loading:**
   - Load `failure_taxonomy.json` in app
   - Verify only 2 modes appear in Phase 3 form

2. **Annotation flow:**
   - Select FAIL verdict
   - Verify 2-mode checkboxes appear (not 5)
   - Test validation (FAIL without mode selection = error)
   - Save annotation with both modes selected
   - Verify it saves and appears in dashboard

3. **Dashboard:**
   - Load Analysis Dashboard
   - Verify frequency chart shows only 2 modes
   - Verify verdict counts start at 0/0
   - Save 3 traces (2 FAIL, 1 PASS) with various modes
   - Verify dashboard updates correctly

4. **Backup integrity:**
   - Verify old annotations exist in `.backup` file
   - Verify can restore from backup if needed

## Success Criteria

- ✅ Only 2 failure modes appear in Phase 3 annotation form
- ✅ Old annotations preserved in backup file
- ✅ Fresh annotations file empty and ready for new data
- ✅ Dashboard shows only 2 failure modes in all visualizations
- ✅ Reviewed field and button retained (not removed)
- ✅ Comment field cleared and ready for new critiques
- ✅ Validation works for PASS/FAIL with 2-mode constraints
- ✅ No breaking changes to AnnotationRecord or core models
