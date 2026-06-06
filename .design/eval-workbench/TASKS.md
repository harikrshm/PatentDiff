# Build Tasks: Eval Workbench — Analyst Console Redesign

Generated from: .design/eval-workbench/DESIGN_BRIEF.md (+ INFORMATION_ARCHITECTURE.md, DESIGN_TOKENS.css)
Date: 2026-06-06
Build location: `.claude/worktrees/eval-workbench/app_workbench/`

**Reuse map (do not rebuild — these are the frozen functional core):**
`core/workbench_data.py` (`list_trace_sets`, `load_merged`) · `core/diagnostics.py`
(`dispersion_pp`, `relationship_gradient`, `evidence_note`) · `core/priority.py`
(`priority_table`) · `core/workbench_state.py` (`load_state`/`save_state`) ·
`core/eval_runner.py` (`eval_for_set`). The redesign rewires the *view*, not these.

**Structural change vs current build:** `app.py` multipage + `pages/explore.py` +
`pages/decision.py` + `dash-pivottable` + `dash-draggable` are **replaced** by one
single-page narrative. `dash-draggable` / `dash-pivottable` deps become removable.

---

## Foundation

- [x] **T1 — Install tokens + Plotly theme** _(establishes the ANALYST CONSOLE philosophy — do first)_:
  Copy `DESIGN_TOKENS.css` → `app_workbench/assets/workbench.css` (Dash auto-serves it). Add a base
  stylesheet section that wires the tokens to real element styles (body bg/text/font, headings, links,
  focus rings, scrollbar). Build `app_workbench/theme.py` exposing a shared `go.layout.Template` +
  the reserved FAIL-rate `colorscale` (from the Plotly reference block in the tokens file), so every
  figure themes identically. _New: workbench.css, theme.py. Reuses: DESIGN_TOKENS.css._

- [x] **T2 — Console shell + sticky control bar + step rail**: Replace the multipage `app.py` with a
  single-page layout: app canvas (≤1440px), a **sticky frosted control bar** (active trace-set dropdown,
  Run-eval button, last-run timestamp, light/dark toggle) and a slim **step rail** (markers ①–⑤ as
  anchor links with scroll-spy current-section highlight). The five section containers are stubbed with
  numbered headers ("question it answers" subtitle) and anchor ids `#how-bad/#where/#why/#priority/#decision`.
  Light/dark toggle sets `data-theme` on `<html>`. _Modifies: app.py (de-multipage). Deletes: pages/.
  Reuses: list_trace_sets, eval_runner (button wired in T10)._ **Visual priority + sticky/scroll-spy risk.**

- [x] **T3 — Voice components (the signature motif)**: Build the two distinct, reusable render helpers —
  `machine_note(text, *, dispersion, gradient)` → cool indigo filled block, uppercase mono **HYPOTHESIS**
  tag, supporting numbers inline; and `human_field(label, value, kind)` → warm ochre outlined "your call"
  affordance (textarea / dropdown / radio variants) with editable feel. Both pull only `--voice-*` tokens;
  distinction must survive grayscale (hue **and** treatment). Verify by rendering a sample pair in isolation.
  _Modifies: components.py `evidence_note`→`machine_note`. New: `human_field`, rebuilt `assumed_badge`._

## Core UI

- [x] **T4 — §1 How bad: KPI tiles**: Rebuild `kpi_tile()` against tokens — mono numerals (size-2xl/3xl),
  left valence rule (`--data-good/mid/bad`), label + value + n-count. Render the 4 tiles (PHOSITA FAIL,
  Citation FAIL, Either, Fully-clean) in a wrapping row, with the attribution context line beneath
  (trace set · model · prompt version). _Modifies: kpi_tile. Reuses: load_merged. Depends on: T1, T2._
  **Early aesthetic validation gate.**

- [x] **T5 — §2 Where: custom themed heatmap**: Replace `dash-pivottable` with a hand-themed
  `go.Heatmap` (rows = claim profile `Method/System · Short/Long`, cols = `Anticipation/Implicit/Novel`),
  using the reserved diverging colorscale. Print **FAIL% + n in every cell**; flag `n<3` cells with ⚠ +
  muted treatment; show row/col averages. Eval toggle (PHOSITA · Citation · Either) as a tokenized
  **segmented control**. Dimension-source caption beneath. _New heatmap (drops dash-pivottable).
  Reuses: load_merged, the `_fail_frame` logic. Depends on: T1._ **Highest uncertainty — build early.**

- [x] **T6 — §3 Why: shape-read**: Render the machine **HYPOTHESIS** (via T3 `machine_note`) from
  `dispersion_pp` + `relationship_gradient`, naming the worst cluster, with dispersion/gradient numbers
  exposed. Pair it with the **your-call** conclusion field (T3 `human_field`, textarea) persisted to
  `annotations.json`. Eval toggle state is **shared with §2** (same control drives both). _Reuses:
  diagnostics, workbench_state. Depends on: T3, T5._

- [x] **T7 — §4 Priority: live table + tier inputs**: Theme `dash_table` to tokens (mono numerals,
  score-driven row emphasis, no zebra noise). Impact-per-failure-mode and Exposure-per-cell controls as
  your-voice dropdowns (T3), each wearing the **⚠ assumed** badge + tooltip. Table cols: Failure mode ·
  Cell · FAIL% · n · Freq(computed) · Impact · Exposure · **Score**; re-sorts live on input change. Add the
  Frequency×Impact inversion rollup. _Reuses: priority_table, assumed_badge. Depends on: T1, T3._

- [x] **T8 — §5 Decision: layer + recommendation + rationale**: Per failure mode, a **Layer** assignment
  (L1/L2/L3, your-voice radio) shown beside an **echo of its §3 HYPOTHESIS**. Assemble the ordered,
  cheapest-layer-first recommendation from score + assigned layer. Required **rationale** textarea
  (your-voice) — the decision audit trail — persisted to `priority_inputs.json`. _Reuses: T3 voice
  components, workbench_state. Depends on: T3, T6, T7._

## Interactions & States

- [x] **T9 — Cross-section reactivity + persistence**: Corpus switch re-derives the **whole page** (KPIs,
  heatmap, hypothesis, priority) from the selected set. All PM inputs (conclusion, tiers, layers,
  rationale) persist keyed by `{section, widget_id, active_set}`, so each trace set keeps independent
  decision state; reopening restores it. Optional `?set=` / `?eval=` deep-link sync. _Reuses:
  workbench_state. Depends on: T4–T8._

- [x] **T10 — Run-eval background states**: Wire the control-bar Run-eval button to the background job:
  disabled/queued while running (no double-run), live status + log tail, refresh page data + update
  last-run timestamp on completion, scroll position preserved. _Reuses: eval_runner (`eval_for_set`).
  Depends on: T2._ Covers: idle, running, done, error.

- [x] **T11 — Empty / low-confidence / loading states**: Handle no-trace-set, missing eval results,
  `n<3` low-confidence cells (⚠), and per-section loading skeletons during corpus switch / eval run.
  Every empty state explains *why* and what to do. _Depends on: T4–T8._

## Responsive & Polish

- [x] **T12 — Responsive desktop → laptop**: Verify and tune 1440 → ~1024: KPI tiles wrap, heatmap stays
  horizontally scrollable, control bar + step rail stay sticky/usable, no phone reflow. Below ~1024
  degrades gracefully (out of scope, must not break). Breakpoints: lg(1024)/xl(1280)/2xl(1440).

- [x] **T13 — Accessibility pass**: Indigo focus rings on every control; full keyboard nav (selector,
  toggles, dropdowns, run-eval, rationale fields); body/numeral contrast ≥4.5:1 and UI ≥3:1 in both
  modes; **voice distinction verified in grayscale**; heatmap % printed in every cell; ⚠ tooltips
  supplementary only. _Checks pulled from brief's Accessibility section._

- [x] **T14 — Dark-mode QA**: Walk all five sections in `data-theme="dark"`: confirm the Plotly template
  swaps to the dark diverging stops, voice tints deepen correctly, no pale-cell glow, indigo/red lift for
  contrast. Both modes must feel intentional, not inverted. _Reuses: token dark overrides + theme.py._

## Review

- [ ] **Design review**: Run `/design-review` against the brief — visual hierarchy, the three disciplines
  (data-only color, indigo chrome, machine/human voice), responsiveness, accessibility, aesthetic fidelity.
