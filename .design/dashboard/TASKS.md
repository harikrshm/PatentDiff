# Build Tasks: Eval Dashboard (Overview → Dashboard)

Generated from: .design/dashboard/DESIGN_BRIEF.md
Date: 2026-06-11

> **Stack:** Plotly **Dash**. The `/eval` page is built by
> `app_workbench.app.build_console_body()` with callbacks in
> `app_workbench/callbacks.py`. "Build" = rework that layout into a 2×3 block
> grid + author `uw-dash*` CSS (consuming existing tokens) + Dash callbacks that
> read the **already-built** backend (`core/kpi_view`, `core/kpi_targets`,
> `core/eval_history`). Aesthetic: **instrument panel** — cool canvas, mono
> numerals, hairline cards; "show, don't conclude." Verify each task by booting
> `python -m app_unified.app` and viewing `/eval`. Keep the eval ruler frozen.

## Foundation
- [x] **T1 · Dashboard grid shell + rename + funnel removal** _(establishes the
  instrument aesthetic; frames every block; riskiest because it guts the funnel)_:
  Replace the funnel body in `build_console_body()` with a 2×3 `uw-dash` grid of
  six titled block cards (placeholder content ok); delete the step-rail and the
  §why/§priority/§decision markup **and their now-dead callbacks** in
  `app_workbench/callbacks.py` (keep run-eval, corpus-selector, heatmap,
  `data-version`, `theme`). Rename the sidebar nav label "Overview" → **"Dashboard"**
  (`app_unified/components.py` EVAL_GROUP). New `uw-dash*` CSS (grid + block card
  on the instrument surface, reusing `--card-padding`, hairline borders).
  _Modifies: `app_workbench/app.py`, `app_workbench/callbacks.py`,
  `app_unified/components.py`; new `uw-dash*` CSS. Done = `/eval` shows a 2×3
  grid of instrument cards, no funnel, app boots, no callback errors._

## Core UI
- [x] **T2 · Block 1 — Trace Properties (static run UI + metadata)**: Move the
  trace-set selector + **Run eval** button + status + last-run out of the floating
  control bar into Block 1 as a static card; add run metadata read from
  `core/eval_history` (latest run timestamp, prompt version, n scored) for the
  active set. _Reuses: `wb-dropdown`, the run-eval button/`run_eval` callback
  (n_clicks guard intact). Modifies: layout + a small metadata callback. Done =
  Block 1 shows set selector + run control + last-run + metadata; selecting a set
  does NOT run evals; Run eval still streams + refreshes._
- [x] **T3 · Block 2 — Eval failure-mode summary** _(risk-first: new data
  assembly)_: Segmented PHOSITA/Citation selector → horizontal bar chart (Plotly)
  of each failure-mode's **share of FAILs** for the active set, mono % + n. Add a
  `core` aggregation helper joining the eval's FAIL traces to human
  `failure_modes` (`traces_annotations.jsonl` + `failure_taxonomy.json`); if the
  join proves non-trivial, pause and brainstorm. _Reuses: `wb-segmented`, theme
  store, `--data-*` for bar tint. New: aggregation helper + chart. Done = picking
  an eval renders ranked failure-mode bars with counts; empty/he-unannotated case
  shows a calm "no annotated FAILs" readout._
- [x] **T4 · Block 3 — Dimension heatmap (selectable row/col)**: Two dimension
  dropdowns (row, col) from `claim_type · claim_length · relationship`; regenerate
  the diverging FAIL-rate heatmap for the chosen pair; cells print value + n.
  _Modifies: `app_workbench/heatmap.py` to accept arbitrary (row_dim, col_dim) +
  its callback. Reuses: the existing heatmap figure/scale. Done = changing either
  dropdown redraws the heatmap on the new axes; color = FAIL-rate only, value
  always shown._
- [x] **T5 · Block 4 — Eval score vs KPI target**: For each eval kind, a readout
  of current PASS-rate vs target with the gap to goal (valence-tinted bar/marker,
  mono numerals). Reads `kpi_view.current_pass_rate` + `kpi_targets.get_target`.
  _Reuses: `wb-kpi` tile vocabulary. Done = shows current % and target % with a
  visible gap; "no target set" state when none exists._
- [x] **T6 · Block 5 — Metric trajectory**: Baseline → current → expected progress
  chart (Plotly) on a time axis — three dated points + the gap-to-target — per eval
  kind (or a small eval toggle). Reads `kpi_view.trajectory`. _New chart. Done =
  the three points plot in time order with the target/expected marker; empty
  history shows a calm empty state._
- [x] **T7 · Block 6 — Set KPI target**: PM inputs — target PASS-rate, target date,
  baseline run (dropdown of history runs) — that write `kpi_targets.set_target`;
  saving updates Blocks 4 & 5. Validation surfaced inline (rate 0–100%, valid
  date). _Reuses: `uw-input`/`uw-btn--primary`, `wb-dropdown`. Done = setting a
  target persists to `traces/kpi_targets.json` and Blocks 4/5 reflect it without a
  page reload._

## Interactions & States
- [x] **T8 · Cross-block wiring + states**: Trace-set select (Block 1) refreshes
  every block for that set; Run-eval completion (`data-version` bump) refreshes all;
  Block-2 eval-select and Block-3 dims re-render in place; Block-6 save refreshes
  4/5. Global empty (no eval file → calm readouts), loading (`dcc.Loading` on
  chart blocks), and disabled/streaming states. Covers: hover, focus-visible,
  disabled, loading, empty. _Done = every block reacts to set/run/target changes;
  nothing runs evals except the Run button; no block errors on a missing file._

## Responsive & Polish
- [x] **T9 · Responsive ~1024 + accessibility pass**: 2×3 grid → single stacked
  column below ~1024; charts full-width; tables/heatmap horizontally scrollable.
  Indigo focus rings on all selectors/inputs/buttons; diverging scale stays
  colorblind-safe with value+n on every cell; Plotly figures keep text
  labels/legends and recolor with the theme; numerals/body ≥ 4.5:1 both themes.
  Breakpoints: 1024, 1280, 1440. _Done = the brief's responsive + a11y
  requirements hold._

## Review
- [ ] **Design review**: Run `/design-review` against the brief — screenshots at
  1280/1440 (+ ~1024) and dark mode of `/eval`; check "show, don't conclude"
  (no machine insight), color-as-data discipline, the 6-block read-at-a-glance,
  and that selecting a set never triggers an eval run.
