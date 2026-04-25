# Phase 2: Axial Coding - Failure Taxonomy Summary

**Date:** 2026-04-25  
**Methodology:** Workflow-Stage Based Axial Coding  
**Output:** failure_taxonomy.json (ready for Phase 3)

---

## Overview

Phase 2 transforms Phase 1 open codes into a **consolidated failure taxonomy** organized by PatentDiff workflow stages.

**Key Findings:**
- **15 traces** from Phase 1 analyzed
- **11 traces** with failure modes (after filtering technical errors)
- **3 PASS** traces, **8 FAIL** traces
- **9 total failures** identified
- **9 unique consolidated categories** across **4 workflow stages**

---

## Exclusions: Technical Errors

The following codes were **excluded** from the taxonomy as they are system/environmental constraints:
- `token_limit`
- `toke_limit`

**Reason:** These are not methodology errors but rather environmental/system constraints. Token limit hitting is a deployment/system configuration issue, not a PatentDiff analysis error.

---

## Failure Taxonomy: 4 Workflow Stages

### Stage 1: Input Understanding & Decomposition (55.6% of failures)

**Purpose:** Understand source and target patents; decompose claims into elements

**Failure Categories:**

#### 1.1 Claim Decomposition & Structure (HIGH impact)
- **Consolidated codes:** `claim_decomposition`, `claim element decomposition`, `big_claim`
- **Problem:** Large claims not properly broken down into elements; elements analyzed without full claim context
- **Impact:** Incomplete element-by-element analysis; missing context
- **Example:** "Long claim elements are not delimited properly, not analyzed for differences"

#### 1.2 Preprocessing & Input Step Recognition (HIGH impact)
- **Consolidated codes:** `pre_processing_mapping`, `pre_processing_step`, `pre+post_processing_steps`
- **Problem:** Failure to correctly classify preprocessing/postprocessing steps; treating foundational steps as novel
- **Impact:** Incorrect novelty/inventive step assessment
- **Example:** "Input steps won't have novelty/inventive step - they're just preprocessing"

#### 1.3 Patent Document Coverage (MEDIUM impact)
- **Consolidated codes:** `preamble_missed`
- **Problem:** Failure to analyze all sections of patent (preamble, claims, specification)
- **Impact:** Incomplete analysis
- **Example:** "Preamble is missed for mapping in all traces"

---

### Stage 2: Claim Language & Term Analysis (22.2% of failures)

**Purpose:** Interpret claim terms correctly; identify corresponding text between patents

**Failure Categories:**

#### 2.1 Term Interpretation & Consistency (HIGH impact)
- **Consolidated codes:** `term_consistent`, `verbatim_term`
- **Problem:** Treating claim terms verbatim instead of using specification context; inconsistent interpretation
- **Impact:** Misinterpretation of claim scope
- **Example:** "Using specification support to understand claim terms better rather than verbatim understanding"

#### 2.2 Corresponding Text Identification (MEDIUM impact)
- **Consolidated codes:** `correspond_text`
- **Problem:** Verdict summarizes/paraphrases rather than quoting actual corresponding text
- **Impact:** Traceability and verification issues
- **Example:** "Verdict summarizes the text rather than quoting the corresponding text"

---

### Stage 3: Novelty Assessment (11.1% of failures)

**Purpose:** Assess whether elements are novel; distinguish novelty from inventive step

**Failure Categories:**

#### 3.1 Novelty vs. Inventive Step Distinction (HIGH impact)
- **Consolidated codes:** `diff_nov_and_invent`, `diff_in_tech`
- **Problem:** Confusion between novelty and inventive step; missing explanation of technical differences
- **Impact:** Fundamental conceptual error
- **Example:** "Different between novelty and inventive step - need clear distinction"

#### 3.2 Person Skilled in Art Consideration (HIGH impact)
- **Consolidated codes:** `person_skilled`
- **Problem:** Failure to consider assessment from perspective of person skilled in the art
- **Impact:** Fundamental patent law requirement missed
- **Example:** "Inventive step in light of person skilled in art not properly considered"

---

### Stage 4: Inventive Step Assessment (11.1% of failures)

**Purpose:** Determine if differences from prior art constitute an inventive step

**Failure Categories:**

#### 4.1 Inventive Step Reasoning & Judgment (CRITICAL impact)
- **Consolidated codes:** `hallucination_inventive_step`, `narrow_inventive_step`, `mark_inventive_step`, `inventive_why?`
- **Problem:** Incorrect marking of inventive step; hallucinated reasoning; threshold issues; missing justification for why a difference is inventive
- **Impact:** CRITICAL - Direct impact on final verdict
- **Examples:**
  - "Hallucination: says no inventive step but marked as inventive"
  - "Threshold too narrow - slight changes marked as inventive"
  - "Missing explanation of why the difference constitutes an inventive step"
  - "Prior art difference mentioned but not explained why it's inventive"

---

## Failure Distribution

```
Input Understanding & Decomposition    : 5 failures (55.6%)
Claim Language & Term Analysis         : 2 failures (22.2%)
Novelty Assessment                     : 1 failure  (11.1%)
Inventive Step Assessment              : 1 failure  (11.1%)
                                        ----------
                                        9 total failures
```

---

## Clustering Analysis

### Failures that Naturally Cluster Together

**Cluster A: Claim Analysis Problems**
- Claim decomposition
- Preprocessing/postprocessing mapping
- Term interpretation
- Corresponding text identification

**Cluster B: Conceptual Understanding Gaps**
- Novelty vs. inventive step distinction
- Person skilled in art consideration
- Inventive step reasoning

**Cluster C: Completeness Issues**
- Patent document coverage (preamble)
- Corresponding text citation
- Inventive step justification

---

## Tech Errors vs. Logic Errors

### Technical/Environmental Errors (Excluded)
- `token_limit` - System constraint, solved via deployment optimization

### Logic/Methodology Errors (Included in Taxonomy)
- **Conceptual errors** (3): Novelty/inventive step confusion, person skilled in art
- **Analysis errors** (5): Claim decomposition, preprocessing mapping, preamble coverage
- **Judgment errors** (1): Inventive step assessment (hallucination, threshold issues)

---

## Next Steps: Phase 3 - Re-annotation

With `failure_taxonomy.json` in place, Phase 3 will:

1. **Load the taxonomy** into the annotation tool (Phase 3 mode)
2. **Re-annotate all 83 traces** using standardized consolidated categories
3. **Preserve open codes** for traceability (maintain `open_coded_failure_modes` field)
4. **Add standardized codes** (populate `failure_modes` field with taxonomy categories)
5. **Output:** Updated `traces_annotations.jsonl` with both open and standardized codes

---

## Files Generated

### 1. **Phase_2_Axial_Coding.ipynb**
Jupyter notebook with step-by-step axial coding analysis:
- Load and explore Phase 1 data
- Extract and normalize open codes
- Define workflow-based taxonomy
- Map codes to consolidated categories
- Frequency analysis
- Visualization
- Taxonomy JSON generation

### 2. **failure_taxonomy.json**
The standardized failure taxonomy with:
- 4 workflow stages
- 9 consolidated categories
- Code mappings
- Impact levels
- Descriptions and examples
- Statistics

### 3. **phase2_generate_taxonomy.py**
Python script to regenerate taxonomy from annotations:
- Loads `traces_annotations.jsonl`
- Filters technical errors
- Generates `failure_taxonomy.json`
- Produces summary statistics

---

## Methodology Notes

### Why Workflow-Based Taxonomy?

1. **Actionable:** Each stage has specific improvement targets
2. **Traceable:** Maps to PatentDiff's analysis pipeline
3. **Hierarchical:** Stages → Categories → Codes
4. **Consolidated:** Related codes merged to reduce taxonomy size
5. **Scalable:** New codes added to existing categories as needed

### Consolidation Rationale

- **Inventive Step** consolidated into single category because all related failures (hallucination, narrow threshold, marking, justification) are aspects of the same assessment problem
- **Preprocessing** consolidated because preprocessing, postprocessing, and input step classification are variants of the same issue
- **Novelty vs. Inventive** consolidated because both relate to conceptual confusion

---

## Ready for Phase 3

The taxonomy is frozen and ready for:
- ✅ Phase 3: Re-annotation with standardized categories
- ✅ Phase 4: Judge building based on failure patterns
- ✅ Phase 5: Scale evaluation with taxonomy

**Status:** Phase 2 Complete ✓
