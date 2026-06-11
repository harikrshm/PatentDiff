# Design Review: Traces — Reviewer Output + Review Tab

Reviewed against: `.design/traces-review/DESIGN_BRIEF.md`
Philosophy: Analyst's workbench (memo annotator + instrument Review readout)
Date: 2026-06-12

## Screenshots Captured

| Screenshot | View | Description |
| --- | --- | --- |
| `screenshots/t1-reader-verdict.png` | Traces reader | "Mapped X/N" + per-element verdict chips + opinion |
| `screenshots/t1-reader.png` | Traces reader | `status=error` trace → "No tool output" note |
| `screenshots/t2-review.png` | Review @1280 light | Coverage headline + bar + what's-left |
| `screenshots/review-review-dark.png` | Review @1280 dark | Same, dark register |

## Summary

Both asks land cleanly. The trace reader now leads with PatentDiff's output — a
"Mapped X of N" headline, a per-element Mapped Y/N chip row (mapped tinted via the
FAIL valence), then the overall opinion — so the reviewer reads the decision
before coding it; `error` traces show a calm note instead of silently hiding the
verdict (the original complaint). The new **Review** tab answers "how many are
reviewed?" at a glance (33 of 93 · 35% · the reviewed/annotated/untouched split +
what's left). 212 tests pass.

## Must Fix

_None._

## Should Fix

_None._ Both views verified in light + dark; the verdict pairs Y/N text with tint
(grayscale-safe), the progress bar pairs % with fill, and the Review nav item
carries the active rail.

## Could Improve

1. **Clickable "what's left" chips** — a run-id chip in the Review tab could
   deep-link into the annotator for that trace. Deferred (out of scope; would
   need a query param the Traces page reads).
2. **Verdict chip could also surface the element `verdict` field** (not just
   `novelty`/Mapped) for reviewers who want the bottom-line per element. Kept to
   "Mapped" per the chosen compact design.

## What Works Well

- **Decision-first reader.** The tool's verdict + opinion sit above the claims, so
  the reviewer judges the output, not a blank. Matches the brief's principle.
- **Honest error state.** No more "just the claims" — `error` traces say why
  (`No tool output — status: error`).
- **Coverage at a glance.** The Review tab is a single instrument readout: big
  mono "33 of 93", indigo progress bar, the three-way split, and the unreviewed
  run-ids — no spreadsheet to parse (the deselected table/frequency/verdict
  pieces were correctly left out).
- **One lineage, two registers.** The annotator stays warm memo; Review is cool
  instrument; both recolor with the theme toggle. The new nav item ("Review", ✓)
  slots into the Evaluation group with the correct active state.
