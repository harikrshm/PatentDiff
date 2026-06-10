# Build Tasks: Unified Workbench

Generated from: .design/unified-workbench/DESIGN_BRIEF.md (+ INFORMATION_ARCHITECTURE.md, DESIGN_TOKENS.css)
Date: 2026-06-10

> **Stack note:** this is a **Plotly Dash** app. "Build" = author `uw-*` CSS consuming the existing tokens
> + adjust Dash component `className`s/markup in `app_unified/`. No React. Backend/callbacks/`core/`
> logic stay frozen. Aesthetic: **"Analyst's workbench" — one token system, two registers** (memo /
> instrument). Verify each task by booting `python -m app_unified.app` and viewing the route.

## Foundation
- [x] **T1 · Token wiring + base stylesheet + fonts** _(establishes the philosophy first)_: Merge the
  three extension groups from `DESIGN_TOKENS.css` (fonts `@import`, `--sidebar-*`, `--memo-*`) into the
  live `app_unified/assets/workbench.css` `:root` + `[data-theme="dark"]` + prefers-color-scheme block.
  Create `app_unified/assets/unified.css` with base `uw-*` primitives consuming tokens: `uw-page`,
  `uw-page--memo` / `uw-page--instrument` surfaces, `uw-label`/`uw-kicker`/`uw-input`/`uw-input--area`/
  `uw-btn`/`uw-btn--primary`/`uw-status`, and the memo prose face (`--font-family-memo`). _Reuses: all
  canonical tokens. New file: `unified.css`. Done = any page renders in Inter/serif/mono with token
  surfaces, no raw browser defaults._

## Core UI
- [x] **T2 · App shell — left sidebar + top toolbar** _(highest visual priority; frames every page)_:
  Replace the Spec-1 horizontal appbar + subnav-slot (in `app_unified/app.py` + `components.py`) with a
  **persistent left sidebar** (PatentDiff · Evaluation › Overview/Traces/Comparison; indigo active rail +
  `--sidebar-item-bg-active`) and a **top contextual toolbar** (reuses `--control-bar-*`; theme toggle
  pinned right). Per-route active state via the existing `url` pathname. _Modifies: `app_unified/app.py`,
  `components.py`. New `uw-sidebar*`, `uw-toolbar*` CSS. Done = Linear-style labeled sidebar + toolbar on
  every route; active item correct._
- [x] **T3 · Sidebar icon-collapse on `/eval`** _(riskiest interaction — do early)_: Collapsed
  (`--sidebar-width-collapsed`) icon state + width transition; sidebar auto-collapses on `/eval` and
  expands on all other routes (extend the existing pathname callback to toggle a root class / `data-`
  attr; clientside or server). Hover/pin temporarily expands. Console step-rail must lead the left edge
  when collapsed. _Modifies: shell callback + CSS. Done = navigating to `/eval` shrinks the sidebar to
  icons with no content jump; leaving restores it; collapsed items keep `aria-label`s._

## Memo register
- [x] **T4 · Prototype `/` — memo form + machine-voice report**: Style the two-column claim/spec form on
  the warm memo surface (`uw-page--memo`): serif reading inputs, `--voice-human-*` field wells, mono for
  the label/ID, single indigo **Analyze**. Render the result as **machine voice** (`--voice-machine-*`):
  element-mapping `dash_table` with mono numerals and Novelty/Inventive/Verdict tinted via the reserved
  `--data-*` scale; overall opinion in serif; run metadata in a quiet `<details>`. _Modifies:
  `app_unified/pages/prototype.py` classNames + `uw-proto*` CSS. Done = `/` reads as a typeset patent
  memo whose output looks measured._
- [x] **T5 · Traces `/eval/traces` — reader + human-voice coder**: Memo three-pane: trace selector
  (memo "contents"), read-only **trace reader** (serif claims/spec/opinion on `--memo-surface`, hairline
  rules), and the **annotation form** as human-voice (segmented PASS/FAIL, taxonomy multiselect, comment
  textarea, reviewed, indigo Save, status). _Modifies: `app_unified/pages/eval_traces.py` + `uw-traces*`
  CSS. Done = reading width is comfortable serif prose; the coder feels like writing on the document._

## Instrument register
- [x] **T6 · Comparison `/eval/comparison` — instrument surfaces**: Style v1 surfaces to the instrument
  register on `uw-page--instrument`: three **KPI tiles** (mono numerals, valence-tinted delta reusing the
  console KPI vocabulary), the **verdict transition matrix** as a themed `dash_table` (mono, hairline,
  `--data-*` tint on flips), and **flipped-trace** lists (mono run-ids). _Modifies:
  `app_unified/pages/eval_comparison.py` + `uw-compare*` CSS; reuses console KPI/table patterns. Done =
  Comparison reads like the console's measurement surfaces, not a plain table._

## Integration & States
- [ ] **T7 · Overview `/eval` integration check** _(no restyle)_: Verify the existing `wb-*` console
  renders correctly inside the new shell, the sidebar-collapse coexists with the step-rail (no double
  left rail, no overlap), and the **global theme toggle recolors `uw-*` AND `wb-*`** (both read the same
  tokens). _Modifies: only glue/CSS adjacencies if needed. Done = `/eval` unchanged in feel; toggle flips
  the whole app, not just the console._
- [ ] **T8 · Interactive states pass**: Hover/focus/active/disabled/loading across sidebar items,
  toolbar controls, segmented toggles, dropdowns, buttons; **empty/error states** for Comparison (missing
  eval file → calm empty readout) and Traces (no trace selected → prompt); Run-eval disabled+streaming
  styling. Covers: hover, focus-visible, active, disabled, loading, empty, error. _Modifies: CSS + minor
  markup. Done = every interactive element has a deliberate state; nothing falls back to browser default._

## Responsive & Polish
- [ ] **T9 · Dark-mode pass (both registers)**: Verify the warm brown-black memo dark vs the cool console
  dark, sidebar dark chrome, voice/data palettes, and that no `uw-*` surface is stranded light in dark
  mode. _Modifies: dark token usage / CSS. Breakpoints: n/a. Done = toggling dark looks intentional in
  every page, both registers._
- [ ] **T10 · Responsive ~1024 + accessibility pass**: Below ~1024 the sidebar defaults to icons, memo
  two-column stacks, instrument tables stay horizontally scrollable (no phone layout). Accessibility:
  indigo focus rings everywhere (never data red/green), body/numeral contrast ≥ 4.5:1 and UI ≥ 3:1 in
  BOTH registers + themes (verify `--memo-text` on `--memo-bg`, `--voice-human-text` on
  `--voice-human-bg`), keyboard reachability of sidebar/toolbar/forms, `aria-label`s on collapsed sidebar
  icons. Breakpoints: 1024, 1280, 1440. _Done = the brief's responsive + a11y requirements all hold._

## Review
- [ ] **Design review**: Run `/design-review` against the brief — screenshots at 1280/1440 (+ ~1024
  degrade) and dark mode for all four routes; check the register hand-off (memo↔instrument feels like one
  app), color-as-data discipline, and the sidebar-collapse behavior on `/eval`.
