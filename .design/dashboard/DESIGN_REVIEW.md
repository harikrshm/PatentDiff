# Design Review: Eval Dashboard (Overview → Dashboard)

Reviewed against: `.design/dashboard/DESIGN_BRIEF.md`
Philosophy: **Instrument panel** — "show, don't conclude"
Date: 2026-06-12

## Screenshots Captured

| Screenshot | Breakpoint | Description |
| --- | --- | --- |
| `screenshots/review-dashboard-desktop-1280.png` | Desktop 1280 | Full 6-block grid, light (post-fix) |
| `screenshots/review-dashboard-desktop-1440.png` | Desktop 1440 | Full grid, light |
| `screenshots/review-dashboard-degrade-1024.png` | 1024 | Single-column degrade |
| `screenshots/review-dashboard-dark-1280.png` | Desktop 1280 | Full grid, dark |
| `screenshots/review-block3-1280-real.png` | Block 3 @1280 | Heatmap **clipping** (before fix) |
| `screenshots/review-block3-1280-fixed2.png` | Block 3 @1280 | Heatmap fits all 3 columns (after fix) |
| `screenshots/t7-block4-after-save.png` | Block 4 | Live refresh after a target save |

> Desktop-first tool; mobile/tablet (375/768) are **out of scope per the brief**,
> so breakpoints are 1280 / 1440 / ~1024, plus dark. All in
> `.design/dashboard/screenshots/`.

## Summary

The dashboard fully realizes the brief: a 2×3 instrument grid that replaced the
step-by-step funnel with pure visualization + numbers and **no machine-written
insight**. The one real defect found — Block 3's heatmap clipping its rightmost
("Novel") column at 1280 because the graph was built inside a callback and missed
Plotly's responsive resize — was fixed during the review (static graph in layout
+ figure output, colorbar removed as redundant). Tests stay green (210).

## Must Fix

_None outstanding._ The heatmap clip (data hidden — see
`review-block3-1280-real.png`) was **fixed during review**: the heatmap is now a
static `dcc.Graph` whose figure is set by the callback, so it sizes
responsively; the redundant colorbar was removed (cells already print % + n).
Verified in `review-block3-1280-fixed2.png`.

## Should Fix

1. **Uneven row heights leave whitespace under Blocks 1–2** (`review-dashboard-desktop-1280.png`):
   Block 3 (heatmap) is much taller than Blocks 1–2, and CSS grid ties row 2's top
   to row 1's tallest cell, so a gap sits under the short cards. Partly mitigated
   by trimming Block 3's caption. _Fix: a masonry/independent-row layout (CSS
   `columns` or JS packing), or cap the heatmap block height, if tighter density
   is wanted. Acceptable as-is for an instrument dashboard (Grafana-style panels
   are commonly uneven)._

## Could Improve

1. **Trajectory baseline≈current points overlap** (`review-dashboard-desktop-1440.png`):
   backfilled history shares one date, so the "actual" segment is a dot. Resolves
   naturally as real dated runs accumulate; no action needed now.
2. **Dash dev-tools button** appears in captures (`debug=True`). Run with
   `debug=False` for any shipped/demo build.

## What Works Well

- **"Show, don't conclude" holds.** Every block is a chart or a number — no
  hypotheses, no recommendation cards. The funnel (why/priority/decision) and its
  step-rail are gone.
- **Color-as-data discipline.** The diverging scale appears only on the heatmap +
  failure bars + gap/valence; all chrome (selectors, run/save buttons, fills,
  focus) is indigo. Every heatmap/bar value is paired with its number, so the
  signal survives grayscale.
- **One token system, two registers honored.** The dashboard reuses the console's
  `wb-kpi`/heatmap/dropdown vocabulary on the cool instrument canvas; charts use
  transparent backgrounds + theme-aware fonts so the **theme toggle recolors the
  whole grid including Plotly** (`review-dashboard-dark-1280.png`).
- **Live wiring.** Trace-set → all blocks; Run eval → refresh; **Set target →
  Blocks 4/5 update without reload** (`t7-block4-after-save.png`). Selecting a set
  never triggers an eval run (the original bug, fixed + regression-tested).
- **Responsive degrade.** 3-col → 1-col at ≤1024 (verified via computed
  `grid-template-columns`); instrument content stays legible.
- **Accessibility.** Indigo focus rings on all controls; instrument text/numerals
  ≥ 4.5:1 in both themes (token-verified earlier); charts carry text labels.
