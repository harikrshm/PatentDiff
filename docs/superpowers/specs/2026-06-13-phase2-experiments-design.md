# Phase 2 Experiments — Targeted Failure-Rate Reduction — Design

**Date:** 2026-06-13
**Status:** Approved (brainstorm), pending implementation plan
**Depends on:** Phase 2 Step 1 (prioritization) + Step 2 (layer localization) — recorded in the
Notion doc "LLM Evals for PatentDiff" and summarized below.

## Problem

The live system fails ~46.7% (PHOSITA) / ~54.2% (Citation) on the last eval run. Step 1 ranked the
worst (eval × claim segment) cells by frequency × user impact; Step 2 localized each to an
architecture layer. We now need a **rigorous, one-change-at-a-time experiment loop** to drive the
failure rate down without confounding the measurement.

## Method (non-negotiable rules)

1. **The ruler does not move.** The judge prompts (`core/phosita_eval.py`, `core/citation_eval.py`)
   are NOT edited during experiments. Changing the product and the measurement instrument in the
   same step confounds the result.
2. **One change per experiment.** Never bundle. Edit exactly one lever, re-run, measure, decide.
3. **Run the whole suite every time.** Every experiment re-runs both evals (a Citation fix is always
   checked against PHOSITA and vice-versa), the judge-vs-human alignment (ruler sanity), and the
   dimension heatmap (cross-effect per cell).
4. **Suffixed outputs + frozen baseline.** Each experiment writes to suffixed files so
   `scripts/compute_eval_delta.py` prints a before/after transition matrix against a frozen baseline.

## Levers (the two layers)

- **Prompt layer (cheapest):** `core/llm.py:build_system_prompt()` — the product system prompt.
- **Model / pre-processing layer (more expensive):** `core/llm.py:build_user_prompt()` +
  `core/truncation.py:smart_truncate_spec` — the inputs the model sees.

Token budget (relevant to the prompt experiments): `GROQ_TOKEN_LIMIT=6500`,
`SYSTEM_PROMPT_TOKENS=1800` (budget constant used for spec truncation). The current system prompt is
**~987 tokens**, leaving **~813 tokens (~325 words) of slack** under the 1800 budget. Spec truncation
is computed from the fixed 1800 constant, so small prompt additions do NOT reduce spec budget or risk
the Groq limit — provided actual system-prompt tokens stay ≤ 1800.

## The experiment protocol (invariant, every experiment)

1. Edit **exactly one lever**.
2. **Token guardrail (prompt experiments):** assert actual `build_system_prompt()` tokens ≤ 1800;
   note the value.
3. `python scripts/regenerate_traces.py --out traces/traces.<exp>.jsonl` — re-runs all inputs,
   preserves `run_id`. Record the `truncation_warnings` count.
4. Run **both** evals on that trace file → `phosita_eval_full.<exp>.jsonl`,
   `citation_text_eval_full.<exp>.jsonl`. Ruler prompts untouched.
5. **Ruler sanity:** `scripts/run_phosita_vs_human.py` / `scripts/run_eval_vs_human.py` on the golden
   set — judge-vs-human alignment must be unchanged.
6. `scripts/compute_eval_delta.py --before <prev adopted> --after <exp>` for each eval → transition
   matrix.
7. Recompute the dimension heatmap per cell — no cell regresses > 10pp.
8. Apply the **success gate** → adopt (keep the lever change) or revert.
9. Register the run in `traces/experiments.jsonl` so it surfaces in the Comparison tab.

**Baseline:** the current live eval files (current prompt) are the frozen reference. Each
experiment's delta is measured against the **immediately preceding adopted state** (its before/after),
while the original pre-Phase-2 live stays the fixed anchor for cumulative progress in the Comparison
tab. Temperature is 0.2, so the gate thresholds (below) sit above run-to-run noise.

## Success gate (quantitative — all must hold)

- Target eval's FAIL drops: **overall −3pp OR targeted segment −10pp**.
- The other eval does **not** regress more than **+2pp**.
- **Ruler stable:** judge-vs-human alignment unchanged (within ±1 disagreement on the golden set).
- **No dimension cell regresses > 10pp** (heatmap, catches whack-a-mole).

## Experiment order (locked: prompt-first)

**Exp 1 → Exp 2** committed and cumulative (Exp 2 builds on Exp 1 if adopted). **Exp 3** conditional —
only if Exp 1 leaves Citation·Long failing; scoped to long claims only (never all), to limit blast
radius and preserve attribution.

### Experiment 1 — Prompt: verbatim `corresponding_text` discipline (layer: Prompt)

- **Change** (`build_system_prompt`): delete the contradictory "or mark as not disclosed if not
  disclosed" from the output-schema description; state the rule once — `corresponding_text` is an
  exact verbatim substring of the target's `independent_claim`/`specification`, else `""`. Add: "no
  paraphrase, no narration, no parentheticals; if no exact span discloses the element, use ``""``;
  copy the shortest exact span." Net token **removal**.
- **Target:** Citation FAIL (rank 1 Method·Short; partial rank 4).
- **Hypothesis:** the "not disclosed" escape hatch produces narration that the frozen citation ruler
  scores as `citation_text` FAIL; removing it forces verbatim-or-empty.
- **Gate:** Citation −3pp overall (or Method·Short −10pp); PHOSITA ≤ +2pp; ruler stable; no cell −>10pp.

### Experiment 2 — Prompt: mandatory per-element obviousness reasoning (layer: Prompt)

- **Change** (`build_system_prompt`): require that **every** element's `comment` contain explicit
  PHOSITA obviousness reasoning — what the prior art teaches, whether reaching this element would be
  obvious, and why — **before** the verdict, calling out **structural/apparatus (system) elements**
  specifically (not just method steps). Comment never empty. Reworded-not-appended, < 100 words,
  within the ≤ 1800-token guardrail.
- **Target:** PHOSITA FAIL (rank 2 System·Short, rank 3 Method·Short).
- **Hypothesis:** `absent_phosita_reasoning` fires because reasoning is optional/under-specified for
  structural elements; mandating it fills the gap, largest on System·Short (72%).
- **Gate:** PHOSITA −3pp overall (or System·Short −10pp); Citation ≤ +2pp; ruler stable; no cell −>10pp.

### Experiment 3 — Model/pre-processing: focused prior-art context for long claims (CONDITIONAL)

- **Trigger:** run only if, after Exp 1, Citation·Long is still failing the gate.
- **Change** (`build_user_prompt`/`truncation`): replace blunt `smart_truncate_spec` with per-element
  candidate-span selection (lexical/embedding match of spec sentences to each source element), **for
  long claims only**, so the exact verbatim span is in-context.
- **Target:** Citation·Long FAIL (rank 4).
- **Hypothesis:** truncation removes the quotable span; focused context restores it.
- **Gate:** Citation·Long −10pp; PHOSITA & Citation·Short ≤ +2pp; latency/tokens within budget; ruler
  stable.

## The tracking table (the experiment log)

Filled in as experiments run; the last two columns come from the suite re-run. Each row links its
`experiments.jsonl` entry so the same numbers surface in the Comparison tab.

| Exp | Layer | What is changed | Target | Eval score after change | Success-gate comment |
|---|---|---|---|---|---|
| 1 | Prompt | verbatim `corresponding_text` discipline (net token removal) | Citation FAIL ↓ (Method·Short) | TBD — Citation% / PHOSITA% vs baseline | TBD — gate verdict |
| 2 | Prompt | mandatory per-element PHOSITA obviousness reasoning (≤1800-token guardrail) | PHOSITA FAIL ↓ (System·Short, Method·Short) | TBD | TBD — gate verdict |
| 3 (cond.) | Model / pre-processing | per-element candidate-span context, long claims only | Citation·Long FAIL ↓ | TBD | TBD — gate verdict |

## Components & boundaries

- **No change to the rulers** (`phosita_eval.py`, `citation_eval.py`) — frozen by rule 1.
- **Exp 1 & 2:** edits confined to `core/llm.py:build_system_prompt()`.
- **Exp 3:** edits confined to `core/llm.py:build_user_prompt()` + `core/truncation.py`.
- **Harness reuse:** `regenerate_traces.py`, `run_phosita_eval.py`, `run_citation_eval.py`,
  `run_phosita_vs_human.py`, `run_eval_vs_human.py`, `compute_eval_delta.py`, `seed_experiments.py`
  (manifest registration) all already exist — the plan orchestrates them, it does not rebuild them.
- **A small helper** may be added to assert the token guardrail and to roll up the per-cell heatmap
  delta into the gate decision, so the gate is computed consistently rather than by eye.

## Testing / validation

- This is an experiment workflow, not a feature: most "validation" is the suite re-run + gate.
- Any new helper code (token-guardrail check, gate roll-up) gets unit tests, following the repo's
  existing test style.
- The frozen-ruler invariant is verifiable: diff `phosita_eval.py`/`citation_eval.py` across the
  experiment commits — they must be byte-identical.

## Out of scope

- Touching the eval/judge prompts (frozen by rule 1).
- Pre-processing for ALL claims (Exp 3 is long-only and conditional).
- Model swaps or temperature changes (would confound; separate investigation).
- Any further Comparison/Dashboard UI work (already shipped).
