# PHOSITA Judge v2 — CoT Prompt + Async Runner

**Date:** 2026-05-30
**Supersedes:** [[2026-05-27-phosita-llm-judge-design]] (v1 prompt)
**Failure mode:** `absent_phosita_reasoning`

## Problem

v1 TPR = 33% (3/9). All 6 false negatives share the same pattern: the tool's
`overall_opinion` contains PSA vocabulary ("novel and non-obvious", "would not
be obvious to a person of ordinary skill") but no argument for *why* a PSA
would reach that conclusion. The v1 judge credits the presence of this
vocabulary as sufficient for a PASS.

Secondary problem: 5 false positives (human=PASS, judge=FAIL). The judge
applied a stricter standard than humans in cases where specific technical
mechanisms are completely absent from prior art — which humans accept as
implicit non-obviousness.

Tertiary problem: sequential Groq calls hit RPM rate limits → 8–15 min wall
time per full run.

## Goal

Improve TPR while not degrading TNR. Maintain qwen/qwen3-32b on Groq. Measure
success by re-running `scripts/run_phosita_vs_human.py` and comparing the
new confusion matrix against v1.

## Design decisions

1. **Judge input = `overall_opinion` only.** Element mappings are no longer
   sent. The failure mode is *absent reasoning in the overall opinion* — the
   judge does not need per-element context to assess that. This also cuts avg
   input tokens from ~1,181 to ~600 per trace.

2. **Chain-of-thought output before verdict.** The judge emits an
   `opinion_check` object before committing to a verdict. This forces an
   explicit intermediate step that distinguishes *conclusion vocabulary* from
   *reasoning*, breaking the v1 short-circuit.

3. **Four-rule rubric** (see system prompt below). The two critical additions:
   - Conclusion rule: PSA vocabulary is a legal conclusion, not reasoning.
   - Complete-absence rule: when named technical mechanisms are entirely absent
     from prior art (architecturally foreign, not just unmatched by label),
     that absence is itself an implicit PSA argument — no explicit PSA language
     required.

4. **Async 4-way concurrency.** Replace the sequential loop in the runner with
   `asyncio.gather` over batches of 4. Uses `AsyncGroq` (drop-in from the
   Groq SDK). Cuts wall time to ~2–4 min without exceeding Groq's RPM limit.

5. **`PROMPT_VERSION = "v2"`.** Existing v1 entries in
   `traces/phosita_eval_full.jsonl` are preserved. The runner only skips
   `(run_id, "v2")` pairs — v1 traces are not re-used.

6. **No downstream changes.** `scripts/run_phosita_vs_human.py`,
   `core/eval_vs_human.py`, and the report format are untouched. The
   `evaluate_trace` output contract (keys: `run_id`, `eval_name`, `verdict`,
   `comment`, `judge_raw`, `config`) is unchanged.

## Scope

**In scope:**
- `core/phosita_eval.py`: bump `PROMPT_VERSION`, new system prompt, updated
  `_build_judge_prompt` (opinion only), updated `_call_judge` (new schema).
- `scripts/run_phosita_eval.py`: async rewrite with `AsyncGroq` + 4-way
  `asyncio.gather`.
- `tests/test_phosita_eval.py`: update mocks and assertions for new schema;
  add two new tests for `has_psa_argument=false` → FAIL.

**Out of scope:**
- Model comparison / switching away from qwen3-32b.
- Changes to human annotations or the annotation schema.
- Per-element verdict or sub-scores.
- Source/target patent text in the judge input.

## System prompt (v2)

```
You are evaluating a patent obviousness analysis produced by an AI tool.
The tool writes an overall_opinion on whether a source patent is valid
given a target patent (prior art).

Your job: judge whether the overall_opinion contains genuine
person-of-ordinary-skill-in-the-art (PSA) obviousness reasoning.

Rules:

1. CONCLUSION TEST — PSA vocabulary is not reasoning.
   Phrases like "non-obvious", "novel and non-obvious", "would not be
   obvious to a person of ordinary skill" are legal conclusions.
   Their presence alone does NOT make a PASS. You must find an
   argument, not just a label.

2. WHAT COUNTS AS REASONING — the opinion must engage with WHY.
   Reasoning explains: what background knowledge or capability a PSA
   has, what prior-art components a PSA would naturally combine, or
   why the specific step or combination is non-trivial given what a
   PSA knows. A one-sentence explanation grounded in the technology
   is sufficient.

3. COMPLETE-ABSENCE IMPLICIT ARGUMENT.
   When the opinion documents that specific named technical mechanisms
   are entirely absent from prior art — not merely unmatched by label,
   but architecturally foreign — that absence is itself an implicit
   PSA argument (a PSA cannot combine what does not exist). In this
   case mark has_psa_argument=true even without explicit PSA language.

4. ALL-NOVEL SHORTCUT.
   If the opinion states that every claim element is novel (no prior
   art overlap at all), obviousness is vacuous. Mark verdict PASS.

Return ONLY valid JSON in this exact shape:
{
  "opinion_check": {
    "uses_psa_vocabulary": true or false,
    "has_psa_argument": true or false,
    "note": "one sentence explaining your classification"
  },
  "verdict": "PASS" or "FAIL",
  "comment": "1-3 sentences explaining the verdict. Quote specific
              phrases from the overall_opinion to justify."
}

verdict must be FAIL if has_psa_argument is false.
verdict must be PASS if has_psa_argument is true.
```

## User prompt (v2, per trace)

```
Overall opinion:
[overall_opinion text]
```

## Judge call parameters

Unchanged from v1: `temperature=0.2`, `max_tokens=1024`,
`response_format={"type": "json_object"}`.

## Updated `_call_judge` validation

After JSON parse, validate:
- `"verdict"` is `"PASS"` or `"FAIL"`.
- `"opinion_check"` is a dict with `"has_psa_argument"` (bool) and `"note"` (str).
- Internal consistency: if `has_psa_argument=false`, verdict must be `FAIL`
  (and vice versa). If inconsistent, log a warning and trust `verdict`.

## Async runner design

```python
import asyncio
from groq import AsyncGroq

CONCURRENCY = 4

async def _evaluate_batch(traces, client, cache):
    sem = asyncio.Semaphore(CONCURRENCY)
    async def _one(trace):
        async with sem:
            return await evaluate_trace_async(trace, client)
    return await asyncio.gather(*[_one(t) for t in traces], return_exceptions=True)
```

`evaluate_trace_async` mirrors `evaluate_trace` but uses `await
client.chat.completions.create(...)`. The sync `evaluate_trace` is kept for
test compatibility (called directly in unit tests with a mock client).

The runner writes results in one shot after all tasks complete (same
idempotency guarantee as v1).

## Token estimates (v2)

| | Per trace (avg) | 30-trace study | 91-trace full run |
|---|---|---|---|
| Input | ~600 tokens | ~18K | ~55K |
| Output | ~250 tokens | ~7.5K | ~23K |
| Cost (qwen3-32b) | ~$0.0001 | ~$0.004 | ~$0.013 |

Input cost drops ~50% vs v1 (element mappings removed).

## Tests to add / update

| Test | Change |
|---|---|
| `test_build_judge_prompt_contains_opinion` | Assert overall_opinion present; assert element text NOT present |
| `test_call_judge_parses_new_schema` | Mock returns new JSON shape; assert `opinion_check` key preserved in `judge_raw` |
| `test_evaluate_trace_fail_when_no_psa_argument` | `has_psa_argument=false` → verdict FAIL |
| `test_evaluate_trace_pass_when_psa_argument_present` | `has_psa_argument=true` → verdict PASS |
| `test_no_novel_elements_short_circuit` | Unchanged |
| `test_missing_parsed_output` | Unchanged |

## Success metric

Re-run `scripts/run_phosita_vs_human.py` with v2 results. Target: TPR > 33%
(v1 baseline) without TNR regression below 76% (v1 baseline). The 30-trace
labeled set is the measurement instrument.

## Rollback

Delete v2 entries from `traces/phosita_eval_full.jsonl` (filter by
`config.prompt_version == "v2"`). Revert `core/phosita_eval.py` and
`scripts/run_phosita_eval.py`. v1 entries are unaffected.
