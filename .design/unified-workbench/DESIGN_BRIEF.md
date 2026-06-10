# Design Brief: Unified Workbench — One App, Two Registers

> Extends `.design/eval-workbench/DESIGN_BRIEF.md`. That brief established the **analyst-console /
> instrument-panel** aesthetic and the token system now living in `app_unified/assets/workbench.css`.
> This brief does **not** restyle the console — it propagates ONE design lineage across the whole
> unified Dash app (shell + prototype + Traces + Comparison), most of which currently renders unstyled
> (`uw-*` classes are referenced but undefined). **Functionality and backend are unchanged** — this is a
> pure visual/UX pass.

## Problem

PatentDiff's four tools now live behind one Dash app, but only the Overview console is designed. A user
moving from the **prototype** (drafting two patent claims) to **Traces** (reading a trace, coding a
failure) to the **Overview** instrument panel to **Comparison** (did the eval scores move?) crosses four
surfaces that look like four different products — one polished instrument and three raw, unstyled HTML
forms. The global light/dark toggle only recolors the console; the rest stays bright white regardless.
There is no shared frame: no consistent navigation, no shared chrome, nothing that says "these are one
workbench." The user has to re-orient at every tab.

## Solution

One workbench with a **persistent left sidebar** and a quiet **top toolbar**, inside which each surface
speaks one of **two registers drawn from a single token system**:

- a **memo register** for the *document* work — drafting claims (Prototype) and reading/annotating
  traces (Traces): a warm, typeset analyst-report surface built on the existing `--voice-human-*`
  paper palette;
- an **instrument register** for the *measurement* work — the Overview console (unchanged) and
  Comparison: dense, mono-numeral, hairline-ruled, terminal-calm.

Both registers share the same color discipline, type ramp, spacing scale, and indigo chrome — so the app
reads as one lineage with two voices, not two products. The split follows the **activity**, not the
section: you can *tell what kind of thinking a screen asks of you* before you read a word.

## Experience Principles

1. **One workbench, two registers — never two products.** Document surfaces feel like a typeset patent
   memo; measurement surfaces feel like an instrument. They diverge in surface, prose, and density — but
   share tokens, color law, and chrome so the seam never shows. If a screen looks like it came from a
   different app, the principle failed.

2. **The frame is constant; the surface follows the work.** A persistent left sidebar and a single top
   toolbar hold every page. The sidebar recedes (collapses to icons) on the Overview console so its own
   step-rail can lead — the chrome yields to the instrument, never competes with it. Navigation is the
   one thing that never changes shape underfoot.

3. **Color is a measurement, not decoration** *(inherited, enforced app-wide).** The red→amber→teal
   diverging scale means exactly one thing everywhere — FAIL rate / data valence. All chrome, nav,
   buttons, and focus use the neutral indigo accent. Prototype verdicts and Comparison deltas obey the
   same law as the console heatmap. If something is colored on the good/bad axis, it is data.

## Aesthetic Direction

- **Philosophy**: **Analyst's workbench.** Two benches under one roof: a *document bench* (typeset
  decision-memo) and an *instrument bench* (trading-terminal). Restraint as confidence; every pixel earns
  its place; the chrome is quiet so the work is loud.
- **Tone**: Composed, precise, trustworthy. The document register is warmer and more literary (a
  well-set legal opinion); the instrument register is cooler and clinical (a working terminal). Same
  composure, two temperatures.
- **Reference points**: Linear (quiet sidebar chrome, taut spacing, monochrome discipline), Stripe
  Dashboard (calm light data surfaces), Bloomberg/trading terminals (mono numerals, density — instrument
  register), a well-typeset legal memo / analyst report (document register).
- **Anti-references**: Generic AI-SaaS template (rounded pastel cards, soft drop shadows, friendly
  emoji). Busy "executive dashboard" with gauges and rainbow KPIs. **Critically: the memo register's
  "warm paper" must read as a disciplined typeset report — hairline rules, refined prose, mono numerals
  — NOT as soft pastel SaaS.** Warmth comes from the paper tone and typography, never from rounding,
  shadows, or candy color.

## Existing Patterns

The token system is **already established** in `app_unified/assets/workbench.css` (`:root` + dark via
`[data-theme="dark"]`). This brief extends it; it invents no new color/type/spacing language. The
console's `wb-*` classes stay as-is. The new work is authoring `uw-*` classes that consume the SAME
tokens, plus a memo-surface treatment built on the existing voice palette.

- **Typography**: `--font-family-display`/`--font-family-body` = **Inter**; `--font-family-mono` = **IBM
  Plex Mono / JetBrains Mono** (all IDs, metrics, table numerals). Size ramp `--font-size-xs`(11) →
  `--font-size-4xl`(44); weights normal→bold; line-heights tight/normal. *(No font loading exists yet —
  Inter + IBM Plex Mono must be added.)*
- **Colors**: chrome canvas `--color-bg-primary #F5F7FA`, surfaces `--color-bg-secondary #FFF`; indigo
  accent `--color-accent-primary #4F46E5` (+ hover/active, `--accent-fill`/`--on-accent`); status
  success/warning/error; **reserved data scale** `--data-fail-0…100` (heatmap only); **voice motif**
  `--voice-machine-*` (indigo paper) and **`--voice-human-* (#FBF4E7 warm paper, amber)`** — the memo
  register is built on `--voice-human-*` extended to full document surfaces.
- **Spacing / radii / chrome metrics**: token spacing scale (`--space-*`), radii, plus
  `--control-bar-height` and `--step-rail-width` consumed by the console.
- **Components (console, reuse as instrument vocabulary)**: `kpi_tile`, `evidence_note`/`machine_note`
  (machine voice), `human_field` (human voice), `assumed_badge`, the themed `dash_table`, the diverging
  heatmap, segmented controls. The instrument register reuses these; the memo register adapts the
  human-voice field treatment into full-page document surfaces.

## Component Inventory

| Component | Status | Notes |
| --- | --- | --- |
| `uw-*` token-consuming stylesheet | New | New `app_unified/assets/unified.css`; consumes existing `:root` tokens. The single biggest deliverable. |
| Persistent left sidebar (app nav) | New | PatentDiff · Evaluation › Overview/Traces/Comparison. Indigo active state, scroll-spy-free, icon+label. |
| Sidebar collapsed/icon state | New | Auto-collapses to icon strip on `/eval`; restores on hover/pin. Width animates via token. |
| Top contextual toolbar | New | Per-page: corpus selector + Run eval + last-run (eval pages), theme toggle (global, right). Replaces the Spec-1 appbar+subnav strip. |
| Font loading (Inter + IBM Plex Mono) | New | `@font-face`/CDN; none loaded today. |
| Memo page surface (document register) | New | Warm `--voice-human` paper canvas, hairline rules, prose type, mono for IDs/numerals. Used by Prototype + Traces. |
| Prototype claim/spec form | Modify | Two-column memo layout; inputs as typeset fields; **machine-voice** treatment for the LLM report + verdict table (verdicts tinted via reserved data scale). |
| Traces 3-pane workbench | Modify | Memo register: trace list (left of content), read-only trace reader (memo), annotation form (human-voice fields, segmented verdict, taxonomy multiselect). |
| Comparison surfaces | Modify | Instrument register: KPI tiles (mono numerals), themed transition-matrix `dash_table`, flipped-trace lists. Reuses console KPI/table vocabulary. |
| Overview console | **No change** | Already designed (`wb-*`). Only the sidebar-collapse behavior interacts with it. |
| Theme toggle (global) | Modify | Keep in top toolbar; must now recolor `uw-*` surfaces too (they read the same tokens), not just the console. |

## Key Interactions

- **Sidebar navigation.** Click a sidebar item → route changes, active item gets the indigo rail/active
  treatment. The Evaluation group shows its three children (Overview/Traces/Comparison) nested.
- **Sidebar auto-collapse on `/eval`.** Entering Overview, the sidebar animates to an **icon-only strip**
  (labels hidden) so the console's step-rail leads the left edge; leaving `/eval` restores it. Hover or a
  pin control temporarily expands it. Width transitions via a single token; no layout jump in content.
- **Top toolbar is contextual.** Controls swap by route: eval pages show corpus selector · Run eval ·
  last-run; the prototype shows nothing but the title; the theme toggle is always pinned right. Run-eval
  remains the existing background job (button disables + streams status), now styled to chrome.
- **Register hand-off.** Moving between a memo page and an instrument page, the **frame** (sidebar +
  toolbar) is identical; only the content **surface** changes temperature (paper→canvas). The transition
  should feel like turning from the written opinion to the readings, not like changing apps.
- **Theme toggle** flips `<html data-theme>`; every `uw-*` and `wb-*` surface recolors because both read
  the same custom properties. Both registers have a dark variant.

## Responsive Behavior

Desktop-first, single-user local tool. Optimized for **1280–1440**; usable down to **~1024** (sidebar may
collapse to icons earlier; the prototype's two memo columns may stack; instrument tables stay
horizontally scrollable). **No mobile/tablet layout** — out of scope, consistent with the console. Below
~1024 the grid degrades gracefully rather than reflowing to a phone layout.

## Accessibility Requirements

- **Color is never the only signal** *(inherited)*: heatmap/verdict cells print value + n; pass/fail pair
  color with text. Diverging scale is colorblind-safe teal→amber→red, never red→green.
- **Contrast**: body text/numerals ≥ 4.5:1; large/heading and UI affordances ≥ 3:1, in BOTH registers and
  BOTH themes. The warm memo paper must keep body text ≥ 4.5:1 (verify `--voice-human-text` on
  `--voice-human-bg`).
- **Keyboard**: sidebar items, toolbar controls, segmented toggles, tier dropdowns, form fields, and
  Run-eval all reachable/operable with a visible focus ring using the **indigo** chrome accent (never the
  data red/green).
- **Register distinction is not color-dependent**: document vs instrument differ in type, density, and
  layout as well as surface temperature, so the distinction survives grayscale.
- **Sidebar collapse** must not trap focus or hide nav from assistive tech — collapsed items keep
  accessible names (icon + `aria-label`).

## Out of Scope

- **Any backend / functionality / data change.** Pure visual-and-CSS pass; Dash callbacks, `core/`
  logic, routes, and persisted data are untouched. (The eval/judge "ruler" stays frozen.)
- **Restyling the Overview console.** Its `wb-*` design is done; we only add the sidebar-collapse behavior
  around it.
- **The Spec-2 experiment tracker** (leaderboard table, splits/repetitions, v1-vs-v2 charts). Comparison
  is styled at its current v1 scope only; the reusable KPI/table vocabulary will carry forward.
- **Mobile/tablet layouts, multi-user/auth, deployment/hosting.**
- **A token rewrite.** Phase 4 (tokens) consolidates/extends the EXISTING `workbench.css` tokens; it does
  not introduce a competing system.
