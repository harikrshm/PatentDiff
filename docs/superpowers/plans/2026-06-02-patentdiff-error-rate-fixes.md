# PatentDiff Prototype Error-Rate Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce PatentDiff's two measured failure modes (Absent PHOSITA Reasoning, Citation Text) by changing the **PatentDiff product's system prompt/architecture one change at a time**, re-running the full eval suite after each change, and keeping only changes that improve the target metric without regressing the other.

**Architecture:** This repo is the **measurement harness** (the eval suite is the fixed ruler — it is *not* modified during these experiments; the v1→v3 judge calibration is already done). Each "task" below is **one controlled experiment**: snapshot baseline → make exactly one prompt change in the PatentDiff product → regenerate traces → run the *full* suite → compute before/after deltas → keep or revert based on a pre-stated success gate. Experiments are ordered cheapest-layer-first (Hamel): Layer 1 prompt instruction → Layer 1/2 instruction + schema → Layer 3 capability (conditional).

**Tech Stack:** Python eval scripts (`scripts/run_*_eval.py`, `scripts/run_*_vs_human.py`, `scripts/compute_eval_delta.py`), Streamlit dashboard, JSONL trace/eval files under `traces/`.

---

## The scientific discipline (read before starting)

- **One variable per experiment.** Never combine two prompt changes in one run. If you change two things and the number moves, you cannot attribute the cause.
- **The ruler does not move.** Do not touch `core/phosita_eval.py`, `core/citation_eval.py`, or any judge prompt during these experiments. Changing the measurement instrument and the product in the same step confounds the result.
- **Always run the *full* suite, not just the targeted eval.** A fix to Citation must be checked against PHOSITA (and vice-versa) to catch cross-regressions. The dashboard heatmap is the cross-effect check by dimension cell.
- **State the success gate before running.** Each experiment names (a) the metric that must improve and (b) the guardrail metrics that must not regress. Decide keep/revert from the printed numbers, not from intuition.
- **Write to suffixed output files.** Never overwrite the baseline eval files. Each experiment writes `*.<expN>.jsonl`, so `compute_eval_delta.py` can diff before vs after.

### The "full eval suite" — the exact command block (referenced as **[SUITE]** below)

For an experiment writing to suffix `<S>` (e.g. `exp1`) against a regenerated `traces/traces.<S>.jsonl`:

```bash
# 1. Citation eval -> suffixed output
python scripts/run_citation_eval.py --traces traces/traces.<S>.jsonl --out traces/citation_text_eval_full.<S>.jsonl
# 2. PHOSITA eval -> suffixed output
python scripts/run_phosita_eval.py  --traces traces/traces.<S>.jsonl --out traces/phosita_eval_full.<S>.jsonl
# 3. Citation delta vs baseline
python scripts/compute_eval_delta.py --before traces/citation_text_eval_full.baseline.jsonl --after traces/citation_text_eval_full.<S>.jsonl
# 4. PHOSITA delta vs baseline
python scripts/compute_eval_delta.py --before traces/phosita_eval_full.baseline.jsonl       --after traces/phosita_eval_full.<S>.jsonl
# 5. Judge-vs-human alignment unchanged sanity (ruler still calibrated)
python scripts/run_phosita_vs_human.py --eval traces/phosita_eval_full.<S>.jsonl --report traces/phosita_vs_human_report.<S>.md
python scripts/run_eval_vs_human.py
```

> **Note on script flags:** `run_citation_eval.py` and `run_phosita_eval.py` already accept `--traces`/`--out`. Verify with `python scripts/run_citation_eval.py --help` before first use; if a flag differs, fix the command, not the discipline.

---

## Task 0: Freeze the baseline

**Files:**
- Create: `traces/citation_text_eval_full.baseline.jsonl`
- Create: `traces/phosita_eval_full.baseline.jsonl`
- Create: `docs/eval-experiments/BASELINE.md`

- [ ] **Step 1: Snapshot the current eval outputs as the immutable baseline**

```bash
cp traces/citation_text_eval_full.jsonl traces/citation_text_eval_full.baseline.jsonl
# PHOSITA baseline must be v3-only (the current ruler); filter it:
python -c "import json; rows=[l for l in open('traces/phosita_eval_full.jsonl',encoding='utf-8') if l.strip() and (json.loads(l).get('config') or {}).get('prompt_version')=='v3']; open('traces/phosita_eval_full.baseline.jsonl','w',encoding='utf-8').writelines(rows)"
```

- [ ] **Step 2: Record the baseline numbers in writing**

Create `docs/eval-experiments/BASELINE.md` with the current figures (already measured on 2026-06-02):

```markdown
# Eval Baseline — 2026-06-02 (PatentDiff prompt: pre-fix)
- Citation Text FAIL: 39/71 = 55%
- PHOSITA (v3) FAIL : 39/87 = 45%
- PHOSITA judge-vs-human: TPR 77.8% / TNR 60.0% (ruler calibration — must stay ~constant)
- Worst PHOSITA cells: System·Long·Novel 67% (n=15), System·Short·Novel 83% (n=6)
- Citation: roughly uniform ~55% across all dimension cells
```

- [ ] **Step 3: Commit the frozen baseline**

```bash
git add traces/citation_text_eval_full.baseline.jsonl traces/phosita_eval_full.baseline.jsonl docs/eval-experiments/BASELINE.md
git commit -m "chore(evals): freeze pre-fix baseline for one-change-at-a-time experiments"
```

---

## Task 1 — Experiment 1 (Layer 1, cheapest): Verbatim-quote instruction → Citation Text

**Hypothesis:** Citation Text fails ~uniformly across all dimension cells (~55%). Uniform failure ⇒ the PatentDiff prompt simply never instructs verbatim quoting. A single instruction-level change should cut the citation FAIL rate.

**The ONE change:** In the **PatentDiff product** system prompt, add an explicit instruction to the element-mapping step: *"For each mapped element, quote the corresponding prior-art text **verbatim** (exact substring of the source). Do not paraphrase or summarize."* Change nothing else.

**Success gate:**
- IMPROVE: Citation FAIL rate drops by ≥10 pp vs baseline (55% → ≤45%).
- GUARDRAIL: PHOSITA FAIL rate does not rise by more than 3 pp; PHOSITA judge-vs-human TPR/TNR within ±5 pp of baseline.

**Files:**
- Modify (external): PatentDiff product system prompt — verbatim-quote instruction only.
- Create: `traces/traces.exp1.jsonl` (regenerated traces)
- Create: `traces/citation_text_eval_full.exp1.jsonl`, `traces/phosita_eval_full.exp1.jsonl`
- Create: `docs/eval-experiments/EXP1-verbatim-quote.md`

- [ ] **Step 1: Make exactly one prompt change in the PatentDiff product** (in the PatentDiff repo), then regenerate traces for the same corpus and copy them here as `traces/traces.exp1.jsonl`. Keep the same source/target patent inputs as the baseline corpus so run_ids/cells are comparable.

- [ ] **Step 2: Run the full eval suite with suffix `exp1`** — execute the **[SUITE]** block above with `<S>=exp1`.

- [ ] **Step 3: Read the two transition matrices.** Confirm Citation shows net FAIL→PASS movement and PHOSITA shows no net PASS→FAIL drift. Note any cell that regressed.

- [ ] **Step 4: Visual cross-check by dimension** — `streamlit run scripts/run_dashboard.py` after temporarily pointing the dashboard paths at the `exp1` files (or copy exp1 over the live files in a scratch branch). Confirm the citation heatmap cooled uniformly and the PHOSITA heatmap is unchanged.

- [ ] **Step 5: Record the verdict (keep or revert).** Write `docs/eval-experiments/EXP1-verbatim-quote.md`:

```markdown
# EXP1 — Verbatim-quote instruction (Layer 1)
Change: added verbatim-quote instruction to PatentDiff element-mapping prompt.
Citation FAIL: 55% -> <X>%  (delta <±Y> pp)
PHOSITA FAIL : 45% -> <Z>%  (guardrail; must be ~unchanged)
PHOSITA TPR/TNR: <..>/<..>  (ruler sanity)
Decision: KEEP / REVERT — <one sentence tied to the success gate>
```

- [ ] **Step 6: Commit the experiment artifacts** (regardless of keep/revert — the negative result is data).

```bash
git add traces/*.exp1.jsonl docs/eval-experiments/EXP1-verbatim-quote.md
git commit -m "exp(evals): EXP1 verbatim-quote instruction — citation <result>"
```

- [ ] **Step 7: GATE.** Only if EXP1 was KEEP, promote it to the new baseline before starting Task 2 (so Task 2 measures from a clean single-variable state):

```bash
cp traces/traces.exp1.jsonl traces/traces.jsonl
cp traces/citation_text_eval_full.exp1.jsonl traces/citation_text_eval_full.baseline.jsonl
cp traces/phosita_eval_full.exp1.jsonl traces/phosita_eval_full.baseline.jsonl
git commit -am "chore(evals): promote EXP1 to baseline"
```

---

## Task 2 — Experiment 2 (Layer 1/2): PSA-reasoning instruction + derived-opinion schema → Absent PHOSITA

**Hypothesis:** PHOSITA fails on a clean gradient (Anticipation 17% → Implicit 50% → Novel 68%). The uniform baseline component ("asserts non-obvious without reasoning") is a prompt instruction/structure gap: the PatentDiff prompt does not require *why-a-PSA* reasoning and lets `overall_opinion` be stated independently of per-element obviousness. A Layer 1/2 change should lift the easy/Implicit cells.

**The ONE change (this is still a single conceptual variable — the obviousness-reasoning structure):** In the **PatentDiff product** prompt: (1) instruct it to state, per novel element, *why a person of ordinary skill would or would not find it obvious*; (2) restructure the output schema so `overall_opinion` is **derived from the per-element obviousness reasoning**, not written free-form. Do **not** also change the citation instruction (already locked from Task 1).

**Success gate:**
- IMPROVE: PHOSITA FAIL rate drops by ≥10 pp overall; the Implicit-cell FAIL rate drops meaningfully (the cells most likely to be prompt-fixable).
- GUARDRAIL: Citation FAIL rate does not rise by >3 pp; PHOSITA judge-vs-human TPR/TNR within ±5 pp (the ruler must still be measuring the same thing).
- DIAGNOSTIC: note whether **System × Novel** cells move. If they stay clustered high after this fix, that is the Layer-3 signal feeding Task 3.

**Files:**
- Modify (external): PatentDiff product prompt — PSA-reasoning instruction + derived-opinion schema only.
- Create: `traces/traces.exp2.jsonl`, `traces/citation_text_eval_full.exp2.jsonl`, `traces/phosita_eval_full.exp2.jsonl`
- Create: `docs/eval-experiments/EXP2-psa-reasoning.md`

- [ ] **Step 1: Make exactly one conceptual change in the PatentDiff product prompt** (PSA-reasoning + derived opinion), regenerate traces over the same corpus, copy here as `traces/traces.exp2.jsonl`.

- [ ] **Step 2: Run the full eval suite with suffix `exp2`** — **[SUITE]** block with `<S>=exp2`.

- [ ] **Step 3: Read both transition matrices.** Confirm PHOSITA net FAIL→PASS movement; confirm Citation did not regress.

- [ ] **Step 4: Dimensional diagnosis.** In the dashboard PHOSITA heatmap (pointed at `exp2` files), record the FAIL rate for each `claim_type × relationship` cell. Specifically capture System·Long·Novel and System·Short·Novel — these decide whether Task 3 is needed.

- [ ] **Step 5: Record the verdict.** Write `docs/eval-experiments/EXP2-psa-reasoning.md`:

```markdown
# EXP2 — PSA-reasoning instruction + derived-opinion schema (Layer 1/2)
PHOSITA FAIL overall: 45% -> <X>%  (delta <±Y> pp)
  - Anticipation cells: <..>%   Implicit cells: <..>%   Novel cells: <..>%
  - System·Long·Novel: <..>%   System·Short·Novel: <..>%   <-- Layer-3 trigger check
Citation FAIL (guardrail): <..>%
PHOSITA TPR/TNR (ruler sanity): <..>/<..>
Decision: KEEP / REVERT
Layer-3 needed? YES if System × Novel still > ~50% after this fix.
```

- [ ] **Step 6: Commit the experiment artifacts.**

```bash
git add traces/*.exp2.jsonl docs/eval-experiments/EXP2-psa-reasoning.md
git commit -m "exp(evals): EXP2 PSA-reasoning + derived opinion — phosita <result>"
```

- [ ] **Step 7: GATE.** If KEEP, promote `exp2` to baseline (same three `cp` commands as Task 1 Step 7 with `exp2`), then evaluate the Layer-3 trigger before Task 3.

---

## Task 3 — Experiment 3 (Layer 3, CONDITIONAL): capability fix for System × Novel

**Run this task ONLY if EXP2 left System × Novel clustered high (> ~50% FAIL).** A failure that survives Layer 1/2 prompt fixes *and* stays clustered in the hardest-reasoning cells is the signature of a model-capability ceiling — prompt engineering has plateaued there. This is the highest Frequency × Impact × Exposure cell, so it is worth the expensive fix; but only after the cheap layers are exhausted and measured.

**The ONE change — pick exactly one sub-option and test it in isolation:**
- **3a (scope reduction, cheapest Layer-3):** add a low-confidence flag in PatentDiff output for `claim_type=System AND relationship=Novel`. This does not improve the reasoning; it de-risks the worst outputs. Measure: does it correctly cover the failing cell without over-flagging clean cells?
- **3b (stronger model routing):** route System × Novel claims to a more capable generation model; keep the prompt from EXP2. Measure: PHOSITA FAIL in that cell vs baseline.
- **3c (fine-tune):** fine-tune on PSA-reasoning exemplars for System × Novel. Highest cost/lead time — only if 3a/3b are insufficient.

**Success gate (for 3b/3c):** System × Novel PHOSITA FAIL drops by ≥15 pp with no regression in any other cell and Citation unchanged. For 3a: flag precision/recall against the known failing cell, no behavior change elsewhere.

**Files:**
- Modify (external): PatentDiff product — exactly one of 3a/3b/3c.
- Create: `traces/traces.exp3.jsonl`, `traces/citation_text_eval_full.exp3.jsonl`, `traces/phosita_eval_full.exp3.jsonl`
- Create: `docs/eval-experiments/EXP3-capability.md`

- [ ] **Step 1: Implement exactly one sub-option** in the PatentDiff product, regenerate traces, copy as `traces/traces.exp3.jsonl`.

- [ ] **Step 2: Run the full eval suite with suffix `exp3`** — **[SUITE]** block with `<S>=exp3`.

- [ ] **Step 3: Cell-level check.** Confirm System × Novel improved and every other cell held. Record per-cell deltas.

- [ ] **Step 4: Record the verdict** in `docs/eval-experiments/EXP3-capability.md`:

```markdown
# EXP3 — Layer-3 capability fix (sub-option 3<a|b|c>)
System·Long·Novel FAIL: <before>% -> <after>%
System·Short·Novel FAIL: <before>% -> <after>%
All other cells: <held / regressions noted>
Citation (guardrail): <..>%   PHOSITA TPR/TNR: <..>/<..>
Decision: KEEP / REVERT / escalate to next sub-option
```

- [ ] **Step 5: Commit.**

```bash
git add traces/*.exp3.jsonl docs/eval-experiments/EXP3-capability.md
git commit -m "exp(evals): EXP3 Layer-3 capability fix for System x Novel — <result>"
```

---

## Task 4: Roll up the experiment log

**Files:**
- Create: `docs/eval-experiments/SUMMARY.md`

- [ ] **Step 1: Write a one-screen summary** chaining baseline → EXP1 → EXP2 → (EXP3) with the FAIL-rate at each step and the keep/revert decision, so the error-rate reduction is a single auditable trail (this is the artifact that proves the fixes were *measured*, not asserted).

- [ ] **Step 2: Commit.**

```bash
git add docs/eval-experiments/SUMMARY.md
git commit -m "docs(evals): experiment summary — baseline to final error rates"
```

---

## Self-review notes

- **Ruler integrity:** No task modifies `core/*_eval.py` or any judge prompt. Confirmed.
- **One variable per task:** Task 1 = verbatim instruction only; Task 2 = PSA-reasoning structure only; Task 3 = exactly one capability sub-option. Confirmed.
- **Full suite every time:** Each experiment runs both evals + both human-alignment checks + dashboard cross-check. Confirmed.
- **Cheapest-first ordering with a measured gate** between layers; Layer 3 is conditional on Layer 1/2 being exhausted and System × Novel persisting. Confirmed.
- **External dependency flagged:** trace regeneration happens in the PatentDiff product repo, not here; this repo only measures. Confirmed.
