# Design Brief: Eval Dashboard (Overview → Dashboard)

> Child of `.design/unified-workbench/DESIGN_BRIEF.md`. Replaces the Spec-1
> step-by-step Overview console (`/eval`) with a 6-block **Dashboard**. Reuses
> the established instrument register (`wb-*` vocabulary + `uw-*` tokens) and the
> new KPI backend (`core/kpi_view`, `core/eval_history`, `core/kpi_targets`).
> Route, nav label, and sidebar-collapse behavior are unchanged except the nav
> label "Overview" → **"Dashboard"**.

## Problem

A product manager looking at `/eval` today is walked through a linear decision
funnel (how bad → where → why → priority → decision) that *interprets* the data
for them with prose hypotheses and recommendation cards. But the PM doesn't want
the tool's opinion — they want to **see the numbers and form their own insight**,
fast, all at once. They also can't answer the questions they actually have:
"are we hitting our quality target?", "is this eval improving across runs?",
"which failure mode dominates?", "which claim shapes break?". The funnel hides
those behind narrative steps, and there's no notion of a target or of progress
over time.

## Solution

A dense, glanceable **dashboard** of six blocks in two rows — pure visualization
and numbers, no machine-written insight. Row 1 reads the *current* eval state
(what set, how bad, where it breaks); row 2 maps that state against *targets and
time* (vs goal, trajectory toward goal, set the goal). The PM scans the grid,
spots the red zones themselves, and decides. The trace-set selector and Run-eval
control live **inside** the dashboard (Block 1), not in a floating header.

## Experience Principles

1. **Show, don't conclude** — every block is a chart or a number; the dashboard
   never writes "the problem is X" or "you should do Y". Insight is the PM's job.
2. **The whole state at a glance** — six blocks on one instrument surface, no
   funnel, minimal scrolling at 1280–1440. Density over hand-holding.
3. **Color is the measurement** *(inherited)* — the red→amber→teal scale means
   FAIL-rate/valence only; all controls, selectors, and chrome stay indigo.

## Aesthetic Direction

- **Philosophy**: **Instrument panel** — Bloomberg/trading-terminal density,
  mono numerals, hairline-ruled cards, calm cool canvas. The same instrument
  register the console and Comparison already use.
- **Tone**: clinical, precise, fast. A readout, not a report.
- **Reference points**: Grafana/Datadog dashboards, a trading terminal, the
  existing PatentDiff console (`wb-kpi` tiles, themed `dash_table`, the diverging
  heatmap).
- **Anti-references**: the step-by-step funnel it replaces; narrative
  "executive summary" cards; gauges/rainbow KPIs; any prose that interprets the
  data for the user.

## Existing Patterns

- **Typography**: Inter (body/display), IBM Plex / JetBrains Mono (all numerals,
  IDs, table cells). `--font-size-*` ramp.
- **Colors**: cool instrument canvas `--color-bg-primary`; indigo chrome
  `--color-accent-primary`; reserved data scale `--data-fail-0…100` (heatmap +
  valence only); status `--color-status-*`.
- **Spacing / chrome**: `--space-*`, `--card-padding`, `--section-gap`,
  `--control-bar-*`, `--kpi-rule-width`.
- **Components (reuse as-is)**: `wb-kpi` tiles, the themed `dash_table`, the
  diverging heatmap (`app_workbench/heatmap.py`), `wb-dropdown`/`wb-segmented`
  controls, the `wb-controlbar` run-eval button + status (relocated into Block 1).
- **Backend (already built)**: `core/kpi_view.{current_pass_rate,series,trajectory}`,
  `core/kpi_targets.{get,set}_target`, `core/eval_history` (dated runs).

## Component Inventory

| Component | Status | Notes |
| --- | --- | --- |
| Dashboard 6-block grid (`uw-dash*`) | New | 2×3 CSS grid on the instrument surface; the shell for everything below. |
| Block 1 · Trace Properties | New (relocates existing controls) | Trace-set selector + **Run eval** button + status + last-run + run metadata (eval timestamps from `eval_history`, prompt version, n scored). Static card, not a floating header. |
| Block 2 · Eval-result summary | New | Eval selector (PHOSITA/Citation) → horizontal bars of **failure-mode share of FAILs** (taxonomy), mono % + n. Replaces the "how bad" KPIs. |
| Block 3 · Dimension heatmap | Modify (`app_workbench/heatmap.py`) | Two dimension dropdowns (row, col) chosen from `claim_type` · `claim_length` · `relationship`; cells = FAIL-rate via `--data-*`. Replaces the fixed "where" matrix. |
| Block 4 · Eval score vs KPI target | New | Current PASS-rate vs target for each eval kind — a bar/marker readout with the gap to goal. Reads `kpi_view.current_pass_rate` + `kpi_targets`. |
| Block 5 · Metric trajectory | New | **Baseline → current → expected** progress chart on a time axis (3 dated points + gap-to-target). Reads `kpi_view.trajectory`. |
| Block 6 · Set KPI target | New | PM inputs: target PASS-rate, target date, baseline run; writes `kpi_targets.set_target`. Persists; Blocks 4/5 update. |
| Failure-mode aggregation helper | New (small) | For Block 2: among traces the selected eval marked FAIL, count human-annotated `failure_modes` (`traces_annotations.jsonl` + `failure_taxonomy.json`) → share per mode. *Existing data; if non-trivial, brainstorm before building.* |
| Step-rail / why / priority / decision | **Removed** | The funnel sections and their callbacks are deleted from `/eval`. |

## Key Interactions

- **Trace-set select (Block 1):** choosing a set refreshes every block for that
  set (drives the existing `corpus-selector` → section callbacks, now pointed at
  the blocks). No eval runs on selection.
- **Run eval (Block 1):** explicit button only (the n_clicks guard already
  prevents run-on-navigation); disables + streams status while running; on
  completion appends an `eval_history` record and refreshes blocks via
  `data-version`.
- **Eval select (Block 2):** segmented PHOSITA/Citation → re-renders the
  failure-mode bar chart for that eval.
- **Heatmap dimensions (Block 3):** two dropdowns (row, col) → regenerates the
  heatmap; same diverging scale, cells print value + n (never color-only).
- **Set target (Block 6):** entering target rate + date (+ baseline run) writes
  the target; Blocks 4 (gap) and 5 (expected point) update immediately.

## Responsive Behavior

Desktop-first, optimized 1280–1440. The 2×3 grid holds at ≥1280; at ~1024 it
degrades to a single column of stacked blocks (each chart full-width,
horizontally scrollable tables/heatmap). No phone layout. The sidebar keeps its
icon-collapse on `/eval` so the dashboard leads the left edge.

## Accessibility Requirements

- Inherited contrast law: numerals/body ≥ 4.5:1, UI ≥ 3:1, both themes; the
  diverging scale stays colorblind-safe teal→amber→red and **every** colored
  cell prints its value + n (color is never the only signal).
- Focus rings indigo (`--focus-ring`) on selectors, dropdowns, the run button,
  and target inputs; all keyboard-reachable.
- Charts (Plotly) carry text labels/legends; the failure-mode bars and KPI
  readouts are legible in grayscale (length + number, not hue alone).
- Dark mode: both register palettes already covered; Plotly figures recolor via
  the existing `theme` store.

## Out of Scope

- **No new eval/backend data model** beyond the already-built `kpi_view` /
  `eval_history` / `kpi_targets` (frozen ruler). The only new backend is the
  small Block-2 failure-mode aggregation helper over existing data.
- **No multi-chart-type toggle** for the over-time view — one chart
  (baseline→current→expected) was chosen.
- **No per-(eval × set) targets**, no composite score, no PM-defined metrics.
- **No restyle of Prototype / Traces / Comparison** — this brief is `/eval` only.
- **No machine-written insight/recommendation** anywhere on the dashboard.
