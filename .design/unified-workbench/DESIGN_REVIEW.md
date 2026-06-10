# Design Review: Unified Workbench

Reviewed against: `.design/unified-workbench/DESIGN_BRIEF.md` (+ IA, tokens)
Philosophy: **Analyst's workbench — one token system, two registers (memo / instrument)**
Date: 2026-06-11

## Screenshots Captured

| Screenshot | Breakpoint | Description |
| --- | --- | --- |
| `screenshots/review-home-light-1280.png` | Desktop 1280 | Prototype memo form, light |
| `screenshots/review-home-light-1440.png` | Desktop 1440 | Prototype memo form, wide |
| `screenshots/review-home-light-1024.png` | 1024 degrade | Sidebar icon-rail + memo columns stacked |
| `screenshots/review-home-dark-1280.png` | Desktop 1280 | Memo dark (warm brown-black) |
| `screenshots/review-overview-light-1280.png` | Desktop 1280 | Console, sidebar collapsed to icons |
| `screenshots/review-overview-light-1440.png` | Desktop 1440 | Console, wide |
| `screenshots/review-overview-light-1024.png` | 1024 degrade | Console |
| `screenshots/review-overview-dark-1280.png` | Desktop 1280 | Console dark (cool), figures recolored |
| `screenshots/review-traces-light-1280.png` | Desktop 1280 | Memo three-pane, trace loaded |
| `screenshots/review-traces-light-1440.png` | Desktop 1440 | Traces, wide |
| `screenshots/review-traces-light-1024.png` | 1024 degrade | Traces |
| `screenshots/review-traces-dark-1280.png` | Desktop 1280 | Traces dark |
| `screenshots/review-comparison-light-1280.png` | Desktop 1280 | Instrument surfaces |
| `screenshots/review-comparison-light-1440.png` | Desktop 1440 | Comparison, wide |
| `screenshots/review-comparison-light-1024.png` | 1024 degrade | Comparison |
| `screenshots/review-comparison-dark-1280.png` | Desktop 1280 | Comparison dark (cool) |

> All screenshots in `.design/unified-workbench/screenshots/`. Captured via Playmwright
> against `python -m app_unified.app` on `:8050`. The blue floating control bottom-right
> is Dash's dev-tools button (`debug=True`), not part of the design.

## Summary

The build delivers the brief's core thesis: one frame (left sidebar + top toolbar) holding
two clearly different registers — a **warm typeset memo** (Prototype, Traces) and a **cool
mono instrument** (Overview, Comparison) — that read as one lineage, not two products. The
register hand-off, sidebar icon-collapse on `/eval`, color-as-data discipline, and full-app
theme toggle (including the console's Plotly figures) all hold in both light and dark. Two
polish defects found during the visual pass — cramped KPI tiles and a red-default checkbox —
were fixed and re-verified.

## Must Fix

_None._ No broken functionality, accessibility failures, or major brief deviations.

## Should Fix

1. **KPI tiles rendered inline/cramped** (`review-comparison-light-1280.png`, original capture):
   `wb-kpi__label/__value/__sub` are `html.Span`s (inline), so they ran together
   ("55.2%n=87", "DELTA+0.0 pp PASS rate"). _Fixed:_ scoped `display:block` override in
   `unified.css` (`.uw-compare__kpi .wb-kpi__*`). Re-verified — tiles now stack like the
   console KPI vocabulary.
2. **Reviewed checkbox used the browser-default red accent** (`review-traces-light-1280.png`,
   original): red reads as a data color, violating "indigo for all chrome." _Fixed:_
   `accent-color: var(--color-accent-primary)` on the reviewed checkbox. Re-verified indigo.

## Could Improve

1. **Memo claim/spec wells are tall (200px) and mostly empty** on first load — a lot of cream
   above the fold. _Suggestion:_ consider a smaller default height that grows, or a subtle
   placeholder, so the drafting surface feels less vacant before input.
2. **`debug=True` dev button** shows in captures. _Suggestion:_ run with `debug=False` for any
   shipped/demo build; harmless in local dev.

## What Works Well

- **Register distinction survives grayscale and theme.** Memo (warm paper, serif, human/machine
  voice wells) vs instrument (cool canvas, mono numerals, hairline tables) differ in type,
  density, and surface temperature — not just color. Confirmed in dark: memo is warm brown-black
  (`review-home-dark-1280.png`), instrument is cool (`review-comparison-dark-1280.png`).
- **The frame is constant.** Sidebar + toolbar are identical across all four routes; only the
  content surface changes — exactly the brief's "different kind of work, not a different app."
- **Sidebar icon-collapse on `/eval`** works with no content jump; the console's own step-rail
  leads the left edge and the two top bars stack cleanly (no double-rail / overlap — the T7
  scroll-container fix holds).
- **Color is a measurement, app-wide.** Only valence cells carry tint (Y = patentability fail in
  the prototype; PASS→FAIL / FAIL→PASS flips in the matrix), always paired with the value text,
  via low-alpha washes that keep numerals at full contrast in both themes.
- **One token system.** Every `uw-*` surface consumes the canonical tokens; the global toggle
  recolors `uw-*` and `wb-*` together, including server-rendered Plotly figures.
- **Accessibility:** verified body/numeral contrast ≥ 4.5:1 for memo, voice-human, and
  voice-machine text in both themes; indigo focus rings; collapsed sidebar items keep their
  accessible names (labels stay in the DOM, opacity-hidden).
