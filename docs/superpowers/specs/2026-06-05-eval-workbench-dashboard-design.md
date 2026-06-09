# Eval Workbench Dashboard — Design Spec

**Date:** 2026-06-05
**Deliverable:** Full-BI interactive eval workbench (Plotly **Dash** app), replacing the
read-only Streamlit dashboard (`scripts/run_dashboard.py`) once at parity.
**Audience:** Product Manager making the post-eval product decision.

## Goal

Turn the eval suite into a **decision workbench the PM operates**, not a static
report. The app must carry the PM through the full Notion "From Dashboard to
Product Decision" arc — *how bad → where → why (which architecture layer) → what
to fix first* — while keeping the PM in control at every step.

**Guiding principle (non-negotiable):** *The LLM/app guides; the PM decides.*
The app shows **where** eval fails and offers a **hypothesis** for why. Every
final conclusion — the architecture layer, the priority order, the decision — is
a **PM input**, captured with the PM's own rationale. No computed verdicts.

---

## Scope

### In scope
- Dash multi-page app, two surfaces: **① Explore / Eval Workbench**, **② Decision**.
- Draggable/resizable widget grid; drag-drop pivot heatmap (dimensions onto rows/cols/filters).
- "Run eval" from the UI on an **already-existing** selected trace set (background job).
- Computed, interactive Frequency × Impact × Exposure priority scoring (Steps 1 / 1b).
- Visual "shape read" diagnostic (Step 2) — surfaced as a hypothesis, PM assigns the layer.
- Auto **evidence-notes** (templated, deterministic) + **PM rationale** capture on every derived insight.
- File-based persistence of layout, annotations, and priority inputs.

### Out of scope (this build)
- **Trace ingest or generation** — confirmed out. The app only measures existing trace sets;
  generating traces stays an upstream manual step in the PatentDiff product repo.
- Auth / multi-user (single-user local tool).
- Deployment / hosting (local run only).
- Historical trending over time.
- Any change to eval or judge logic — **the measurement ruler stays frozen**
  (`core/phosita_eval.py`, `core/citation_eval.py`, judge prompts untouched).

---

## Architecture

```
core/workbench_data.py            NEW — load+merge logic (extracted from run_dashboard._load_data)
├── load_merged(active_set) -> pandas.DataFrame   # one row per trace w/ >=1 eval result
└── list_trace_sets() -> list[TraceSet]           # scans traces/ for live + suffixed sets

core/diagnostics.py               NEW — deterministic "shape read" + evidence-note logic
├── cell_fail_table(df, eval, rows, cols, filters) -> pivot of FAIL% + n
├── dispersion(pivot) -> float                    # spread of FAIL% across cells
├── relationship_gradient(df, eval) -> GradientResult  # Anticipation->Implicit->Novel monotonicity
└── evidence_note(...) -> str                     # templated hypothesis string (NEVER a verdict)

core/priority.py                  NEW — Step 1 / 1b scoring
└── priority_table(df, impact_tiers, exposure_tiers) -> DataFrame  # Freq x Impact x Exposure

core/workbench_state.py           NEW — file-based persistence (read/write JSON)
├── load_state() / save_state(...)               # layout.json, annotations.json, priority_inputs.json

core/eval_runner.py               NEW — background eval execution
└── run_evals(active_set) -> job handle           # shells out to scripts/run_*_eval.py, streams log

app_workbench/                    NEW — Dash app
├── app.py                         # Dash(__name__, use_pages=True), DiskCache background manager
├── pages/explore.py               # Surface ① widgets in a dash-draggable grid
└── pages/decision.py              # Surface ② priority table + decision capture

tests/
├── test_workbench_data.py         # parity: load_merged == old _load_data on same inputs
├── test_diagnostics.py            # dispersion, gradient, evidence-note templating
└── test_priority.py              # F x I x E scoring + sort order
```

- **Data flow:** all reads at callback time via `core/workbench_data.load_merged`. Dimensions
  inferred by `dimension_tagger.tag_trace`; human annotations (phase 3) override, exactly as today.
- **Eval runner:** Dash **background callback** with the **DiskCache** manager (zero extra infra —
  no Celery/Redis). Shells out to the existing idempotent-cached eval scripts; re-running is safe.
  Streams status + tail of the log; refreshes the active set's data on completion.
- **Persistence:** plain JSON under `traces/workbench_state/`. Single-user, no DB.

### Trace-set selector
`list_trace_sets()` scans `traces/` and groups files by suffix into selectable sets:

| Set | phosita file | citation file | traces file |
|---|---|---|---|
| **live** | `phosita_eval_full.jsonl` | `citation_text_eval_full.jsonl` | `traces.jsonl` |
| **baseline** | `phosita_eval_full.baseline.jsonl` | `citation_text_eval_full.baseline.jsonl` | — |
| **exp1** | `phosita_eval_full.exp1.jsonl` | `citation_text_eval_full.exp1.jsonl` | `traces.exp1.jsonl` |
| … | (any `*.<suffix>.jsonl` discovered) | | |

PHOSITA verdicts are filtered to `prompt_version == PHOSITA_PROMPT_VERSION` (v3), as today.

---

## Surface ① — Explore / Eval Workbench

A **draggable, resizable widget grid** (`dash-draggable`, which wraps
react-grid-layout). Seeded with a default layout in Approach-A funnel order; the
PM rearranges/resizes and the layout persists to `layout.json`.

**Widgets:**

1. **Top bar — corpus + run control**
   - Active trace-set dropdown (from `list_trace_sets()`).
   - **Run eval** button → background job → live status + log tail → last-run timestamp.
   - Disabled/queued state while a job is in flight (no double-runs).

2. **How bad — KPI tiles**
   - PHOSITA FAIL %, Citation FAIL %, Either-fails %, Fully-clean %, each with n.
   - Computed on the active set, same definitions as the current Summary tab.

3. **Where — configurable pivot heatmap** *(the drag-drop centerpiece)*
   - Three dimensions available: `claim_type`, `claim_length`, `relationship`.
   - PM drags each onto **Rows / Columns / Filters** (pivot builder).
   - Eval toggle: PHOSITA / Citation / Either.
   - Cell value: FAIL % with `(n=N)`; cells with `n < 3` flagged ⚠ (low confidence).
   - Color scale red(high)→green(low), as today.
   - Dimension-source caption preserved (human-verified vs inferred accuracy figures).

4. **Shape read — Step 2 diagnostic (hypothesis only)**
   - For the current pivot: sorted cell-FAIL bars, a **dispersion** number, and the
     **relationship gradient** (Anticipation→Implicit→Novel monotonicity).
   - Auto **evidence-note** (templated): e.g.
     *"FAIL% spread across cells = 12pp (low) → uniform → Layer-1 (instruction) hypothesis"*, or
     *"FAIL% rises monotonically Anticipation 17% → Implicit 50% → Novel 68% → reasoning-correlated → Layer-2/3 signal; residual clustered in System×Novel."*
   - Labeled **HYPOTHESIS**. The app **does not** assign a layer here — that happens on Surface ②.

Every widget has a **PM comment** affordance (persisted to `annotations.json`, keyed by widget id + active context).

---

## Surface ② — Decision (Steps 1 + 1b + the decision)

1. **Interactive priority inputs**
   - **Impact** tier per failure mode (High/Med/Low dropdown) — domain judgment.
   - **Exposure** tier per dimension cell (High/Med/Low) — production query mix.
   - Every Impact/Exposure control rendered with a **⚠ assumed** badge and a tooltip:
     *"Placeholder until live claim_type × relationship query distribution is instrumented."*

2. **Live priority table (Step 1b)**
   - Rows: (failure mode × dimension cell).
   - Columns: **Frequency** (cell FAIL %, tiered ≥67%→3 / 34–66%→2 / ≤33%→1 — *computed*),
     **Impact** (input), **Exposure** (input), **Score = Freq × Impact × Exposure**.
   - Sorted by score desc; re-sorts live as inputs change. Mirrors the Notion Step 1b table.

3. **Frequency × Impact rollup (Step 1)**
   - The two-mode summary: frequency from data, impact from input, net priority — so the PM
     can see the "frequency said citation; Frequency×Impact said PHOSITA" inversion explicitly.

4. **Layer assignment (PM decides)**
   - Each priority row shows the **shape-read indicator** carried from Surface ① + its evidence-note.
   - PM picks the **final layer** (L1 / L2 / L3) per failure mode via a control — this is the
     human conclusion, not a computed one.

5. **Decision output + rationale capture**
   - The ordered, **cheapest-layer-first** recommendation assembled from score + assigned layer.
   - Each line has a **required PM rationale** field (persisted). This is the decision audit trail:
     *why* the PM ordered the fixes this way.

---

## The "guides, not decides" rule — implemented uniformly

Every data-derived statement in the app carries **two visually distinct elements**:

| Element | Source | Nature | Example |
|---|---|---|---|
| **Evidence-note** | `core/diagnostics.evidence_note` | Deterministic, templated, labeled **HYPOTHESIS** | *"spread 12pp → uniform → L1 hypothesis"* |
| **PM rationale** | PM input, persisted | Human conclusion / decision | *"Agree it's L1; verbatim instruction is near-free, do first."* |

- Evidence-notes are **never** LLM-generated prose and **never** phrased as a verdict — they state
  the rule that fired and the number behind it, so the PM can sanity-check small-n cells.
- Final **layer**, final **priority order**, and final **decision** are PM inputs. The app cannot
  set them.

### Evidence-note logic (spread + gradient)
`core/diagnostics` computes, for a given eval + pivot:
- **Dispersion:** spread of FAIL % across populated cells (e.g. max−min, or stdev) →
  low ⇒ "uniform → Layer-1" hypothesis; high ⇒ "clustered → capability signal."
- **Relationship gradient:** monotonicity of FAIL % along Anticipation→Implicit→Novel →
  rising ⇒ "reasoning-correlated → Layer-2/3" hypothesis, naming the worst cluster.
Both numbers are shown next to the note so the PM can discount noisy small-n cells.

---

## Persistence schema (`traces/workbench_state/`)

| File | Contents |
|---|---|
| `layout.json` | dash-draggable grid layout per surface (positions, sizes) |
| `annotations.json` | PM comments, keyed by `{surface, widget_id, active_set}` |
| `priority_inputs.json` | Impact tier per failure mode, Exposure tier per cell, assigned layers, decision rationale |

All writes are debounced full-file rewrites (single-user, small files). Missing files → sensible defaults.

---

## Reuse / migration

- `core/workbench_data.load_merged` is the **extracted, test-covered** version of today's
  `run_dashboard._load_data`. A parity test asserts identical output on the same inputs.
- `dimension_tagger` reused unchanged.
- The Streamlit app (`scripts/run_dashboard.py`) **stays as legacy** until the Dash app reaches
  parity on KPIs + heatmap, then is removed in a follow-up.

---

## Success criteria

1. `python -m app_workbench.app` (or documented run command) launches the Dash app without error.
2. Surface ① KPIs match the current Streamlit dashboard on the `live` set (parity test passes).
3. The pivot heatmap lets the PM put any of the three dimensions on rows/cols/filters and shows FAIL% (n).
4. Widgets can be dragged/resized and the layout persists across restarts.
5. "Run eval" executes the existing eval scripts on the selected set as a background job, streams a log, and refreshes data on completion — without blocking the UI.
6. The Decision surface computes a live Freq × Impact × Exposure priority table that re-sorts as Impact/Exposure inputs change, with every assumed input flagged ⚠.
7. Every derived insight shows a templated evidence-note (spread + gradient) labeled HYPOTHESIS, plus a PM rationale/comment field that persists.
8. No file under `core/*_eval.py` or any judge prompt is modified (ruler frozen).
```
