# Design Brief: Traces — Reviewer Output + Review-Progress Tab

> Child of `.design/unified-workbench/DESIGN_BRIEF.md`. Extends the Traces
> annotation tool (`/eval/traces`, memo register) and adds a **Review** sub-route
> for coverage. Reuses the established `uw-*`/`wb-*` token system. Backend
> (traces, annotations, taxonomy) is unchanged.

## Problem

A reviewer opens a trace to code its failure mode — but the tool only shows the
two patent claims and (sometimes) a paragraph of opinion. It never shows **what
PatentDiff actually decided**: the per-element mapping verdicts. Without the
verdict in front of them, the reviewer can't judge whether the tool was right,
so the annotation is guesswork. And there's no way to see the **big picture** —
how much of the corpus has been reviewed, how much is left. The old tool had a
view toggle for exactly this; the unified port dropped it.

## Solution

Two changes. First, the trace reader shows **the tool's output up front** — a
compact per-element verdict (Mapped Y/N) with a headline "Mapped X of N", then
the overall opinion — so the reviewer reads the decision, then codes it. Second,
a new **Review** tab (sidebar sub-route) answers one question at a glance: *how
much is reviewed?* — a progress headline (X of N reviewed) and what's left.

## Experience Principles

1. **Decision first, then judgment** — the reviewer sees the tool's verdict +
   opinion before the annotation form; you can't code what you can't see.
2. **Coverage at a glance** — the Review tab answers "how far along are we?" in
   one number and a bar, not a spreadsheet to parse.
3. **One lineage, two registers** — the annotator stays the warm memo document;
   the Review tab is the cool instrument readout. Same tokens, same chrome.

## Aesthetic Direction

- **Philosophy**: Analyst's workbench — memo register for the annotator (reading
  + writing on the document), instrument register for the Review readout.
- **Tone**: composed, precise. The verdict block reads as a measured finding, the
  Review tab as a progress gauge.
- **Reference points**: the existing Prototype report (element verdicts), the
  Dashboard's KPI/progress readouts (mono numerals, progress bar).
- **Anti-references**: a dense spreadsheet dump for the Review tab; burying the
  verdict below the claims; emoji verdicts.

## Existing Patterns

- **Typography**: Inter (body), Source Serif (memo prose), IBM Plex Mono (IDs,
  verdicts, numerals).
- **Colors**: memo paper `--memo-*` + `--voice-*`; instrument canvas
  `--color-bg-*`; indigo chrome; reserved `--data-fail-*` for verdict valence.
- **Components (reuse)**: the Traces 3-pane (`uw-traces*`), `wb-segmented`,
  `wb-dropdown`, the prototype's verdict tinting law, the Dashboard's progress
  bar (`uw-kt__bar`/`__fill`) and `wb-kpi`-style readouts.
- **Data**: `core.trace_loader` (trace.parsed_output.element_mappings has
  element_number, corresponding_text, novelty="Y"/"N", verdict; overall_opinion),
  `core.annotation` (reviewed flag per run_id).

## Component Inventory

| Component | Status | Notes |
| --- | --- | --- |
| Trace reader verdict block | New | Compact per-element "Mapped Y/N" list + "Mapped X/N" headline, in the reader above/with the opinion. Mapped = novelty Y (found in prior art). Verdict tint via `--data-fail-*`. |
| Trace reader opinion | Modify | Always show when present; for `status=error` / no parsed_output, show a calm "no tool output (error)" note instead of silence. |
| "Your reading" label | **Remove** | Delete the `uw-field__voice` span in the annotation form. |
| Review tab (`/eval/review`) | New | New Dash page: review-progress headline (X of N reviewed, % bar), reviewed/unreviewed split, and a compact list of what's left to review. Instrument register. |
| Sidebar nav item "Review" | New | Add to `EVAL_GROUP` in `app_unified/components.py` (Dashboard · Traces · **Review** · Comparison). |

## Key Interactions

- **Select a trace** → reader shows the verdict block (Mapped X/N + per-element
  Y/N) and the overall opinion first, then the claims; the annotation form
  pre-fills any saved annotation. (No eval runs.)
- **Error trace** → verdict block shows "no tool output — status: error"; claims
  still render so the reviewer has context.
- **Open Review tab** → progress headline + bar render from annotations vs total
  traces; the unreviewed list shows run-ids still to do; clicking one (stretch)
  could deep-link to the annotator — out of scope unless trivial.

## Responsive Behavior

Desktop-first (1280–1440). The annotator keeps its 3-pane→stack at ~1024 (already
built). The Review tab is a single readout column, full-width, no special
breakpoints.

## Accessibility Requirements

- Verdict pairs Y/N text with tint (never color-only); contrast ≥ 4.5:1 both
  themes. The progress bar pairs the % number with the fill. Indigo focus rings.
- The Review nav item keeps its label + active state; keyboard reachable.

## Out of Scope

- No backend/data changes (traces, annotations, taxonomy, eval ruler frozen).
- **No** all-annotations table, failure-mode frequency chart, or verdict summary
  in the Review tab (deselected — review progress only).
- No element-level annotation (the tool codes one verdict + modes per trace).
- No restyle of Dashboard / Prototype / Comparison.
