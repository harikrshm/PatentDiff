# Error Rate Dashboard — Design Spec

**Date:** 2026-05-30
**Deliverable:** Standalone Streamlit app (`scripts/run_dashboard.py`)
**Audience:** Product Manager / stakeholder

## Goal

Turn the two automated evaluators (PHOSITA reasoning + Citation Text) into a
product decision surface. A PM opening the dashboard should immediately see:
1. How bad the quality problem is overall (KPIs)
2. Where it's worst by patent type and prior-art relationship (heatmap)
3. What to do about it, in plain English (PM implications)

---

## Data sources (read-only, no writes)

| File | Used for |
|---|---|
| `traces/traces.jsonl` | Source of truth for claim text + element mappings → dimension inference |
| `traces/phosita_eval_full.jsonl` | PHOSITA eval verdicts (filter to `prompt_version = "v3"`) |
| `traces/citation_text_eval_full.jsonl` | Citation eval verdicts |
| `traces/traces_annotations.jsonl` | Human-verified dimensions (phase=3, where `dimensions` key present) |

All reads happen at Streamlit startup. No database, no server state.

---

## Automated dimension inference

Only 28 of 87 traces have human-annotated dimensions. The remaining 59 need
inference from trace data so the heatmap covers the full corpus.

### `core/dimension_tagger.py` (new module)

Three inference functions, each taking the full `trace` dict:

**`infer_claim_type(trace) → "Method" | "System" | "Unknown"`**

Reads `inputs.source_patent.independent_claim`. Strips leading numbering
(e.g. "1. "), lowercases, then applies regex priority:
1. Match `\ba (computer-implemented )?method\b` or `\bmethod (for|comprising|performed|implemented)\b` → `"Method"`
2. Match `\b(system|apparatus|device|article|encoder|circuit)\b` in first 60 chars,
   or `comprising:\s*(one or more )?(processors?|memory|means)` → `"System"`
3. Else → `"Unknown"`

Validated at 100% accuracy on 28 annotated traces.

**`infer_claim_length(trace) → "Short" | "Long"`**

Counts `len(parsed_output.element_mappings)`.
- `≤ 5 elements` → `"Short"`
- `> 5 elements` → `"Long"`

Validated at 89% accuracy on 28 annotated traces. Remaining 11% are borderline
5-element claims where annotator judgement differed. Acceptable for a dashboard.

**`infer_relationship(trace) → "Anticipation" | "Implicit" | "Novel" | "Unknown"`**

Computes `frac_Y = count(novelty == "Y") / total_elements`.
- `frac_Y >= 0.60` → `"Anticipation"` (prior art substantially matches)
- `frac_Y <= 0.25` → `"Novel"` (source patent is mostly novel vs prior art)
- Otherwise → `"Implicit"` (mixed — prior art partially teaches)
- No elements → `"Unknown"`

Validated at ~61% accuracy on 28 annotated traces. Limited by the fact that
the novelty flags are produced by the tool being evaluated (they may themselves
be wrong). Human-annotated relationship values take precedence where available.

**`tag_trace(trace) → dict`**

```python
{
    "claim_type": "Method" | "System" | "Unknown",
    "claim_length": "Short" | "Long",
    "relationship": "Anticipation" | "Implicit" | "Novel" | "Unknown",
    "source": "inferred"
}
```

**Dimension merging rule:** For traces with human annotations, replace the
`"source": "inferred"` fields with the annotation values and set
`"source": "human"`. Human dimensions always win.

---

## App structure (`scripts/run_dashboard.py`)

```
streamlit run scripts/run_dashboard.py
```

Three tabs rendered via `st.tabs(["📊 Summary", "🔥 Error Heatmap", "📋 PM Implications"])`.

### Tab 1 — Summary

**Header:** Last-updated timestamp (from newest eval file mtime) · total traces · eval versions.

**Four KPI metrics (st.metric):**
- PHOSITA Reasoning Failures: `n_fail / n_judge_evaluated` % (excludes short-circuit PASSes)
- Citation Text Failures: `n_fail / (n_pass + n_fail)` % (excludes NO_CITATIONS traces)
- Either failure mode: traces where at least one eval returns FAIL / total
- Fully clean: traces where both evals return PASS / total

**Failure co-occurrence table (on the 30-trace human-annotated sample):**

|  | PHOSITA PASS | PHOSITA FAIL |
|---|---|---|
| **Citation PASS** | Clean (green) | PHOSITA only (purple) |
| **Citation FAIL** | Citation only (orange) | Both fail (red) |

Show only traces that have BOTH eval results AND a human annotation.

**Highest-risk dimension preview:** Two metric tiles showing the
relationship dimension with the highest FAIL rate (both evals combined) and
the lowest, drawn from the heatmap data.

---

### Tab 2 — Error Heatmap

**Eval toggle:** `st.radio` with options `["PHOSITA Reasoning", "Citation Text", "Both (overlay)"]`.

**Heatmap grid (rendered as a styled `st.dataframe` or Plotly heatmap):**

- Rows: `claim_type × claim_length` combinations — Method/Short, Method/Long, System/Short, System/Long
- Columns: `relationship` — Anticipation, Implicit, Novel
- Cell value: FAIL rate % for the selected eval
- Color scale: green (0%) → yellow (40%) → red (70%+)
- Cell label: `"XX% (n=N)"` where N is the trace count in that cell
- "Both" overlay: show PHOSITA % / Citation % stacked in each cell

**Below the heatmap:** Three `st.metric` tiles showing column averages
(FAIL rate per relationship type, selected eval) — the single most readable
takeaway for a PM ("Implicit prior art causes 73% PHOSITA failures").

**Dimension source note:** `"28 of 87 traces use human-verified dimensions.
Remaining 59 use inferred dimensions (claim_type: 100% accurate,
claim_length: 89%, relationship: ~61%). Cells with n < 3 shown in grey."`

---

### Tab 3 — PM Implications

Static content (not computed from data — represents product judgement).
Rendered via `st.markdown` with colour-coded severity badges.

**Priority matrix table:**

| Issue | Priority | Fix type | Effort |
|---|---|---|---|
| PHOSITA failures on Implicit prior art (73% FAIL) | 🔴 P0 | Prompt iteration | 1–2 sprints |
| Citation text paraphrasing (45% FAIL) | 🟠 P1 | Prompt fix (v2 deployed) | Done — verify |
| System claims fail harder than Method (60% vs 43%) | 🔴 P1 | Architecture: claim-type routing | 2–4 sprints |
| Overall quality too low for production gate (~38% clean) | 🟣 P2 | Fine-tuning | 4–8 sprints |

**Fix type definitions** (collapsible `st.expander`):
- **Prompt fix** — change the system prompt or schema instruction. Reversible, fast, cheap. Does not require retraining.
- **Architecture change** — separate prompt paths for different claim types, or multi-agent routing. Requires engineering work but no training data.
- **Fine-tuning** — train the model on high-quality example outputs. Highest quality ceiling, highest cost and lead time. Requires a labelled dataset of good outputs.

**What to act on now** (two columns):

Left — Act:
1. Monitor Implicit prior art cases — consider a confidence flag in the UI for these outputs
2. Verify citation fix landed — re-run citation eval after v2 prompt deployed to production
3. Spec a claim-type router — different prompt logic for System vs Method claims

Right — Wait:
- Anticipation cases performing well (0–17% FAIL) — don't change what's working
- Fine-tuning — wait until prompt fixes plateau; collect labelled data in parallel

---

## Architecture

```
core/dimension_tagger.py           NEW
├── infer_claim_type(trace) → str
├── infer_claim_length(trace) → str
├── infer_relationship(trace) → str
└── tag_trace(trace) → dict

scripts/run_dashboard.py           NEW (Streamlit)
├── _load_data() → merged DataFrame (cached with @st.cache_data)
│   ├── reads traces.jsonl → infers dimensions for all 87 traces
│   ├── reads traces_annotations.jsonl → overrides with human dimensions
│   ├── joins phosita_eval_full.jsonl (v3)
│   └── joins citation_text_eval_full.jsonl
├── render_summary(df)
├── render_heatmap(df, eval_selection)
└── render_implications()

tests/test_dimension_tagger.py     NEW
├── test_infer_claim_type_method()
├── test_infer_claim_type_system()
├── test_infer_claim_type_unknown()
├── test_infer_claim_length_short()    # ≤5 elements
├── test_infer_claim_length_long()     # >5 elements
├── test_infer_relationship_anticipation()
├── test_infer_relationship_novel()
├── test_infer_relationship_implicit()
└── test_infer_relationship_unknown()  # no elements
```

`_load_data()` is decorated with `@st.cache_data` — recomputes only when any
source file's mtime changes. All three tabs read from the same cached DataFrame.

---

## DataFrame schema (output of `_load_data`)

One row per trace that has at least one eval result.

| Column | Type | Source |
|---|---|---|
| `run_id` | str | traces.jsonl |
| `claim_type` | str | human annotation or inferred |
| `claim_length` | str | human annotation or inferred |
| `relationship` | str | human annotation or inferred |
| `dim_source` | str | `"human"` or `"inferred"` |
| `phosita_verdict` | str | `"PASS"` / `"FAIL"` / `None` |
| `citation_verdict` | str | `"PASS"` / `"FAIL"` / `"NO_CITATIONS"` / `None` |
| `has_human_annotation` | bool | from traces_annotations.jsonl |

---

## Out of scope

- Writing back to any file (pure read-only)
- Real-time refresh / websocket updates
- User authentication
- Historical trending over time (single snapshot)
- CRM claim type (mentioned in Notion coverage matrix but not in current annotation taxonomy)
- Drill-down to individual trace view (handled by existing annotation tool)

---

## Success criteria

1. `streamlit run scripts/run_dashboard.py` launches without error
2. Summary KPIs match the values in `traces/phosita_vs_human_report.md` and
   `traces/eval_vs_human_report.md`
3. Heatmap shows at least 6 populated cells (relationship × claim_type)
4. PM Implications tab renders with the priority matrix and fix-type definitions
5. All 87 traces are dimensioned (no blank rows in the heatmap)
