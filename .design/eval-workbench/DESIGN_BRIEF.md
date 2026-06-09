# Design Brief: Eval Workbench — Analyst Console Redesign

> Supersedes the visual/structural layer of `docs/superpowers/specs/2026-06-05-eval-workbench-dashboard-design.md`.
> The functional core of that spec (data loading, diagnostics, priority scoring, file persistence,
> "guides not decides" rule) stays intact. This brief changes **how it looks and how it flows**:
> from a two-page draggable BI grid into a single guided analyst narrative.

## Problem

A product manager has just run the eval suite against PatentDiff's outputs. They are now staring at
raw numbers and a generic, default-styled Dash app and are expected to walk a hard arc in their head —
*how bad is it → where does it fail → why (which architecture layer) → what do we fix first* — and then
**own** that decision with a defensible rationale.

The current build makes this harder than it should be. It is a pile of widgets in a rearrangeable grid
with scattered inline styling, a generic drag-drop pivot table, and ad-hoc red/green/blue hex codes used
inconsistently for both data and chrome. Nothing carries the PM through the decision. The flexibility
(drag any widget anywhere, pivot any dimension) is BI-tool freedom that the PM doesn't want at decision
time — it adds choices instead of removing them. Worst of all, the product's whole point — *the app
offers a hypothesis, the PM makes the call* — is visually invisible: a machine guess and a human
conclusion look identical on screen.

## Solution

A single-screen **analyst console** the PM reads top to bottom like an instrument panel. It walks the
decision arc as one deliberate scrolling narrative — **how bad → where → why → priority → decision** —
with each section answering the previous one's question. Numbers read like a data instrument (monospace,
tabular, quiet). The heatmap is a custom, calm, colorblind-safe matrix, not a generic pivot. And the
console speaks in two unmistakably different voices: a **machine HYPOTHESIS voice** (deterministic,
templated, never a verdict) and a distinct **your-voice** for everything the PM inputs or concludes.
The console guides; the PM decides — and the screen makes that obvious at every step.

## Experience Principles

1. **The funnel decides the layout, not the PM** — A fixed, curated top-to-bottom order beats a
   draggable grid. Removing arrangement choices is the feature: the screen *is* the decision arc, so the
   PM spends attention on the judgment, not on configuring widgets.

2. **The machine guesses, the human concludes — and you can always tell which is which** — Every
   data-derived statement carries one of two visually distinct treatments: a templated HYPOTHESIS
   (machine voice) or a PM input (your voice). They never blur. A conclusion the app computed and a
   conclusion the PM owns must never look the same.

3. **Color is a measurement, not decoration** — The red→(amber)→teal diverging scale means exactly one
   thing: FAIL rate. Chrome, buttons, and interactive accents use a separate neutral indigo. If something
   is colored on the good/bad axis, it is data. This discipline is what separates a calm analyst console
   from a noisy dashboard.

## Aesthetic Direction

- **Philosophy**: **Analyst console / instrument panel.** Dense but calm, information-forward, quiet
  chrome. Every pixel earns its place. Restraint as confidence.
- **Tone**: Composed, precise, trustworthy. Clinical without being cold. The register of a well-set
  decision memo rendered as a working instrument.
- **Reference points**: Linear (quiet chrome, taut spacing, monochrome discipline), Bloomberg/trading
  terminals (data density, mono numerals, instrument feel), Stripe Dashboard (calm light-mode data
  surfaces), a well-typeset analyst report.
- **Anti-references**: Generic AI SaaS template (rounded pastel cards, soft drop shadows, friendly
  emoji). Busy "executive dashboard" with gauges and rainbow KPIs. The current default-Dash look. The
  prior dark-navy `#1a1a2e` mockup — its density instinct was right, but we are going **light primary**.

## Existing Patterns

There is **no design system to inherit** — no CSS files, no `assets/` folder, no tokens, no Tailwind, no
component library. Styling today is inline `style={...}` dicts scattered across the worktree build. This
redesign establishes the system from scratch.

- **Typography**: System default (Dash/browser default sans). No font loading exists. → Establishing
  Inter (prose/labels) + IBM Plex Mono / JetBrains Mono (all metrics & table numerals).
- **Colors**: Ad-hoc inline hex in `app_workbench/components.py` — `GREEN #2e7d32`, `YELLOW #f9a825`,
  `RED #c62828`, HYPOTHESIS blue `#1565c0` on `#e3f2fd`, greys `#555/#888/#e0e0e0`. Used for both data
  and chrome with no discipline. → Replacing with a tokenized palette: neutral indigo accent for chrome,
  a reserved diverging scale for FAIL-rate data only.
- **Spacing**: Inline rem/px values (`0.6rem`, `0.75rem`, `8px`) with no scale. → Establishing a token
  spacing scale.
- **Components**: `kpi_tile()`, `assumed_badge()` (⚠ assumed), `evidence_note()` (HYPOTHESIS chip),
  `fail_color()` in `components.py`. These are the right *concepts* and will be **rebuilt against tokens**,
  not reused as-is.
- **Stack constraint**: Plotly **Dash**. Styling via a single hand-authored CSS file with custom-property
  tokens in `app_workbench/assets/`; Plotly figures themed via a shared `go.layout.Template`.

## Component Inventory

| Component | Status | Notes |
| --- | --- | --- |
| Token stylesheet (`assets/workbench.css`) | New | CSS custom properties: palette, spacing, type ramp, radii, light + dark. |
| Plotly theme template | New | Shared `layout.Template` — fonts, gridlines, diverging colorscale, margins. |
| Sticky control bar | New | Corpus selector + Run-eval button + last-run timestamp + light/dark toggle. Persistent across the scroll. |
| KPI tile | Modify | Rebuild `kpi_tile()` against tokens — mono numerals, valence-tinted left rule, n-count. |
| Section header / step marker | New | Numbered funnel markers (1 How bad · 2 Where · 3 Why · 4 Priority · 5 Decision). |
| Custom heatmap (claim profile × relationship) | New | Replaces `dash-pivottable`. Themed Plotly, colorblind-safe diverging, % printed per cell, n<3 ⚠ flag. |
| Eval / dimension toggle | Modify | Segmented control (PHOSITA · Citation · Either) styled to tokens, not default `RadioItems`. |
| HYPOTHESIS note (machine voice) | Modify | Rebuild `evidence_note()` — distinct "machine voice" treatment, dispersion + gradient numbers inline. |
| PM rationale / comment field (your voice) | New | The visually distinct "your voice" counterpart — input affordance, persisted, paired with each hypothesis. |
| ⚠ assumed badge | Modify | Rebuild `assumed_badge()` to tokens; consistent tooltip. |
| Priority table (Freq × Impact × Exposure) | Modify | Themed `dash_table` — mono numerals, score-driven row emphasis, tier dropdowns inline. |
| Layer / impact / exposure inputs | Modify | Tokenized dropdowns/segmented controls, each carrying the your-voice treatment. |
| Decision block + rationale capture | Modify | Closing section — ordered cheapest-layer-first recommendation + required PM rationale. |

## Key Interactions

- **Scroll = decision arc.** The PM scrolls one screen through five numbered sections. Each section's
  output sets up the next ("FAIL is concentrated here → why? → which layer? → fix order").
- **Corpus switch** (sticky top): selecting a trace set re-derives every number on the page from that
  set. The control bar stays pinned so the active corpus is always visible while scrolling.
- **Run eval** (sticky top): background job; button disables + shows live status while running, then
  refreshes the page's data on completion. Never blocks the scroll.
- **Eval toggle** (PHOSITA / Citation / Either) re-renders the heatmap and the shape-read hypothesis
  together — they always agree.
- **Hypothesis → your call.** Each HYPOTHESIS note sits beside its PM-input counterpart. The PM reads the
  machine's templated guess (with the spread/gradient numbers exposed so small-n cells can be discounted),
  then records their own conclusion in the visually distinct your-voice field. Saved to disk.
- **Priority table is live.** Changing an Impact or Exposure tier re-sorts the Freq×Impact×Exposure table
  instantly; every assumed input wears a ⚠ badge with an explanatory tooltip.
- **Decision capture** is the terminal action: the PM assigns the architecture layer per failure mode and
  writes the required ordering rationale — the audit trail for *why this order*.

## Responsive Behavior

Desktop-first, single-user local tool. Optimized for **1280–1440** monitors; remains usable down to
**~1024** laptop (KPI tiles wrap, heatmap stays scrollable, control bar stays sticky). **No mobile/tablet
layout** — out of scope. Below ~1024 the grid degrades gracefully rather than reflowing to a phone layout.

## Accessibility Requirements

- **Color is never the only signal.** Every heatmap cell prints its FAIL % and n; pass/fail states pair
  color with text/iconography. Heatmap uses a **colorblind-safe** diverging scale (teal→amber→red), not
  red→green.
- **Contrast**: body text and numerals ≥ 4.5:1; large/heading text and UI affordances ≥ 3:1, in both
  light and dark modes.
- **Keyboard**: all controls (corpus selector, toggles, tier dropdowns, run-eval, rationale fields)
  reachable and operable by keyboard with a visible focus ring (uses the indigo chrome accent, never the
  data red/green).
- **Voice distinction is not color-dependent**: HYPOTHESIS vs your-voice are distinguished by label +
  shape/treatment as well as hue, so the core motif survives grayscale.
- **Tooltips** (e.g. ⚠ assumed) are supplementary, never the sole carrier of meaning.

## Out of Scope

- **Trace ingest / generation** — confirmed out per the original spec; the console only measures existing
  trace sets.
- **The draggable/resizable widget grid** — explicitly dropped (removes original spec success criterion #4).
- **`dash-pivottable` freeform pivot builder** — replaced by the curated custom heatmap with toggles.
- **Two-page split (Explore / Decision routes)** — merged into one scrolling narrative.
- **Any change to eval/judge logic** — the measurement ruler stays frozen (`core/phosita_eval.py`,
  `core/citation_eval.py`, judge prompts untouched).
- **Mobile/tablet layouts, auth/multi-user, deployment/hosting, historical trending** — all out.
- **Real Exposure/query-mix data** — Exposure tiers remain PM-assumed placeholders (⚠ flagged) until the
  live query distribution is instrumented; instrumenting it is out of scope here.
