# Build Tasks: Comparison — Experiment Tracker (visual restyle)

Generated from: .design/comparison-experiment-tracker/DESIGN_BRIEF.md
Date: 2026-06-13

> Philosophy (established in the brief): **analyst's workbench / instrument register** — cool data
> canvas, hairline-framed cards, tabular mono numerals, restraint. Every value comes from the
> existing `uw-*` / workbench token system. Indigo = chrome only; red/teal = valence; new
> `--data-cat-*` = neutral categorical chart series. Restyle only — no data-layer changes. Each task
> below is a vertical slice (structure + style + interaction) that can be eyeballed on its own.
> Files: `app_unified/assets/workbench.css` (tokens), `app_unified/assets/unified.css` (`uw-*`),
> `app_unified/pages/eval_comparison.py` (page + figures). Tests: `tests/test_comparison_page.py`.
> Verify the suite stays green (`python -m pytest -q`) after each code task.

## Foundation
- [x] **Data palette tokens**: Add a categorical chart palette to `workbench.css` — `--data-cat-1`
  / `--data-cat-2` in `:root` (light) and the `[data-theme="dark"]` block (and the
  `prefers-color-scheme: dark` fallback block). Proposed: light `#3B6EA5` (slate-blue) / `#C98A2B`
  (amber); dark `#6FA8DC` / `#E0B25C`. Done = both tokens resolve in both themes and each clears
  ≥3:1 against the card surface (`--color-bg-secondary`) and is visually distinct from the other
  and from red/teal. _New tokens; reuses the token-file structure._

- [x] **Chart card = instrument card, dead CSS removed**: In `unified.css`, rewrite the
  `.uw-compare__chart` / `.uw-compare__charts` / `.uw-compare__chart-head` / `-title` rules to
  match `.uw-dash__block` exactly (`background: var(--color-bg-secondary)`, `border: 1px solid
  var(--color-border-primary)`, `border-radius: var(--border-radius-md)`, `padding:
  var(--card-padding)`; grid `gap: var(--space-5)`). Reuse `.uw-dash__block-kicker` / `-title`
  vocabulary for the heads. Delete the dead pre-rewrite rules (`.uw-compare__controls`, `__kpis`,
  `__kpi*`, `__matrix`, `__flips`, `__flip*`, and the `__empty*` rules only if not reused by the
  empty-state task — keep `__empty` if the empty-state task reuses it). Done = chart cards are
  pixel-consistent with the `/eval` dashboard cards in both themes; no references to removed
  classes remain (`grep`). _Modifies existing CSS; reuses `uw-dash__block` look._

## Core UI
- [x] **Theme-aware charts via callback + data palette + newest emphasis**: The highest-risk slice;
  do it early to validate the look. In `eval_comparison.py`: (1) make the figure builders take
  `dark: bool` and resolve bar colors to the per-theme hex of `--data-cat-1/2` (mirror
  `app_workbench/callbacks.py:_fm_figure(rows, theme)` — keep a small light/dark hex map in the
  module since Plotly is server-rendered and can't read CSS vars); also theme axis tick/title
  color, gridline color, and legend font for dark vs light. (2) Apply a per-experiment opacity ramp
  so older groups recede (~0.70) and the newest is full (1.0) — via per-bar `marker.opacity` lists
  ordered oldest→newest. (3) Move the three `dcc.Graph`s into a callback: wrap them in a container
  with a stable id and add an `@callback(Output(container,"children"), Input("theme","data"))`
  (shell-owned theme store, same as the dashboard) that rebuilds `experiments_with_metrics()` →
  `build_figures(pairs, dark=...)` → the three `_chart_block`s. Keep `build_figures`/`build_table_rows`
  unit-testable (pure). Update `tests/test_comparison_page.py` so `build_figures(pairs, dark=False)`
  still asserts series names + values, and add a dark-mode call asserting the bar colors differ.
  Done = toggling theme recolors all three charts in lock-step; newest bar group reads forward;
  suite green. _Modifies the page; reuses the dashboard theme-callback pattern._

- [x] **Experiment history table — newest-row emphasis**: In `eval_comparison.py`, give the top
  (newest) table row a 3px indigo left rail + faint `--color-accent-primary` background wash (~8%
  alpha) using `style_data_conditional` keyed on a hidden marker column (e.g. add `"is_newest":
  "1"` to the first row's data dict, mirror of the existing `*_dir` hidden-column technique) so
  only that row is emphasized. Keep the mono/hairline cells and the ▼green/▲red delta coloring
  unchanged. Add a test asserting the newest row carries the marker and older rows do not. Done =
  the newest experiment row is gently brought forward in both themes; deltas unchanged; suite
  green. _Modifies the table; reuses the hidden-marker-column idiom._

## Interactions & States
- [x] **Empty / missing-manifest state**: In `_build_layout()` (or the charts callback), when
  `experiments_with_metrics()` is empty, render one calm instrument empty-state card (reuse the
  `.uw-compare__empty` dashed-card pattern + `uw-compare__empty-title`/`-hint`) reading e.g. "No
  experiments recorded yet — run `scripts/seed_experiments.py` or an experiment to populate this
  view," instead of three blank chart boxes and an empty table. Covers: empty manifest, missing
  `traces/experiments.jsonl`. Add a test (point `last_n`/the loader at a tmp empty manifest) that
  the empty card renders and no chart `dcc.Graph` is emitted. Done = empty state is calm and
  legible in both themes; suite green. _Reuses `uw-compare__empty` (so do NOT delete it in the CSS
  task)._

## Responsive & Polish
- [x] **Responsive + accessibility pass**: Standardize the chart-row stack breakpoint to the
  app-wide `@media (max-width: 1024px)` (remove the stray 920px rule added in Task 7 of the build)
  so it matches `uw-dash__grid`/`uw-compare`. Confirm: charts stack to one column ≤1024 and the
  table keeps `overflowX: auto`; legend series names are always present (color never the sole
  encoding); chart tick/title/legend text ≥4.5:1 and bars ≥3:1 against the card surface in both
  themes; the newest-row indigo wash keeps row text full-contrast; focus rings use `--focus-ring`.
  Done = one breakpoint app-wide, contrast verified in both themes, no color-only encodings.
  _Modifies CSS; accessibility pass per the brief._

## Review
- [ ] **Design review**: Run /design-review against the brief — capture the tab in light + dark at
  desktop/tablet/mobile, check instrument-register consistency with `/eval`, the data-vs-chrome
  color discipline, newest-experiment emphasis, and the empty state.
