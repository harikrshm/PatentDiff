# Unified Workbench — Tool Unification (Spec 1 of 2)

> **Status:** Design approved 2026-06-10. This is **Spec 1** of a two-part effort.
> Spec 2 (the full experiment tracker) is scoped but not designed here.

## Problem

PatentDiff's tooling is scattered across four separate apps a user must launch and
context-switch between:

| Tool | Today | Stack |
|---|---|---|
| **PatentDiff prototype** | `app.py` (112 lines) | Streamlit |
| **Annotation tool** | `app_annotation.py` (530 lines) | Streamlit |
| **Error-rate dashboard** (old) | `scripts/run_dashboard.py` | Streamlit |
| **Eval workbench / analyst console** (new) | `app_workbench/` (~1360 lines) | Plotly **Dash** |

There is no single place to go from "run the prototype" to "evaluate the outputs" to
"compare experiments." The work lives in different processes, different stacks, and (the
console) on a different branch. The team wants **one interface** for everything.

## Solution

A single **Plotly Dash** application that houses every tool under one navigation tree.
No React, no API layer — Dash callbacks call the existing Python `core/` modules directly,
exactly as the Streamlit apps do today. The unification is a **migration**, not a redesign:
the prototype and annotation tool are ported as-is in behavior; the console folds in
nearly unchanged; visual/UX redesign of each interface is explicitly **out of scope** for
this spec (a later, separate pass).

### Navigation

```
PatentDiff  ┃  Evaluation                          ← top-level nav
─────────────────────────────────────────────────
  /                  PatentDiff prototype   (port of app.py)
  /eval              Overview — analyst console (fold in app_workbench)
  /eval/traces       Traces — annotation tool (port of app_annotation.py)
  /eval/comparison   Comparison — before/after eval delta (NEW, minimal v1)
```

The three eval views render as a **secondary nav strip** (Overview · Traces · Comparison)
that switches routes — visually a tab bar, structurally separate Dash Pages. This keeps
each view URL-addressable (matching the console IA's URL strategy), scopes each view's
callbacks to its own page module, and lets each interface be redesigned later in isolation
without touching the others.

### Scope split (the larger picture)

This is **Spec 1 of 2**. The Comparison tab the team ultimately wants is a full
**experiment tracker / leaderboard** — rows = experiments, columns = experiment · splits ·
repetitions · eval-1 · eval-2, plus v1-vs-v2 charts. That requires a net-new data model
("what is an experiment / split / repetition?") that does not exist in the codebase today
(trace sets are currently just suffix-named `.jsonl` files). That is **Spec 2**, designed
and built separately on top of this shell.

**Spec 1 (this doc)** ships the unification + migrations, and a **minimal Comparison v1** =
the existing `scripts/compute_eval_delta.py` before/after view, so the tab is functional
rather than empty.

## Architecture

### Stack & boundary

- **One Dash app**, `Dash(use_pages=True)`.
- Callbacks import and call `core/` directly. **No API layer, no React.**
- `DiskcacheManager` retained for the background **Run eval** job (already in the console).
- The console's `assets/` (`workbench.css` design tokens + `workbench.js` scroll-spy) become
  **app-global** assets. The dark/light theme toggle moves into the shared top header so it
  applies across all views.

### File layout

```
app_unified/
  __init__.py
  app.py                 # use_pages=True · top nav · secondary eval nav · theme toggle · page_container · DiskcacheManager
  components.py          # shared chrome: top nav, eval nav strip, header, reused tile/badge helpers
  pages/
    __init__.py
    prototype.py         # path="/"                ← port of app.py
    eval_overview.py     # path="/eval"            ← console layout folded in
    eval_traces.py       # path="/eval/traces"     ← port of app_annotation.py
    eval_comparison.py   # path="/eval/comparison" ← NEW before/after delta v1
  assets/
    workbench.css        # relocated from app_workbench/assets/
    workbench.js         # relocated from app_workbench/assets/

core/   (reused as-is; the console's modules relocate here from the eval-workbench branch)
  workbench_data.py · diagnostics.py · priority.py · workbench_state.py · eval_runner.py
  eval_delta.py          # NEW — extracted from scripts/compute_eval_delta.py so page + CLI share it
```

The existing `app_workbench/components.py`, `heatmap.py`, `state.py`, `theme.py`,
`constants.py`, `data.py`, `callbacks.py` relocate under `app_unified/` (or are imported by
`eval_overview.py`); their concepts are preserved, not rewritten.

### Build units (each independently runnable; TDD throughout)

1. **Shell** — `app.py` boots: top nav (PatentDiff | Evaluation), secondary eval strip
   (Overview · Traces · Comparison), app-global theme toggle, `page_container`. Each page is
   a routing stub. Acceptance: all four routes resolve; nav highlights the active section.

2. **Overview** — relocate the console code onto the working branch; mount its layout at
   `/eval`. Convert its `@app.callback`s to global `@callback` (Dash Pages registry); the
   theme toggle/control-bar adapt to the shared header. **Behavior unchanged.** Its existing
   tests (`test_workbench_data`, `test_diagnostics`, `test_priority`, `test_workbench_state`,
   `test_eval_runner`) come along and stay green.

3. **Prototype** — `/` reproduces `app.py`'s two-column claim form → Analyze → report,
   calling the same `core.llm.build_system_prompt / build_user_prompt / call_groq`,
   `core.report.parse_llm_response`, and `tracing.logger / tracing.store` functions, appending
   traces to `traces/traces.jsonl` identically. **Parity test** against current behavior.

4. **Traces** — `/eval/traces` reproduces the annotation tool: trace selector + read-only
   trace display (metadata, dimensions, both patents, output) + failure-mode coder (phase
   detection, taxonomy, parse + save), persisting to `traces/traces_annotations.jsonl` via
   `core.annotation`. **Parity test** for the load/save round-trip.

5. **Comparison v1** — `/eval/comparison`: before-set + after-set + eval (PHOSITA / Citation)
   selectors → PASS-rate delta KPIs, verdict transition matrix (PASS/FAIL/NO_CITATIONS/MISSING),
   and a flipped-run_id list for spot-checking. Logic extracted to `core/eval_delta.py`
   (unit-tested, no UI), reusing `core.workbench_data` trace-set discovery for the selectors.
   `scripts/compute_eval_delta.py` is refactored to call `core/eval_delta.py` so CLI and page
   never drift.

6. **Cleanup** (final, only after parity confirmed): delete `scripts/run_dashboard.py`
   (Overview supersedes its Summary/Heatmap/Implications tabs), then delete `app.py` and
   `app_annotation.py`. Update `requirements.txt` (drop Streamlit if nothing else needs it)
   and any run docs.

### Data flow & persistence (unchanged)

- Trace sets: suffix-named `traces/*.jsonl` (`traces.jsonl` live, `traces.exp2.jsonl`,
  `traces.post-prompt-v2.*`, …) discovered by `core.workbench_data`.
- Eval outputs: `traces/phosita_eval_full*.jsonl`, `traces/citation_text_eval_full*.jsonl`.
- Annotations: `traces/traces_annotations.jsonl` via `core.annotation`.
- Console PM state: `traces/workbench_state/*.json` via `core.workbench_state`.
- **The eval/judge "ruler" is frozen** — `core/phosita_eval.py`, `core/citation_eval.py`,
  and judge prompts are not modified.

### Error handling

Each page guards missing/empty data sources the way the originals do (the console's
`_iter_jsonl` / graceful-empty pattern, the annotation tool's load-failure `st.error`
equivalent → a Dash error banner). A broken trace-set selection degrades to an empty-state
message, never a stack trace in the UI.

## Branch strategy

1. Merge the **`eval-workbench`** branch → **`main`** (it is complete and tested), landing the
   console as committed history.
2. Cut a fresh **`unify-workbench`** branch off `main` for all Spec 1 work.

This gives a clean baseline where the console code is already present, rather than copied
across branches. (Git operations confirmed before execution.)

## Testing strategy

- **TDD per build unit.** Each port gets a parity test asserting the Dash view produces the
  same persisted artifacts / derived numbers as the Streamlit original for representative input.
- **Reuse** the console's existing `core/` tests unchanged.
- **New** `tests/test_eval_delta.py` covering the transition matrix, PASS-rate delta, and
  run-id filtering (mirrors `compute_eval_delta` behavior).
- A page boots without error on empty/missing data (smoke test per route).

## Out of scope (Spec 1)

- **The full experiment tracker** (leaderboard of experiments × splits × repetitions × evals,
  v1-vs-v2 charts) — that is **Spec 2**.
- **Any visual/UX redesign** of the prototype, Traces, or Comparison interfaces — design pass
  is later and separate.
- **A shared global "active trace set"** across eval views — deferred (each view keeps its own
  selector); a natural Spec 2 unification.
- **Any change to eval/judge logic** — frozen ruler.
- **Auth / multi-user / deployment / hosting** — single-user local tool, unchanged.

## Success criteria

1. `python -m app_unified.app` serves all four routes; nav switches between them.
2. The prototype produces an identical trace record to `app.py` for the same input.
3. The Traces view loads existing annotations and round-trips a save identically to
   `app_annotation.py`.
4. The Overview view renders the analyst console with all existing behavior intact and tests
   green.
5. The Comparison view reproduces `compute_eval_delta`'s matrix + delta for a chosen
   before/after pair.
6. `scripts/run_dashboard.py`, `app.py`, and `app_annotation.py` are removed; no remaining
   import references them.
