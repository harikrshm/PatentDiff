# Experiment Agent — Design Spec

**Date:** 2026-06-20
**Status:** Approved for planning
**Topic:** An "AI employee" that takes over the PM's experiment-design analysis: it reads the live evaluation dashboard, proposes a ranked sequence of experiments, runs them one at a time on a subset under human approval, and surfaces results in the existing Comparison tracker.

---

## 1. Motivation

PatentDiff already lets a PM *own a number and move it*: the Dashboard shows FAIL rates by dimension, KPI targets, and a frequency × impact × exposure priority table; the Comparison tab tracks before/after experiments through a regression gate (`core/experiment_gate.evaluate_gate`).

What a PM still does **by hand** today: stare at the priority table, decide which failure mode × segment to attack next, hand-author the prompt change, run the regeneration + eval, and read the gate. The Experiment Agent automates that analysis-and-execution busywork while keeping the PM as the decision-maker (KEEP/REVERT). It is the literal embodiment of "delegating the busywork to an AI employee" — the PM sets direction and judges results; the agent does the legwork.

This is a thin, additive feature built on existing core modules. It does **not** change the evaluation methodology, the gate, or the trace/eval data model.

---

## 2. Scope

### In scope
- A new workbench tab `/eval/agent` ("Experiment Agent").
- An **Analyze** action that produces a **ranked plan of ~3 experiments** grounded in real dashboard data.
- A **PM feedback loop**: a free-text box where the PM steers the plan; the agent revises before anything runs.
- **Staged execution** with a **per-experiment approval gate** (KEEP/REVERT), **cumulative** baselines (each kept change builds on the last).
- One runnable lever: an **appended system-prompt instruction block** (applied as data, never code edits).
- Results written to `traces/experiments.jsonl` so the **existing Comparison tab** displays them.
- A committed demo-safety cache so the feature degrades gracefully and can be rehearsed offline.

### Out of scope (YAGNI)
- Preprocessing/truncation or few-shot levers as *runnable* changes (the proposal text MAY mention them as advisory only).
- Fully autonomous multi-experiment loops with no human gate between stages.
- Code-editing or arbitrary-lever experiments.
- Full-corpus regeneration (runs are on a small subset for on-camera speed).
- Any change to the Comparison tab itself beyond consuming the manifest rows the agent appends.

---

## 3. Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|---|---|
| 1 | Autonomy | **Propose + one-click run on a subset** (not advisory-only, not fully autonomous) |
| 2 | Runnable lever | **Appended system-prompt instruction block**, applied as data |
| 3 | Placement | New tab `/eval/agent`, linked from the Dashboard priority table |
| 4 | Proposal shape | **Ranked sequence of ~3 experiments** + a PM feedback text box to revise |
| 5 | Execution | **Staged**, with PM **approval (KEEP/REVERT) between every experiment** |
| 6 | Sequencing baseline | **Cumulative** — a kept change is appended on top for the next stage; REVERT drops it |
| 7 | Results surface | The **existing Comparison tab** (append to `traces/experiments.jsonl`) |

---

## 4. Architecture

Pure, testable logic lives in `core/`; the Dash page is a thin delegator (matches the established page pattern: `dash.register_page` + module-level `layout` + pure functions the callbacks call).

### 4.1 `core/experiment_agent.py` — the brain

No Dash, no live IO except the single LLM call in `propose_plan`.

- **`gather_context(df, targets) -> AgentContext`** — *deterministic.* Assembles the targeting facts:
  - top priority cells via `core.priority.priority_table()` (failure_mode × claim_type × relationship, scored);
  - per-KPI gap = `current_fail − target_fail`, from `core.kpi_targets` + `core.experiments.metrics_for`;
  - 2–3 example failing `run_id`s per top mode/segment.
  The agent never invents targeting — these are real numbers passed into the prompt.
- **`propose_plan(context, pm_feedback: str | None = None) -> ExperimentPlan`** — builds the LLM prompt from `AgentContext` (+ optional PM feedback), calls `core.llm.call_groq`, parses JSON into Pydantic. Retries once on malformed JSON; raises a typed error caught by the page (which falls back to cache).

**Pydantic models:**
- `ProposedExperiment { order: int, target_eval: Literal["citation","phosita"], target_segment: str, prompt_block: str, predicted_delta_pp: float, rationale: str, cited_run_ids: list[str] }`
- `ExperimentPlan { experiments: list[ProposedExperiment] }`
- `AgentContext` — the deterministic targeting payload (priority rows, KPI gaps, example failing trace excerpts).

### 4.2 `core/experiment_agent_runner.py` — the staged executor

- **`select_subset(df, segment) -> list[str]`** — the targeted segment's `run_id`s plus a small guardrail sample from other segments, capped (default 8) for on-camera speed.
- **`run_stage(proposed, kept_block, subset_run_ids) -> StageResult`** —
  1. Compose the cumulative system-prompt block: `kept_block + "\n\n" + proposed.prompt_block`.
  2. Regenerate the subset traces with that block appended (via `build_system_prompt(extra_instructions=...)`).
  3. Re-score citation + PHOSITA on the regenerated subset.
  4. Compute before/after FAIL and per-cell deltas; call `core.experiment_gate.evaluate_gate()`.
  5. Return `StageResult { before, after, segment_before, segment_after, other_before, other_after, cell_deltas_pp, gate: GateResult, coverage: "ran X/Y" }`.
- **On KEEP** (PM action, invoked from the page): append an `Experiment` row to `traces/experiments.jsonl` so the Comparison tab renders the move; the returned `kept_block` for the next stage includes this block.
- **On REVERT**: drop `proposed.prompt_block`; the next stage's `kept_block` is unchanged.

### 4.3 Enabling refactor — `core/llm.build_system_prompt`

Add an optional parameter:

```python
def build_system_prompt(extra_instructions: str = "") -> str:
    base = "...existing constant..."
    return base if not extra_instructions else base + "\n\n" + extra_instructions
```

Default behavior is **byte-identical** to today, so every existing caller and test is unaffected. The regeneration path threads the cumulative block through this seam. This is the single mechanism that makes the lever runnable without code edits.

### 4.4 `app_unified/pages/eval_agent.py` — the page (thin)

- **Layout (top→bottom):** Analyze button → plan cards (one per `ProposedExperiment`: order, target KPI+segment, the prompt block, predicted Δ, rationale + cited traces) → PM feedback textbox + **Revise** button → **Approve plan & start** → staged run area (per-stage `StageResult` + **Approve/Reject** buttons) → link to the Comparison tab.
- The LLM call (`propose_plan`) and regeneration (`run_stage`) run as **diskcache background callbacks** (already used in the app) so the UI never blocks.
- **State** in `dcc.Store`s: the current `ExperimentPlan`, the current stage index, and the cumulative kept block.
- Callbacks delegate entirely to the two core modules; no business logic in the page (keeps it unit-testable per the project convention).

### 4.5 Data flow

```
dashboard frame ──▶ gather_context ──▶ propose_plan (LLM)
                                            │
                          ┌─────────────────┘
                          ▼
                 PM revise loop (feedback textbox ──▶ propose_plan)
                          │ approve
                          ▼
   for each stage:  run_stage (regen + rescore + evaluate_gate)
                          │
                          ▼
                 PM KEEP / REVERT  ──KEEP──▶ append to experiments.jsonl ──▶ Comparison tab
                          │
                          └─ next stage uses cumulative kept_block
```

---

## 5. Error handling & demo safety

- **Malformed LLM JSON** → retry once with a stricter "JSON only" reminder; if it still fails, show a clean "couldn't parse a plan" state with the raw output, not a stack trace.
- **`GROQ_API_KEY` missing / Groq error / rate-limit** → fall back to the cached last-good plan with a visible banner ("Showing cached plan — live API unavailable").
- **Per-trace regeneration failure** → skip the trace, continue, report real coverage ("ran 7/8"); `evaluate_gate` already consumes measured rates, so partial coverage just lowers n.
- **Tiny-n gate** → display n beside the verdict with a "low-confidence, n=6" note.
- **No actionable segment** (priority table already drops `Unknown`) → the agent says "no actionable segment" instead of proposing a hollow experiment.
- **Demo-safety cache:** a committed `traces/agent_demo_cache.json` holds one known-good plan + one known-good `StageResult`, used automatically when the live path is unavailable and forceable via a hidden `?demo=1` flag, so the Loom can be rehearsed/recorded offline. Live-first, cache-as-safety-net.

---

## 6. Test plan (TDD; all Groq calls stubbed — no live API in tests)

- `gather_context` — from a fixture dashboard frame + targets: returns the expected top cell, correct KPI gap, and right cited `run_id`s.
- `propose_plan` — monkeypatched `call_groq` returning canned JSON parses into a valid `ExperimentPlan`; the malformed-JSON retry path and the cached-fallback path are both exercised.
- Pydantic models — validation rejects bad `target_eval` / missing fields.
- `select_subset` — picks the targeted segment + guardrail sample, respects the cap.
- `build_system_prompt(extra_instructions=...)` — appends correctly; **default call is byte-identical to today** (guards every existing caller/test).
- `run_stage` — with stubbed `call_groq` over fixture traces: cumulative block composition, before/after FAIL math, manifest append on KEEP, block-drop on REVERT.
- Gate integration — `run_stage` feeds `evaluate_gate` and returns the expected PASS/FAIL.

All new tests mock the network; the suite stays green offline (current baseline: 237 passing).

---

## 7. Files touched

**New**
- `core/experiment_agent.py`
- `core/experiment_agent_runner.py`
- `app_unified/pages/eval_agent.py`
- `traces/agent_demo_cache.json`
- `tests/test_experiment_agent.py`, `tests/test_experiment_agent_runner.py`

**Modified**
- `core/llm.py` — add `extra_instructions` param to `build_system_prompt` (default-compatible).
- Dashboard priority table — add a "→ Ask the agent" link to `/eval/agent`.
- The regeneration path — thread the cumulative block through `build_system_prompt`.

---

## 8. Open risks

- **Subset run latency on camera.** ~8 traces × (model-under-test + 2 evaluators) Groq calls per stage. Mitigation: small cap + the demo cache for the recorded run.
- **Predicted Δ credibility.** The agent's `predicted_delta_pp` is a guess; the *measured* gate result is the truth. The UI must visually subordinate the prediction to the measured outcome so the agent never looks like it's grading its own homework.
