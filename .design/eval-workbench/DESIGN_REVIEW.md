# Design Review: Eval Workbench — Analyst Console

Reviewed against: DESIGN_BRIEF.md
Philosophy: Analyst console / instrument panel (Linear × Bloomberg × Stripe)
Date: 2026-06-06
Build: `eval-workbench` worktree · http://127.0.0.1:8050

## Screenshots Captured

| Screenshot | Breakpoint | Description |
| --- | --- | --- |
| `screenshots/review-abovefold-desktop-1440.png` | Desktop 1440 (above fold, @2x) | Control bar, step rail, §1 KPIs, §2 heatmap — close detail |
| `screenshots/review-console-desktop-1280.png` | Desktop 1280 (full page) | Full narrative §1–§5, light |
| `screenshots/review-console-tablet-768.png` | Tablet 768 (full page) | Single-column reflow, light |
| `screenshots/review-console-mobile-375.png` | Mobile 375 (full page) | Degraded layout (out of scope), light |
| `screenshots/review-console-dark-desktop-1280.png` | Desktop 1280 (full page) | Full narrative, dark mode |
| `screenshots/review-console-dark-mobile-375.png` | Mobile 375 (full page) | Dark mode, narrow |
| `screenshots/review-focus-state-1440.png` | Desktop 1440 | After keyboard Tab (focus check) |

> All screenshots are in `.design/eval-workbench/screenshots/`.

## Summary

The build is a faithful, high-quality realization of the brief. The analyst-console
philosophy is unmistakable — quiet chrome, mono numerals, a tight grid, and a calm
data-forward surface — and the single guided narrative (How bad → Where → Why →
Priority → Decision) reads exactly as designed. The two strongest bets paid off: the
**HYPOTHESIS / your-call voice motif** is instantly legible and consistent everywhere
a claim is made, and the **custom heatmap** is a genuine upgrade over the old pivot
(colorblind-safe scale, % + n in every cell, n<3 ⚠). Dark mode is intentional, not an
inversion, and the heatmap correctly recolors with it. No must-fix issues; the
refinements below are polish and a couple of verification items.

## Post-review fixes applied (2026-06-06)

Both **Should Fix** items were addressed after the review:
- **#1 Focus ring** — added an explicit `.Select.is-focused > .Select-control`
  token ring so the dropdown no longer masks `:focus-visible`.
- **#2 "Fully clean" red rule** — the clean tile is now **neutral** (no data-scale
  valence); red/amber rules appear only on the three failure tiles, so red always
  means "more failure." Confirmed in `screenshots/review-kpi-fix-1440.png`.

## Must Fix

_None._ No broken functionality, no contrast failures (T13 fixed all AA gaps), no
brief deviations. The five-section narrative, voice motif, color discipline, and dark
mode all render as specified.

## Should Fix

1. **Confirm the keyboard focus ring visually.** `review-focus-state-1440.png` (after
   two Tabs) doesn't clearly show the indigo ring — the focus likely landed on the
   react-select dropdown, whose internal focus style can mask the token ring. The ring
   is implemented (`:focus-visible` + `:has(input:focus-visible)`), but it should be
   eyeballed by tabbing through corpus selector → segmented toggle → tier dropdowns →
   layer pills → textareas. _Fix: manual keyboard pass; if the dropdown ring is weak,
   add an explicit `.wb-dropdown .Select-control--is-focused { box-shadow: var(--shadow-focus) }`._

2. **"Fully clean" KPI rule reads red (24%).** Correct per the `invert` logic (low
   clean = bad), but on `review-abovefold-desktop-1440.png` a red rule beside the word
   "clean" can momentarily scan as an alarm on a good metric. _Fix: keep the semantics,
   but consider a subtler treatment for the inverted metric (e.g. rule reflects the
   clean value directly, or a small "↑ better" affecting hint) so red always means
   "more failure."_ Low urgency — it is technically accurate.

## Could Improve

1. **Step-rail labels are very small (9px vertical).** On `review-abovefold-desktop-1440.png`
   the rail works and the active step (02 WHERE) is clearly indigo, but the rotated
   labels are near the floor of legibility. _Suggestion: bump to 10px or rely on the
   number + active state and show the label only on hover/active._

2. **Dark-mode heatmap flash on load** for users with a saved dark theme: the figure
   renders light, then the `theme` store updates and it recolors. _Suggestion: gate the
   first heatmap render on the theme store, or set the Store's initial value from a
   cookie so the first paint is already dark._

3. **Loading spinner + empty-cell "—" use fixed colors.** The `dcc.Loading` indigo
   (`#4F46E5`) is a touch dim on the dark canvas, and the heatmap "—" is a fixed gray.
   Both are transient/neutral, but could read from tokens for perfect dark fidelity.

4. **`LAST RUN —` placeholder** until the first in-session run. _Suggestion: seed it
   from the eval file's mtime so it shows the real last-eval time on load._

## What Works Well

- **The voice motif is the standout.** Across §3 and §5 (`review-console-desktop-1280.png`)
  the filled cool-indigo **HYPOTHESIS** blocks and the dashed warm-ochre **YOUR CALL**
  fields are never confusable — exactly the "machine guides, human decides" signature
  the brief demanded, and it survives grayscale by treatment, not just hue.
- **The heatmap.** `review-abovefold-desktop-1440.png`: teal→amber→red is calm and
  colorblind-safe, every cell prints % and n, n<3 is flagged (Method·Long × Novel,
  "50% ⚠ n=2"), and the relationship-average dots reinforce the read. The dark variant
  (`review-console-dark-desktop-1280.png`) recolors cleanly with no pale-cell glow.
- **Color discipline held.** Indigo is the only interactive hue (Run eval, active
  segment, selected layer, links); red/green appear *only* in the heatmap. No "is this
  a button or a warning?" ambiguity anywhere in the captures.
- **Typography & hierarchy.** Inter for prose, IBM Plex Mono for every numeral; the
  `STEP 0X` kicker → title → question pattern gives each section an unmistakable entry
  point, and the mono KPI numerals read like an instrument.
- **Dark mode is designed, not inverted.** Cool slate surfaces, deepened voice tints,
  lifted indigo/red for contrast — it feels like a deliberate second skin.
- **Responsive reflow is real, not just shrinking.** At 768
  (`review-console-tablet-768.png`) the rail goes horizontal, decision cards stack, and
  KPI valence rules become more prominent — the layout reorganizes as intended down to
  the laptop floor. (Mobile 375 is explicitly out of scope and degrades gracefully with
  the heatmap as a scroll region — no broken overflow elsewhere.)
- **Fully tokenized.** Spot-checks show no stray hardcoded chrome colors; light/dark
  switch is a pure variable swap, and the T13 contrast fixes land.
