# Design Review: Traces — Reviewer Output + In-Tab Coverage Navigator

Reviewed against: `.design/traces-review/DESIGN_BRIEF.md`
Philosophy: Analyst's workbench (memo annotator)
Date: 2026-06-12

## Screenshots Captured

| Screenshot | View | Description |
| --- | --- | --- |
| `screenshots/t1-reader-verdict.png` | Traces reader | "Mapped X/N" + per-element verdict chips + opinion |
| `screenshots/t1-reader.png` | Traces reader | `status=error` trace → "No tool output" note |
| `screenshots/r2-nav.png` | Traces nav | Coverage header + filter + ✓/○ status list (selection highlighted) |

## Summary

Both asks land, and the coverage view now lives **inside** Traces (the first cut's
separate `/eval/review` sidebar tab was removed per feedback). The trace reader
leads with PatentDiff's output — "Mapped X of N" + per-element Mapped Y/N chips,
then the overall opinion — with a calm note for `error` traces. The Traces left
pane is now a real navigator: a coverage header (X of N reviewed + bar), an
All / To review / Reviewed filter, and a scrollable ✓/○ status list that replaces
the dropdown — overall picture *and* selection in one place. 211 tests pass.

## Must Fix

_None._

## Should Fix

_None._ Verified: filter narrows correctly (All 93 → To review 60, none reviewed);
clicking a row loads the verdict reader; selection is highlighted; coverage +
status dots refresh after a save (ann-version signal). Verdict pairs text with
tint; ✓/○ pairs shape with color (grayscale-safe).

## Could Improve

1. **Sort/group the list** (e.g., unreviewed first, or by status) so the "what's
   left" is even faster to work through. Currently corpus order.
2. **Surface the element `verdict` field** alongside Mapped in the reader, for
   reviewers who want the bottom-line per element. Kept to Mapped per the chosen
   compact design.

## What Works Well

- **Decision-first reader.** Tool verdict + opinion above the claims; `error`
  traces explain themselves instead of showing only claims.
- **Coverage + selection in one pane.** No separate tab — the navigator carries
  the overall picture (33 of 93 · 35% · bar) and the filterable ✓/○ list, exactly
  where the reviewer already is.
- **Live feedback.** Saving an annotation updates the coverage and the row's
  status dot without a reload (the `ann-version` store drives `render_nav`).
- **In-register.** The navigator stays warm memo (selected row uses the
  human-voice surface); the reused `uw-kt` progress bar ties it to the rest of
  the system. Both themes covered.
