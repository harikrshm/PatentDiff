# Design Brief: Comparison — Experiment Tracker

> Visual restyle of the **already-functional** Comparison tab (`/eval/comparison`,
> `app_unified/pages/eval_comparison.py`). The data layer, charts, and table exist and pass
> tests (225); this brief covers the visual layer only. It extends the existing `uw-*`
> "analyst's workbench" system — it does not introduce a parallel design language.

## Problem

A PM running experiments to drive down the model's eval failure rate has no calm, at-a-glance read
of whether the last few experiments are actually working. The numbers exist, but the current tab
shows them in colors and cards that fight the rest of the app: chart bars use the chrome indigo
(which everywhere else means "interactive," never data), the cards don't match the dashboard's
instrument cards, and the charts don't follow the light/dark toggle the PM uses everywhere else. The
result reads like a bolt-on, not part of the workbench.

## Solution

A measurement bench that reads like the rest of the instrument register: three framed instrument
cards across the top (eval FAIL-rate, latency, tokens) showing the last four experiments as
grouped bars, and an experiment-history table below. The newest experiment is gently brought
forward so the eye lands on "where we are now," and the whole surface recolors correctly in both
themes. Falling bars and green ▼ deltas tell the improvement story without the design having to
shout it.

## Experience Principles

1. **Consistency over novelty** — every color, card, and numeral comes from the existing `uw-*` /
   workbench token system. This tab should be indistinguishable in register from the `/eval`
   dashboard. No new visual language, only a new arrangement.
2. **Data colors are earned, chrome colors are reserved** — indigo stays chrome (selection, focus,
   nav), red/teal stay good/bad valence, and neutral categorical series (PHOSITA vs Citation, P50
   vs P99, Input vs Output) get their own dedicated, theme-aware data palette so nothing carries
   accidental meaning.
3. **Trend first, decoration last** — the shape of the trend and the delta arrows carry the
   message; emphasis is a whisper (the newest experiment), never a scoreboard.

## Aesthetic Direction

- **Philosophy**: "Analyst's workbench / instrument register" (the project's established
  philosophy; see `.design/unified-workbench/DESIGN_BRIEF.md`). Cool data canvas, hairline-framed
  cards, tabular mono numerals, restraint.
- **Tone**: Calm, clinical, precise. A measurement readout, not a marketing dashboard.
- **Reference points**: Weights & Biases experiment tables (structure), Linear/Vercel analytics
  (restraint), the project's own `/eval` dashboard instrument cards (direct sibling).
- **Anti-references**: Rainbow BI dashboards; glossy gradients/drop-shadows; indigo-everything;
  charts that look like a different app than the table beneath them.

## Existing Patterns

Defined in `app_unified/assets/workbench.css` (tokens) + `app_unified/assets/unified.css` (`uw-*`).

- **Typography**: body `--font-family-body`; mono `--font-family-mono` (tabular-nums) for all
  numerals/kickers; sizes via `--font-size-*`.
- **Colors**: surfaces `--color-bg-primary/secondary/tertiary`; borders
  `--color-border-primary/secondary`; chrome accent `--color-accent-primary` (#4F46E5 light /
  #7C74F0 dark) — **chrome only**; valence `--color-status-success` (teal) / `--color-status-error`
  (red); dark theme via `[data-theme="dark"]` and `prefers-color-scheme`.
- **Spacing**: `--space-1..8` (4px base); cards use `--card-padding` (= `--space-5`); radius
  `--border-radius-md` (6px).
- **Components**: `uw-dash__block` instrument card (head = kicker + title; body), the page header
  (`page_header`), and the mono/hairline `dash_table` styling idiom already in this file. The
  theme-callback chart pattern in `app_workbench/callbacks.py` (`_fm_figure(rows, theme)`,
  `Input("theme","data")`, `dark = theme == "dark"`).

## New Tokens

Add to `workbench.css` `:root` (light) and `[data-theme="dark"]` (dark) — a categorical **data**
palette, distinct from chrome and valence, legible on the card surface in both themes:

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--data-cat-1` | slate-blue (e.g. `#3B6EA5`) | lighter slate-blue (e.g. `#6FA8DC`) | series A: PHOSITA / P50 / Input |
| `--data-cat-2` | amber/ochre (e.g. `#C98A2B`) | lighter amber (e.g. `#E0B25C`) | series B: Citation / P99 / Output |

(Exact hex set in the design-tokens-adjacent step; must clear 3:1 contrast against both card
surfaces and be distinguishable from each other and from red/teal.)

## Component Inventory

| Component | Status | Notes |
| --- | --- | --- |
| Chart card (`uw-compare__chart`) | Modify | Re-base on `uw-dash__block` look: `--color-bg-secondary`, `--border-radius-md`, `--card-padding`. Fix the non-existent `--radius-md`/`--color-surface-raised` refs. |
| Chart-row grid (`uw-compare__charts`) | Modify | Keep 3-up grid; align gap to `--space-5` like the dash grid; stacks ≤1024 (match the app's breakpoint, not 920). |
| Grouped-bar figures (3) | Modify | Move from static-at-import to a theme `@callback`; builders take `dark: bool`; bars use `--data-cat-1/2` resolved to hex per theme; oldest→newest opacity ramp (~0.7→1.0). |
| Experiment history table | Modify | Keep mono/hairline idiom; add newest-row emphasis (indigo selection rail + faint bg tint). Delta ▼green/▲red unchanged. |
| Card kicker/title | Modify | Use `uw-dash__block-kicker`/`-title` vocabulary so heads match the dashboard exactly. |
| Old comparison CSS (`__controls`,`__kpis`,`__matrix`,`__flips`,`__flip*`,`__empty*`) | Remove | Dead since the rewrite; delete to prevent drift. |
| Data palette tokens | New | `--data-cat-1`, `--data-cat-2` (light + dark). |

## Key Interactions

- **Theme toggle**: flipping light/dark recolors the three charts (axis ticks/titles, gridlines,
  bar fills) via the theme callback, in lock-step with the CSS-themed table and chrome — no stale
  light-mode chart left stranded on a dark surface.
- **Newest-experiment emphasis**: rightmost bar group renders at full opacity, older groups
  recede (~0.7); the top table row carries a 3px indigo left rail + faint `--color-accent-primary`
  bg wash (≈8% alpha). Static (no hover behavior required), purely orienting.
- **Hover (charts)**: Plotly tooltip shows experiment name + exact value (mono); modebar stays
  hidden. No click behavior.
- **Empty/missing manifest**: if `last_n(4)` is empty, show one calm instrument empty-state card
  (reuse the `uw-compare__empty` dashed-card pattern) instead of three blank chart boxes.

## Responsive Behavior

- ≥1024px: three chart cards in one row; table full width below.
- ≤1024px: chart cards stack to one column (match the app-wide `@media (max-width: 1024px)`
  breakpoint already used by `uw-dash__grid` and `uw-compare`); table scrolls horizontally via its
  existing `overflowX: auto`. Standardize away the stray 920px breakpoint added in Task 7.

## Accessibility Requirements

- `--data-cat-1` vs `--data-cat-2` must be distinguishable for common color-vision deficiencies;
  because they sit in a legend + axis context (not encoding good/bad), pair them with text labels
  (series names in the legend) — never rely on color alone. Bars also differ by position/label.
- Delta valence in the table is already text-paired (▼/▲ + signed pp) so it is not color-only.
- All numerals tabular mono for scannability.
- Chart text (ticks/titles/legend) ≥ 4.5:1 against the card surface in both themes; bar fills ≥
  3:1 (non-text graphical contrast).
- Newest-row indigo emphasis is decorative; row content remains full-contrast text.
- Focus rings on any focusable controls use `--focus-ring` (indigo), never data colors.

## Out of Scope

- Any data-layer change (`core/experiments.py`, manifest, seed) — done and frozen.
- Seed-data realism (flat eval bars; `prompt-v2` citation 0.04 artifact) — tracked separately;
  this brief does not "fix" the numbers, only how they're drawn.
- New chart types, a KPI target reference line on charts, per-experiment drill-down, selectors, or
  sorting/filtering the table.
- Writing the manifest from the live run pipeline.
- Touching the `/eval` dashboard, Prototype, or Traces pages.
