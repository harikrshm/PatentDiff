# Build Tasks: Traces — Reviewer Output + Review Tab

Generated from: .design/traces-review/DESIGN_BRIEF.md
Date: 2026-06-12

> Plotly **Dash**. Verify by booting `python -m app_unified.app` and viewing
> `/eval/traces` and `/eval/review`. Backend frozen.

## Core UI
- [ ] **T1 · Trace reader shows the tool's output + remove "Your reading"**:
  In `app_unified/pages/eval_traces.py` `_render_trace_detail`, add a **verdict
  block** above the opinion — a "Mapped X of N" headline + a compact per-element
  list (`Elem N — Mapped Y/N`, tinted via `--data-fail-*`; Mapped = `novelty=="Y"`,
  i.e. found in prior art). Always render the **overall opinion** when present;
  when `parsed_output` is absent (e.g. `status=error`), show a calm "no tool
  output — status: <status>" note instead of silence. Delete the `"Your reading"`
  `uw-field__voice` span. New `uw-traces__verdict*` CSS. _Done = selecting a trace
  shows Mapped X/N + per-element verdicts + opinion before the claims; error
  traces show the note; no "Your reading" label._

- [ ] **T2 · Review tab (`/eval/review`) + nav item**: New Dash page
  `app_unified/pages/eval_review.py` (instrument register): a progress headline
  (**X of N reviewed**, % bar reusing `uw-kt__bar`/`__fill`), the reviewed /
  unreviewed split (mono counts), and a compact list of unreviewed run-ids
  ("what's left"). Add **Review** to `EVAL_GROUP` in `app_unified/components.py`
  (Dashboard · Traces · Review · Comparison) with a glyph. Pure read of
  `core.annotation` (reviewed flag) vs `core.trace_loader` total. New
  `uw-review*` CSS. _Done = `/eval/review` shows reviewed/total + % bar + the
  unreviewed list; the nav item is active on that route._

## Review
- [ ] **Design review**: `/design-review` against the brief — `/eval/traces`
  (verdict block + opinion, error trace, no "Your reading") and `/eval/review`
  (progress) at 1280/1440 + dark.
