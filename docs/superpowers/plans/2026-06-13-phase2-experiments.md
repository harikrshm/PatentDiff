# Phase 2 Experiments Implementation Plan

> **For agentic workers:** This plan is executed **INLINE with the user** (superpowers:executing-plans), NOT via background subagents — every step ends at a human approval gate that only the user can clear. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Run three rigorously-controlled experiments to drive down PatentDiff's eval failure rate, one change at a time, with the ruler frozen and the whole suite re-run each time.

**Architecture:** A small pure **gate helper** (`core/experiment_gate.py`, TDD) computes the token guardrail and the quantitative success gate consistently. The three experiments then orchestrate the existing harness scripts (`regenerate_traces.py`, `run_*_eval.py`, `run_*_vs_human.py`, `compute_eval_delta.py`, `seed_experiments.py`) through the invariant protocol, stopping at an approval gate after every step.

**Tech Stack:** Python 3.13, pytest, the existing `core/llm.py` product prompt + `traces/` harness. Groq API (live runs need `GROQ_API_KEY`).

**Spec:** `docs/superpowers/specs/2026-06-13-phase2-experiments-design.md`

---

## ⛔ GOVERNING RULE — per-step human approval

**After EVERY step below, STOP. Show the user the step's output (diff, run summary, FAIL rates, transition matrix, gate verdict). Do NOT start the next step until the user explicitly approves.** This applies to all three experiments. The prompt/lever edit (first step of each experiment) is a *discussion*: propose the change, show the exact diff, refine with the user, get approval — then proceed. Never chain steps. Never run a live regeneration (cost) without approval.

Two invariants enforced throughout:
- **The ruler does not move.** `core/phosita_eval.py` and `core/citation_eval.py` are never edited. (Verify with `git diff` — they must be byte-identical across all experiment commits.)
- **One change per experiment, whole suite every time.**

---

## File Structure

- **Create** `core/experiment_gate.py` — pure helpers: `system_prompt_within_budget()` (token guardrail) and `evaluate_gate(...)` → `GateResult` (the quantitative gate). Core-only, no app imports.
- **Create** `tests/test_experiment_gate.py` — unit tests for both.
- **Create** `scripts/check_experiment_gate.py` — thin CLI that loads a baseline + experiment trace set, computes overall/segment/cell FAIL for both evals (via `core.workbench_data.load_merged`), and prints the gate verdict using `evaluate_gate`.
- **Modify (Exp 1 & 2)** `core/llm.py:build_system_prompt()` — the only lever; one isolated edit per experiment.
- **Modify (Exp 3, conditional)** `core/llm.py:build_user_prompt()` + `core/truncation.py` — long-claim pre-processing.
- **Produced per experiment:** `traces/traces.<exp>.jsonl`, `traces/phosita_eval_full.<exp>.jsonl`, `traces/citation_text_eval_full.<exp>.jsonl`, `traces/*_vs_human.<exp>.md`, and an `experiments.jsonl` row.

Experiment suffixes: `exp1-verbatim`, `exp2-reasoning`, `exp3-longctx`.

---

## Stage 0 — Gate helper (code, TDD)

### Task 0.1: Token guardrail + success gate

**Files:**
- Create: `core/experiment_gate.py`
- Test: `tests/test_experiment_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_experiment_gate.py
from core.experiment_gate import evaluate_gate, system_prompt_within_budget


def _gate(**kw):
    base = dict(target_eval="citation", before=54.0, after=50.0,
                segment_before=58.0, segment_after=55.0,
                other_before=46.0, other_after=46.0,
                cell_deltas_pp={"Method/Short": -5.0, "System/Long": 3.0},
                ruler_ok=True)
    base.update(kw)
    return evaluate_gate(**base)


def test_gate_passes_on_overall_target_improvement():
    assert _gate().passed                       # citation -4pp, nothing else regresses


def test_gate_passes_on_segment_threshold_when_overall_small():
    # overall only -2pp (< 3pp bar) but the targeted segment drops 10pp -> still passes
    r = _gate(after=52.0, segment_after=48.0)
    assert r.passed


def test_gate_fails_when_target_unmoved():
    r = _gate(after=53.0, segment_after=57.0)   # -1pp overall, -1pp segment
    assert not r.passed
    assert any("target" in reason.lower() for reason in r.reasons)


def test_gate_fails_when_other_eval_regresses():
    r = _gate(other_after=49.0)                  # +3pp > +2pp guardrail
    assert not r.passed
    assert any("other eval" in reason.lower() for reason in r.reasons)


def test_gate_fails_on_cell_regression():
    r = _gate(cell_deltas_pp={"System/Short": 12.0})   # > 10pp worse
    assert not r.passed
    assert any("cell" in reason.lower() for reason in r.reasons)


def test_gate_fails_when_ruler_moved():
    r = _gate(ruler_ok=False)
    assert not r.passed
    assert any("ruler" in reason.lower() for reason in r.reasons)


def test_system_prompt_within_budget_current():
    ok, n = system_prompt_within_budget()
    assert ok and n <= 1800
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_experiment_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.experiment_gate'`.

- [ ] **Step 3: Implement**

```python
# core/experiment_gate.py
"""Pure gate logic for Phase 2 experiments: the token guardrail and the
quantitative success gate. No app/IO dependencies — callers pass in the measured
FAIL rates so this stays unit-testable. See
docs/superpowers/specs/2026-06-13-phase2-experiments-design.md."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateResult:
    passed: bool
    reasons: list[str]          # one line per criterion, with its verdict


def system_prompt_within_budget() -> tuple[bool, int]:
    """Token guardrail: the live product system prompt must fit its budget so
    spec-truncation math (which uses the fixed SYSTEM_PROMPT_TOKENS) stays valid."""
    from core.llm import build_system_prompt, _estimate_tokens, SYSTEM_PROMPT_TOKENS
    n = _estimate_tokens(build_system_prompt())
    return n <= SYSTEM_PROMPT_TOKENS, n


def evaluate_gate(*, target_eval: str,
                  before: float, after: float,
                  segment_before: float, segment_after: float,
                  other_before: float, other_after: float,
                  cell_deltas_pp: dict[str, float],
                  ruler_ok: bool) -> GateResult:
    """All inputs are FAIL rates in percent (0-100). A negative delta = improvement.

    PASS requires ALL of:
      - target eval FAIL drops >= 3pp overall OR >= 10pp in the targeted segment
      - the other eval does NOT regress more than +2pp
      - the ruler (judge-vs-human alignment) is unchanged (ruler_ok)
      - no dimension cell regresses by more than +10pp
    """
    reasons: list[str] = []
    overall_delta = after - before
    segment_delta = segment_after - segment_before
    other_delta = other_after - other_before
    worst_cell = max(cell_deltas_pp.values(), default=0.0)

    c1 = (overall_delta <= -3.0) or (segment_delta <= -10.0)
    c2 = other_delta <= 2.0
    c3 = bool(ruler_ok)
    c4 = worst_cell <= 10.0

    reasons.append(
        f"[{'PASS' if c1 else 'FAIL'}] target {target_eval}: "
        f"{overall_delta:+.1f}pp overall, {segment_delta:+.1f}pp segment "
        f"(need <=-3 overall or <=-10 segment)")
    reasons.append(
        f"[{'PASS' if c2 else 'FAIL'}] other eval: {other_delta:+.1f}pp "
        f"(need <=+2)")
    reasons.append(
        f"[{'PASS' if c3 else 'FAIL'}] ruler vs human: "
        f"{'unchanged' if c3 else 'MOVED'}")
    reasons.append(
        f"[{'PASS' if c4 else 'FAIL'}] worst dimension cell: {worst_cell:+.1f}pp "
        f"(need <=+10)")
    return GateResult(passed=c1 and c2 and c3 and c4, reasons=reasons)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_experiment_gate.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add core/experiment_gate.py tests/test_experiment_gate.py
git commit -m "feat(phase2): experiment gate helper (token guardrail + success gate)"
```

### Task 0.2: Gate CLI

**Files:**
- Create: `scripts/check_experiment_gate.py`

- [ ] **Step 1: Implement the CLI**

```python
# scripts/check_experiment_gate.py
"""Print the Phase 2 success-gate verdict for an experiment vs a baseline.

Both trace sets are discovered by suffix (core.workbench_data.list_trace_sets),
so they must already have their suffixed eval files written. Computes overall +
targeted-segment FAIL for both evals and the per-cell heatmap deltas, then calls
core.experiment_gate.evaluate_gate. Ruler stability is passed in via --ruler-ok
(read off the *_vs_human report by the operator).

Usage:
  python scripts/check_experiment_gate.py --baseline live --after exp1-verbatim \
      --target citation --segment-claim-type Method --segment-claim-length Short --ruler-ok
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.experiment_gate import evaluate_gate
from core.workbench_data import list_trace_sets, load_merged

TRACES = REPO_ROOT / "traces"
ANN = TRACES / "traces_annotations.jsonl"


def _frame(set_name):
    s = {x.name: x for x in list_trace_sets(TRACES)}[set_name]
    return load_merged(s, ANN)


def _fail(df, vcol, ct=None, cl=None):
    sub = df[df[vcol].isin(["PASS", "FAIL"])]
    if ct:
        sub = sub[sub["claim_type"] == ct]
    if cl:
        sub = sub[sub["claim_length"] == cl]
    n = len(sub)
    return (100.0 * (sub[vcol] == "FAIL").sum() / n) if n else 0.0


def _cell_deltas(b, a, vcol):
    out = {}
    for ct in ("Method", "System"):
        for cl in ("Short", "Long"):
            out[f"{ct}/{cl}"] = _fail(a, vcol, ct, cl) - _fail(b, vcol, ct, cl)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True)
    p.add_argument("--after", required=True)
    p.add_argument("--target", required=True, choices=["phosita", "citation"])
    p.add_argument("--segment-claim-type", default=None)
    p.add_argument("--segment-claim-length", default=None)
    p.add_argument("--ruler-ok", action="store_true")
    a = p.parse_args()

    b, af = _frame(a.baseline), _frame(a.after)
    tcol = f"{a.target}_verdict"
    ocol = "phosita_verdict" if a.target == "citation" else "citation_verdict"
    ct, cl = a.segment_claim_type, a.segment_claim_length

    res = evaluate_gate(
        target_eval=a.target,
        before=_fail(b, tcol), after=_fail(af, tcol),
        segment_before=_fail(b, tcol, ct, cl), segment_after=_fail(af, tcol, ct, cl),
        other_before=_fail(b, ocol), other_after=_fail(af, ocol),
        cell_deltas_pp=_cell_deltas(b, af, tcol),
        ruler_ok=a.ruler_ok)

    print(f"GATE: {'PASS ✅' if res.passed else 'FAIL ❌'}")
    for r in res.reasons:
        print("  " + r)
    return 0 if res.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-check it runs (against the existing baseline/live sets)**

Run: `python scripts/check_experiment_gate.py --baseline baseline --after live --target citation --segment-claim-type Method --segment-claim-length Short --ruler-ok`
Expected: prints a `GATE:` verdict with 4 criterion lines (no crash). This is a wiring smoke test, not a real experiment.

- [ ] **Step 3: Commit**

```bash
git add scripts/check_experiment_gate.py
git commit -m "feat(phase2): gate CLI (overall/segment/cell deltas -> evaluate_gate)"
```

---

## Stage 1 — Experiment 1: verbatim `corresponding_text` discipline (Prompt)

Suffix: `exp1-verbatim`. Baseline: `live`. Target: **Citation**, segment **Method · Short**.

- [ ] **Step 1 — Propose & make the prompt edit (DISCUSS → ⛔ APPROVAL).**
  In `core/llm.py:build_system_prompt()`, make ONLY this change. In the JSON-schema
  description of `corresponding_text` (the long line ending `or mark as not disclosed if not
  disclosed`), replace the trailing clause so it reads:
  `"corresponding_text": "EXACT verbatim text quoted from the target patent's independent_claim or specification — no paraphrase, no narration, no parentheticals; use the empty string \"\" if no exact span discloses the element",`
  And in the standalone rule block (the paragraph beginning `For every element, \`corresponding_text\` MUST be`), append one sentence: `Copy the shortest exact span that discloses the element.`
  Show the user the exact `git diff core/llm.py` and the confirmation that the rulers are untouched (`git diff --stat` shows only `core/llm.py`). **STOP for approval.**

- [ ] **Step 2 — Token guardrail (⛔ APPROVAL).**
  Run: `python -c "from core.experiment_gate import system_prompt_within_budget; print(system_prompt_within_budget())"`
  Expected: `(True, <n>)` with `n <= 1800` (Exp 1 is a net removal, so `n` should be ≤ the ~987 baseline). Show the user. **STOP.**

- [ ] **Step 3 — Regenerate traces (LIVE RUN, cost; ⛔ APPROVAL before running).**
  Confirm `GROQ_API_KEY` is set. Run:
  `python scripts/regenerate_traces.py --out traces/traces.exp1-verbatim.jsonl`
  Show the user the processed/ok/parse_error/api_error counts and the `truncation_warnings`
  frequency (must not rise vs baseline). **STOP.**

- [ ] **Step 4 — Run BOTH evals (⛔ APPROVAL).**
  ```bash
  python scripts/run_phosita_eval.py  --traces traces/traces.exp1-verbatim.jsonl --out traces/phosita_eval_full.exp1-verbatim.jsonl
  python scripts/run_citation_eval.py --traces traces/traces.exp1-verbatim.jsonl --out traces/citation_text_eval_full.exp1-verbatim.jsonl
  ```
  Show the user both overall FAIL rates. **STOP.**

- [ ] **Step 5 — Ruler sanity (⛔ APPROVAL).**
  ```bash
  python scripts/run_phosita_vs_human.py --eval traces/phosita_eval_full.exp1-verbatim.jsonl --report traces/phosita_vs_human.exp1-verbatim.md
  python scripts/run_eval_vs_human.py
  ```
  Show the user the judge-vs-human alignment vs the baseline report — it must be unchanged
  (the ruler didn't move, so this is a sanity check on the golden set). **STOP.**

- [ ] **Step 6 — Transition matrices (⛔ APPROVAL).**
  ```bash
  python scripts/compute_eval_delta.py --before traces/citation_text_eval_full.jsonl --after traces/citation_text_eval_full.exp1-verbatim.jsonl
  python scripts/compute_eval_delta.py --before traces/phosita_eval_full.jsonl     --after traces/phosita_eval_full.exp1-verbatim.jsonl
  ```
  Show the user both matrices (FAIL→PASS vs PASS→FAIL flips). **STOP.**

- [ ] **Step 7 — Gate verdict (⛔ APPROVAL — adopt or revert).**
  Read the ruler result from Step 5; pass `--ruler-ok` only if unchanged. Run:
  `python scripts/check_experiment_gate.py --baseline live --after exp1-verbatim --target citation --segment-claim-type Method --segment-claim-length Short [--ruler-ok]`
  Show the user the GATE verdict + the four criterion lines. **STOP — the user decides adopt or revert.**

- [ ] **Step 8 — Record the result (on approval).**
  If **adopted**: keep the `core/llm.py` edit; add an `experiments.jsonl` row for `exp1-verbatim`
  (via editing `scripts/seed_experiments.py`'s spec or appending a manifest line) so it shows in the
  Comparison tab; fill the tracking-table row in the spec ("eval score after change" + "success-gate
  comment"). If **reverted**: `git checkout core/llm.py`; record the negative result in the table.
  Then commit:
  ```bash
  git add core/llm.py traces/experiments.jsonl traces/*.exp1-verbatim.* docs/superpowers/specs/2026-06-13-phase2-experiments-design.md
  git commit -m "exp(phase2): exp1-verbatim — <adopted|reverted>, citation <delta>pp"
  ```
  **STOP. Await approval before starting Experiment 2.**

---

## Stage 2 — Experiment 2: mandatory per-element obviousness reasoning (Prompt)

Suffix: `exp2-reasoning`. Baseline: the **adopted state after Exp 1** (`exp1-verbatim` if adopted, else `live`). Target: **PHOSITA**, segment **System · Short**. Same 8-step structure, same ⛔ approval gate after every step.

- [ ] **Step 1 — Propose & make the prompt edit (DISCUSS → ⛔ APPROVAL).**
  In `core/llm.py:build_system_prompt()`, ONLY change the reasoning instruction. Replace the
  bullet `Include a comment with step-by-step reasoning through novelty and inventive step before the verdict.`
  with: `The \`comment\` MUST give explicit reasoning a person having ordinary skill in the art (PHOSITA) would use — first novelty, then, for EVERY element including structural/apparatus elements (e.g. a processor, memory, module), whether the prior art renders this element obvious and why — and only then the verdict. Never leave the comment empty.`
  Show the exact `git diff core/llm.py`; confirm rulers untouched. **STOP for approval.**

- [ ] **Step 2 — Token guardrail (⛔ APPROVAL).**
  `python -c "from core.experiment_gate import system_prompt_within_budget; print(system_prompt_within_budget())"`
  Expected `(True, <n>)`, `n <= 1800` (the reworded addition is < 100 words, within the headroom). If `n > 1800`, STOP and trim wording with the user. Show the user. **STOP.**

- [ ] **Step 3 — Regenerate traces (LIVE RUN; ⛔ APPROVAL before running).**
  `python scripts/regenerate_traces.py --out traces/traces.exp2-reasoning.jsonl`
  Show counts + `truncation_warnings`. **STOP.**

- [ ] **Step 4 — Run BOTH evals (⛔ APPROVAL).**
  ```bash
  python scripts/run_phosita_eval.py  --traces traces/traces.exp2-reasoning.jsonl --out traces/phosita_eval_full.exp2-reasoning.jsonl
  python scripts/run_citation_eval.py --traces traces/traces.exp2-reasoning.jsonl --out traces/citation_text_eval_full.exp2-reasoning.jsonl
  ```
  Show both overall FAIL rates. **STOP.**

- [ ] **Step 5 — Ruler sanity (⛔ APPROVAL).**
  ```bash
  python scripts/run_phosita_vs_human.py --eval traces/phosita_eval_full.exp2-reasoning.jsonl --report traces/phosita_vs_human.exp2-reasoning.md
  python scripts/run_eval_vs_human.py
  ```
  Show alignment vs baseline. **STOP.**

- [ ] **Step 6 — Transition matrices (⛔ APPROVAL).**
  Compare against the Exp-1-adopted baseline files (use `phosita_eval_full.exp1-verbatim.jsonl` /
  `citation_text_eval_full.exp1-verbatim.jsonl` if Exp 1 was adopted, else the `live` files):
  ```bash
  python scripts/compute_eval_delta.py --before <baseline phosita>  --after traces/phosita_eval_full.exp2-reasoning.jsonl
  python scripts/compute_eval_delta.py --before <baseline citation> --after traces/citation_text_eval_full.exp2-reasoning.jsonl
  ```
  Show both matrices. **STOP.**

- [ ] **Step 7 — Gate verdict (⛔ APPROVAL — adopt or revert).**
  `python scripts/check_experiment_gate.py --baseline <exp1-verbatim|live> --after exp2-reasoning --target phosita --segment-claim-type System --segment-claim-length Short [--ruler-ok]`
  Show the GATE verdict + criteria. **STOP — user decides.**

- [ ] **Step 8 — Record the result (on approval).** As in Exp 1 Step 8 (manifest row, fill the
  tracking table, commit `exp(phase2): exp2-reasoning — <adopted|reverted>, phosita <delta>pp`).
  **STOP. Await approval before deciding on Experiment 3.**

---

## Stage 3 — Experiment 3 (CONDITIONAL): focused prior-art context for long claims (Model/pre-processing)

**Run ONLY if** after Exp 1 the Citation · Long segment still fails its gate. Confirm this with the
user first (⛔ APPROVAL to start Stage 3 at all). Suffix: `exp3-longctx`. Target: **Citation · Long**.

- [ ] **Step 1 — Propose & make the pre-processing edit (DISCUSS → ⛔ APPROVAL).**
  In `core/llm.py:build_user_prompt()` / `core/truncation.py`: for **long claims only** (gate on the
  source claim length / current `truncation` path), replace blunt `smart_truncate_spec` with
  per-element candidate-span selection — for each source claim element, pick the top-k most
  lexically-similar specification sentences and assemble those as the spec context, so the exact
  verbatim span is present. Keep short claims on the existing path (no change). Show the exact diff;
  confirm rulers and `build_system_prompt` untouched. **STOP.**

- [ ] **Step 2 — Unit-test the new pre-processing in isolation (TDD; ⛔ APPROVAL).**
  Add `tests/test_longctx_preprocessing.py` asserting: (a) short claims are byte-identical to the old
  path; (b) for a long synthetic claim+spec, the selected context contains the sentence holding a
  known verbatim span. Run `python -m pytest tests/test_longctx_preprocessing.py -v` → PASS. Show the
  user. **STOP.**

- [ ] **Steps 3–8 — Same protocol as Exp 1/2** (regenerate → both evals → ruler sanity → transition
  matrices → gate → record), each ending at a ⛔ approval gate. Gate command:
  `python scripts/check_experiment_gate.py --baseline <current adopted> --after exp3-longctx --target citation --segment-claim-type Method --segment-claim-length Long [--ruler-ok]`
  Also confirm latency/tokens stay within budget (from the regenerated trace `llm_response`). Commit
  `exp(phase2): exp3-longctx — <adopted|reverted>, citation·long <delta>pp`.

---

## Self-Review Notes

- **Spec coverage:** ruler-frozen + one-change + whole-suite + suffixed/baseline (governing rule + each step) ✓; token guardrail (Stage 0 + Step 2 of each prompt exp) ✓; quantitative gate (Stage 0 `evaluate_gate` + Step 7) ✓; prompt-first order with Exp 3 conditional (Stages 1→2→3) ✓; tracking table fill-in (Step 8) ✓; Comparison-tab surfacing via `experiments.jsonl` (Step 8) ✓; per-step approval rule (governing rule + every step) ✓.
- **Placeholder scan:** the only "TBD"s live in the spec's results table, filled at Step 8 by design — not plan placeholders. All code steps show complete code.
- **Type consistency:** `evaluate_gate(...)`/`GateResult`/`system_prompt_within_budget()` signatures match between Task 0.1, the CLI (0.2), and the gate steps. Suffix names (`exp1-verbatim`, `exp2-reasoning`, `exp3-longctx`) and file paths are consistent across stages.
- **Note:** live regeneration + eval runs hit the Groq API (~90 traces each, cost + minutes); these are exactly the steps gated by user approval.
