# Phase 3 Re-annotation Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify Phase 3 taxonomy to 2 failure modes, backup old annotations, create fresh start, and update annotation UI to reflect the simplified taxonomy.

**Architecture:** 
- Update taxonomy file to contain only 2 failure modes (absent_phosita_reasoning, citation_text)
- Backup existing annotations and create fresh empty file to start clean
- Modify app_annotation.py to dynamically load only 2 modes in the Phase 3 form
- Update analysis dashboard to show stats for only 2 modes
- No breaking changes to AnnotationRecord model

**Tech Stack:** Python/Streamlit, Pydantic, JSON

---

## Task 1: Backup and Reset Annotation Files

**Files:**
- Modify: `traces/traces_annotations.jsonl`

- [ ] **Step 1: Create timestamped backup of current annotations**

```bash
cd C:\Users\91978\patentdiff
$timestamp = Get-Date -Format "yyyy-MM-dd"
Copy-Item -Path "traces\traces_annotations.jsonl" -Destination "traces\traces_annotations.jsonl.backup.$timestamp"
```

Expected: `traces_annotations.jsonl.backup.2026-05-15` created alongside original file with identical content.

- [ ] **Step 2: Clear the annotations file for fresh start**

```bash
# Create an empty JSONL file (no header, just empty)
"" | Set-Content -Path "traces\traces_annotations.jsonl" -Encoding UTF8
```

Expected: `traces_annotations.jsonl` is now empty (0 bytes or minimal whitespace).

- [ ] **Step 3: Verify backup exists and is readable**

```bash
# Check backup size (should be > 0)
(Get-Item "traces\traces_annotations.jsonl.backup.$timestamp").Length
# Check original is empty
(Get-Item "traces\traces_annotations.jsonl").Length
```

Expected: Backup file shows size > 0, original file shows size ≈ 0.

- [ ] **Step 4: Commit**

```bash
git add traces/traces_annotations.jsonl traces/traces_annotations.jsonl.backup.2026-05-15
git commit -m "backup: save Phase 3 annotations before taxonomy simplification"
```

---

## Task 2: Update Failure Taxonomy

**Files:**
- Modify: `failure_taxonomy.json`

- [ ] **Step 1: Read current taxonomy file**

```bash
type C:\Users\91978\patentdiff\failure_taxonomy.json
```

Expected: JSON with 5 failure_categories (Failed Claim Construction, Absent PHOSITA Reasoning, Citation Text, Inconsistent Verdict, Unnecessary Evaluation).

- [ ] **Step 2: Replace taxonomy with 2-mode version**

Use the Read and Edit tools to update the file:

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

Removed categories: failed_claim_construction, inconsistent_verdict, unnecessary_evaluation.

- [ ] **Step 3: Verify the taxonomy file loads in Python**

```bash
python -c "import json; tax = json.load(open('failure_taxonomy.json')); print(f'Phase {tax[\"phase\"]}, {len(tax[\"failure_categories\"])} modes'); [print(f'  - {c[\"id\"]}: {c[\"name\"]}') for c in tax['failure_categories']]"
```

Expected output:
```
Phase 3, 2 modes
  - absent_phosita_reasoning: Absent PHOSITA Reasoning
  - citation_text: Citation Text
```

- [ ] **Step 4: Commit**

```bash
git add failure_taxonomy.json
git commit -m "refactor: simplify Phase 3 taxonomy to 2 failure modes"
```

---

## Task 3: Update Phase 3 Annotation Form in app_annotation.py

**Files:**
- Modify: `app_annotation.py:183-251` (annotation_form function, Phase 3 branch)

- [ ] **Step 1: Read the Phase 3 form section**

Read `app_annotation.py` lines 183-251 to understand current structure:
- Phase 3 branch that loads taxonomy
- Multi-select for failure_categories
- Maps category names back to IDs

- [ ] **Step 2: Verify the form still uses same variables and logic**

The form should:
- Load `st.session_state.taxonomy` (dict with failure_categories list)
- Build `failure_categories` dict: `{cat['id']: cat['name']}`
- Build `category_names` list: `[cat['name'] for cat in ...]`
- Show multi-select with `category_names`
- Map selected names back to IDs

Since we're only changing the taxonomy file, the form logic remains identical. Verify this is true by reading the function.

- [ ] **Step 3: Test form logic with 2-mode taxonomy**

The form function receives `st.session_state.taxonomy` which is now loaded from the updated `failure_taxonomy.json`. No code changes needed — the form will automatically display only 2 modes because the JSON now contains only 2 categories.

To verify this works, we'll test it in Task 5 (manual UI test).

- [ ] **Step 4: No code changes needed for this task**

The Phase 3 form logic (lines 183-251) is generic and reads from the taxonomy file. Since we've updated the taxonomy to 2 modes, the form will automatically show only 2 modes in the multi-select. No code edits required.

Document this in a comment:

```python
# Note: Phase 3 form dynamically loads failure_categories from failure_taxonomy.json
# After taxonomy update to 2 modes, multi-select will show only 2 options:
# - absent_phosita_reasoning
# - citation_text
# (No code changes needed — form adapts to taxonomy)
```

- [ ] **Step 5: Verify no syntax errors**

```bash
python -m py_compile app_annotation.py
```

Expected: No output (success).

- [ ] **Step 6: Commit (if any changes made)**

If no changes were needed:
```bash
# No commit needed — taxonomy change in Task 2 automatically updates form behavior
```

---

## Task 4: Update Analysis Dashboard in app_annotation.py

**Files:**
- Modify: `app_annotation.py:303-373` (build_analysis_dashboard function)

- [ ] **Step 1: Read the dashboard function**

Read `app_annotation.py` lines 303-373 to understand:
- How it builds the annotations table (rows from st.session_state.annotations)
- How it displays failure_modes (from `annotation.open_coded_failure_modes` for Phase 1, or `annotation.failure_modes` for Phase 3)
- How it calculates frequency (Counter on all_modes)
- How it displays verdict summary

- [ ] **Step 2: Understand the data flow**

The dashboard displays annotations from `st.session_state.annotations`. When Phase 3 is selected, the form saves records with:
- `phase: 3`
- `failure_modes: List[str]` (contains 0, 1, or 2 IDs)

For Phase 3 records, the dashboard will automatically show only the failure modes in the list. Since the list now only contains IDs from the 2-mode taxonomy, the frequency chart will only show those 2 modes.

- [ ] **Step 3: Verify dashboard works with fresh annotations**

The dashboard logic doesn't hardcode the failure modes — it iterates over `annotation.failure_modes` (Phase 3) or `annotation.open_coded_failure_modes` (Phase 1).

With the fresh empty `traces_annotations.jsonl`:
- No annotations exist initially
- Dashboard will show:
  - Empty table ("No annotations yet" message will appear if filtered to empty)
  - Failure Mode Frequency: empty (no modes to count)
  - Verdict Summary: 0 PASS, 0 FAIL

As annotators add records, the dashboard will populate dynamically.

- [ ] **Step 4: No code changes needed**

The dashboard is mode-agnostic. It reads whatever failure_modes are in the annotations. Since we're using the new 2-mode taxonomy, it will automatically display only those 2 modes. No code edits required.

Add a documentation comment:

```python
# Note: Dashboard displays failure modes from annotations
# With Phase 3 simplified to 2 modes, frequency chart will show only:
# - absent_phosita_reasoning
# - citation_text
# (No code changes needed — dashboard adapts to saved data)
```

- [ ] **Step 5: Verify no syntax errors**

```bash
python -m py_compile app_annotation.py
```

Expected: No output (success).

- [ ] **Step 6: Commit (if any changes made)**

If no changes were needed:
```bash
# No commit needed — form and dashboard are mode-agnostic
```

---

## Task 5: Manual Integration Test - Annotation Flow

**Files:**
- Test: Manual UI test in Streamlit app

- [ ] **Step 1: Start the annotation tool**

```bash
cd C:\Users\91978\patentdiff
python -m streamlit run app_annotation.py
```

Expected: Streamlit app starts and serves at http://localhost:8501

- [ ] **Step 2: Verify Phase 3 form shows only 2 failure modes**

1. In sidebar, select Phase 3 under "Phase Selection"
2. In main area, select a trace to annotate
3. In annotation form, select verdict = FAIL
4. Look at "FAILURE MODES:" multi-select

Expected: Multi-select shows exactly 2 options:
- Absent PHOSITA Reasoning
- Citation Text

NOT showing: Failed Claim Construction, Inconsistent Verdict Logic, Claim Elements Evaluated Unnecessarily

- [ ] **Step 3: Test FAIL annotation with 1 failure mode**

1. Select FAIL verdict
2. Check "Absent PHOSITA Reasoning" (leave Citation Text unchecked)
3. Enter comment: "Test annotation - PHOSITA mode"
4. Click "Reviewed" checkbox
5. Click "💾 Save"

Expected: 
- Green "Annotation saved!" message
- Form resets
- No errors

- [ ] **Step 4: Test FAIL annotation with 2 failure modes**

1. Select another trace
2. Select FAIL verdict
3. Check both modes: "Absent PHOSITA Reasoning" AND "Citation Text"
4. Enter comment: "Test annotation - both modes"
5. Click "Reviewed" checkbox
6. Click "💾 Save"

Expected: Same as Step 3 — annotation saves successfully

- [ ] **Step 5: Test PASS annotation**

1. Select another trace
2. Select PASS verdict
3. Verify failure modes section shows: "✓ PASS verdict: no failure modes applicable"
4. Enter comment: "Test PASS annotation"
5. Click "Reviewed" checkbox
6. Click "💾 Save"

Expected: Annotation saves, no failure modes selected

- [ ] **Step 6: View Analysis Dashboard**

1. In sidebar, click "Analysis Dashboard"
2. Verify table shows 3 annotations:
   - Row 1: Verdict=FAIL, Failure Modes="absent_phosita_reasoning"
   - Row 2: Verdict=FAIL, Failure Modes="absent_phosita_reasoning; citation_text"
   - Row 3: Verdict=PASS, Failure Modes="none"

Expected: Table displays correctly with only 2 failure modes in the data

- [ ] **Step 7: Verify Failure Mode Frequency Chart**

In Analysis Dashboard, look for "Failure Mode Frequency" section.

Expected:
- Bar chart shows 2 bars: absent_phosita_reasoning (count=2), citation_text (count=1)
- Table below shows same counts

- [ ] **Step 8: Verify Verdict Summary**

Look for "Verdict Summary" section:

Expected:
- PASS: 1
- FAIL: 2

- [ ] **Step 9: Stop Streamlit**

```bash
# In the Streamlit terminal, press Ctrl+C
```

---

## Task 6: Verify Annotations File Structure

**Files:**
- Verify: `traces/traces_annotations.jsonl`

- [ ] **Step 1: Check annotations file content**

```bash
type traces\traces_annotations.jsonl
```

Expected: JSONL file with 3 records (one per line), each containing:
- `run_id`: trace ID
- `phase`: 3
- `failure_modes`: array with 0, 1, or 2 IDs (only from the 2-mode taxonomy)
- `verdict`: "PASS" or "FAIL"
- `comment`: annotation comment text
- `reviewed`: true
- `timestamp`: ISO 8601 timestamp
- `dimensions`: metadata from trace

Example record:
```json
{"run_id": "abc123...", "phase": 3, "failure_modes": ["absent_phosita_reasoning"], "verdict": "FAIL", "comment": "Test annotation - PHOSITA mode", "reviewed": true, "timestamp": "2026-05-15T...", "dimensions": {...}}
```

- [ ] **Step 2: Verify no old failure mode IDs exist**

```bash
# Search for old mode IDs in annotations file
Select-String -Path "traces\traces_annotations.jsonl" -Pattern "(failed_claim_construction|inconsistent_verdict|unnecessary_evaluation)" | Measure-Object
```

Expected: Count = 0 (no matches)

- [ ] **Step 3: Verify backup file is intact**

```bash
# Count lines in backup (should have many annotations)
(Get-Content "traces\traces_annotations.jsonl.backup.2026-05-15" | Measure-Object -Line).Lines
```

Expected: Line count > 0 (old annotations preserved)

---

## Task 7: Final Verification and Commit

**Files:**
- Verify: All modified files

- [ ] **Step 1: Check git status**

```bash
git status
```

Expected: Shows modified/committed files:
- failure_taxonomy.json (committed)
- traces/traces_annotations.jsonl (committed)
- traces/traces_annotations.jsonl.backup.2026-05-15 (committed)
- app_annotation.py (no changes in this version, committed in Task 5 or not modified)

- [ ] **Step 2: Verify no uncommitted changes**

```bash
git diff
```

Expected: No output (all changes committed)

- [ ] **Step 3: Review commit log**

```bash
git log --oneline -5
```

Expected: Recent commits include:
- "backup: save Phase 3 annotations before taxonomy simplification"
- "refactor: simplify Phase 3 taxonomy to 2 failure modes"

- [ ] **Step 4: Final integration test (optional)**

Run the app one more time to ensure everything works:

```bash
python -m streamlit run app_annotation.py
```

Spot-check:
1. Phase 3 form shows only 2 modes
2. Can save a FAIL annotation with 1 mode
3. Dashboard displays correctly
4. Exit (Ctrl+C)

- [ ] **Step 5: Create a final commit summarizing the work**

```bash
git log --oneline -3
# Should show commits from this task sequence
```

If needed, create a summary commit:
```bash
git commit --allow-empty -m "Phase 3 simplification complete: 2-mode taxonomy, fresh annotations, updated UI"
```

---

## Testing Checklist

- [ ] Taxonomy file loads with 2 modes
- [ ] Backup file created and contains original annotations
- [ ] Fresh annotations file is empty
- [ ] Phase 3 form shows exactly 2 failure modes in multi-select
- [ ] FAIL verdict allows selecting 1 or 2 modes (validation passes)
- [ ] FAIL verdict with no modes selected shows warning (validation fails)
- [ ] PASS verdict hides failure modes (no selection allowed)
- [ ] Annotations save with correct structure (phase=3, failure_modes array)
- [ ] Dashboard displays Failure Mode Frequency with only 2 modes
- [ ] Dashboard Verdict Summary shows correct PASS/FAIL counts
- [ ] No old failure mode IDs (failed_claim_construction, etc.) appear anywhere
- [ ] Backup file integrity preserved

---

## Rollback Plan

If issues arise:

```bash
# Restore old taxonomy
git checkout HEAD~2 -- failure_taxonomy.json

# Restore old annotations
Copy-Item -Path "traces\traces_annotations.jsonl.backup.2026-05-15" -Destination "traces\traces_annotations.jsonl" -Force

# Verify
git status
```

---

## Summary

**Three files modified:**
1. `failure_taxonomy.json` - reduced to 2 modes
2. `traces_annotations.jsonl` - cleared for fresh start (backup preserved)
3. `app_annotation.py` - no code changes needed (form/dashboard adapt dynamically)

**Total commits:** 2-3
- Backup & clear annotations
- Update taxonomy
- (Optional) Summary commit

**Testing:** Manual UI testing validates the integration
