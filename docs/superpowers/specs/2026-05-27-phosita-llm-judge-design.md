# Absent PHOSITA Reasoning — LLM-Judge Eval Design

**Date:** 2026-05-27
**Failure mode:** `absent_phosita_reasoning` (see [[2026-05-15-phase3-simplification-design]])
**Related:** [[2026-05-16-citation-text-eval-design]], [[2026-05-16-eval-vs-human-design]]
**Target metric:** Per-trace PASS/FAIL agreement with human annotations on the 30-trace ground truth.

## Goal

Build a coded eval for the `absent_phosita_reasoning` failure mode so re-annotation efforts can be driven by an automated PASS/FAIL on all 91 traces, validated against human labels on the 30 annotated traces. The eval is a single Groq judge call per trace (qwen/qwen3-32b) that scores whether the analysis contains genuine person-of-ordinary-skill-in-the-art (PSA) obviousness reasoning.

## Motivation

The Phase 3 taxonomy has 2 failure modes: `citation_text` (already coded — see `core/citation_eval.py`) and `absent_phosita_reasoning` (still ungated, only human-annotated). Without a coded eval for PHOSITA reasoning, the team cannot measure the impact of prompt or model changes on this failure mode across the full trace corpus — only the 30 hand-annotated samples.

Observed behaviour (user description):
> The mental model of person skilled in the art to determine obviousness is weak. Every novel element is considered to be non-obvious with no reasoning on why a PSA will judge this as obvious or non-obvious.

The failure mode is not amenable to a rule-based scorer (no quotable string to n-gram against). LLM-as-judge is the appropriate technique.

## Design decisions (recorded during brainstorm 2026-05-27)

1. **Unit = trace, not element.** One judge call per trace; verdict matches the grain of the human annotation (one failure-mode tag per trace).
2. **Single dimension scored.** Only `reasoning for obviousness`. Threshold-for-obviousness and PSA-understanding sub-dimensions discussed but explicitly dropped to keep the rubric simple.
3. **Two-step rubric inside one prompt.** Judge checks (a) presence of obviousness reasoning in `overall_opinion` and (b) consistency between that reasoning and the per-element `comment` fields. Both checks done internally; single PASS/FAIL emitted.
4. **Judge input = full `parsed_output`.** All `element_mappings` (with `novelty`, `inventive_step`, `verdict`, `comment`) plus `overall_opinion`. No source/target patent text — the failure is about *absent* reasoning, not technically *wrong* reasoning, so the patents aren't needed.
5. **Judge model = `qwen/qwen3-32b` on Groq.** Different family from the model under test (gpt-oss-120b is OpenAI open-weight; qwen3-32b is Alibaba) — reduces self-grading bias. 131K context, JSON object mode, ~$0.05 per full run. No new SDK / API key required. Reasoning mode (thinking vs. non-thinking) is a configurable knob — start with Groq's default; revisit only if calibration vs. human ground truth is poor.
6. **Binary verdict + free-text comment.** No sub-verdicts, no scores, no N/A user-facing class. (Operationally, traces with no novel elements pass vacuously with an N/A note in the comment.)
7. **Validation is diagnostic, not gating.** Build the eval, run it, compare to human ground truth via the existing `eval_vs_human` confusion-matrix pattern. No automatic ship/iterate threshold in this spec.

## Scope

**In scope:**
- New module `core/phosita_eval.py` with `evaluate_trace(trace, groq_client) -> dict | None`.
- New runner `scripts/run_phosita_eval.py` that iterates `traces/traces.jsonl` and writes `traces/phosita_eval_full.jsonl`.
- One-line modification to `core/eval_vs_human.py`: `classify_human` gains an optional `failure_mode_key` argument defaulting to `"citation_text"` (preserves existing behaviour).
- Unit tests in `tests/test_phosita_eval.py` for: judge-prompt construction, JSON parsing, no-novel-elements short-circuit, missing-parsed_output skip.
- An `eval_vs_human` invocation/runner that consumes both `phosita_eval_full.jsonl` and `traces/traces_annotations.jsonl` to produce a confusion matrix for `absent_phosita_reasoning`.

**Out of scope:**
- Re-annotating any human labels.
- Per-element sub-scores or structured sub-verdicts (deliberately simplified to binary).
- Source/target patent text in the judge input.
- Threshold-for-obviousness and PSA-understanding rubrics (deliberately dropped).
- Any changes to `core/llm.py`, `core/models.py`, `core/citation_eval.py`, or the report generator.
- Shipping/iteration decisions based on the v1 vs. human comparison (separate concern).
- Concurrent judge calls (sequential is fine for v1).

## Architecture

```
core/phosita_eval.py            NEW
├── PROMPT_VERSION = "v1"
├── JUDGE_MODEL = "qwen/qwen3-32b"
├── _has_novel_elements(element_mappings) -> bool
├── _build_judge_prompt(parsed_output) -> tuple[str, str]   # (system, user)
├── _call_judge(client, system, user) -> dict               # JSON-only
└── evaluate_trace(trace, client) -> dict | None

core/eval_vs_human.py           MODIFIED
└── classify_human(failure_modes, failure_mode_key="citation_text") -> int

scripts/run_phosita_eval.py     NEW
└── CLI: --traces PATH (default: traces/traces.jsonl)
         --out PATH    (default: traces/phosita_eval_full.jsonl)
    Iterates trace file, calls evaluate_trace, appends one JSON line per
    trace. Skips traces whose (run_id, config.prompt_version) already
    exist in --out (idempotent cache).
```

No new files outside the above. No new dependencies (Groq SDK already present). No schema changes to `traces_annotations.jsonl` or `traces.jsonl`.

## Eval output contract

`evaluate_trace(trace, client)` returns:

```python
{
    "run_id": str,
    "eval_name": "absent_phosita_reasoning",
    "verdict": "PASS" | "FAIL",
    "comment": str,                 # judge's reason, 1-3 sentences
    "judge_raw": str,               # raw judge JSON response, for debugging
    "config": {
        "judge_model": "qwen/qwen3-32b",
        "prompt_version": "v1",
        "temperature": 0.2,
    },
}
```

Returns `None` (and logs to stderr) when:
- `trace["parsed_output"]` is missing or falsy (source model parse failure).
- Judge call raises an exception.
- Judge response is non-JSON or missing required fields.

These are *operational* errors — they leave no line in the output file, so a re-run will retry them. They are not eval verdicts.

Special PASS cases (the judge is not called):
- `element_mappings` empty → `verdict="PASS"`, `comment="N/A: no elements analysed."`
- All elements have `novelty="Y"` → `verdict="PASS"`, `comment="N/A: no novel elements; obviousness reasoning not required."`

## Judge prompt

**System prompt** (sent to `qwen/qwen3-32b`):

```
You are evaluating a patent obviousness analysis. The analysis was produced
by an AI tool that assesses whether a source patent's independent claim is
invalid given a target patent (prior art). For each claim element, the tool
records novelty (Y/N) and inventive_step (Y/N), with a reasoning comment.
The tool also writes an overall_opinion on the source patent's validity.

Your job: judge whether the analysis contains genuine obviousness reasoning
grounded in the person-of-ordinary-skill-in-the-art (PSA) standard.

A PASS analysis:
- The overall_opinion explicitly engages with WHY novel elements are
  obvious or non-obvious to a PSA — it doesn't just state a conclusion.
- The obviousness claims in the overall_opinion are supported by the
  per-element comments (the elements actually contain the reasoning the
  overall_opinion claims).

A FAIL analysis (either pattern triggers FAIL):
- The overall_opinion is silent on obviousness, or asserts non-obviousness
  by default without engaging PSA reasoning ("all novel elements are
  non-obvious", "the source patent is valid because elements are novel").
- The overall_opinion claims obviousness reasoning that the element
  comments don't actually support — hand-waving disconnected from the
  per-element analysis.

Focus only on elements where novelty=N (the obviousness question only
applies to novel elements). Elements with novelty=Y are out of scope —
they're already disclosed, so obviousness doesn't matter.

Return ONLY valid JSON:
{
  "verdict": "PASS" or "FAIL",
  "comment": "1-3 sentences explaining why. Cite specific elements or
              quote phrases from overall_opinion to justify."
}
```

**User prompt** (per trace):

```
ANALYSIS TO JUDGE:

Element mappings:
[for each element: element_number, novelty, inventive_step, verdict, comment]

Overall opinion:
[overall_opinion]
```

The judge call uses `response_format={"type": "json_object"}`, `temperature=0.2`, `max_tokens=1024` (sufficient for one short verdict + 1-3 sentence comment). Reasoning mode left at Groq's default for `qwen/qwen3-32b`; revisit if calibration is poor.

## Validation against human ground truth

The 30 traces in `traces/traces_annotations.jsonl` carry phase-3 `failure_modes` arrays that include `"absent_phosita_reasoning"` where human annotators tagged it. Validation reuses the existing `eval_vs_human` pattern:

1. Run `scripts/run_phosita_eval.py` to produce `traces/phosita_eval_full.jsonl`.
2. Generalise `classify_human` (one-line change): add `failure_mode_key="citation_text"` parameter.
3. Run an `eval_vs_human` invocation (CLI flag or thin runner) that:
   - Loads both files.
   - Joins on `run_id` (inner join — only traces with both human label and coded verdict).
   - Calls `classify_human(annotation["failure_modes"], "absent_phosita_reasoning")` and `classify_coded(coded["verdict"])`.
   - Emits the 2x2 confusion matrix, TPR, TNR, and lists of FP and FN `run_id`s for spot-checking.

This spec does not define a pass/fail threshold for shipping. The artefact is the comparison; downstream decisions on whether to iterate the prompt are out of scope.

## Edge cases

| Case | Behaviour |
|---|---|
| `parsed_output` missing | Skip (return None), log to stderr. Matches `citation_eval`. |
| `element_mappings` empty | Verdict `PASS`, comment `"N/A: no elements analysed."` Judge not called. |
| All elements `novelty="Y"` | Verdict `PASS`, comment `"N/A: no novel elements; obviousness reasoning not required."` Judge not called. |
| Judge returns non-JSON | Log raw output to stderr, return None. User re-runs. |
| Judge call raises | Log + return None. Cache survives. |
| Re-run with same `prompt_version` | Skip traces already present in `--out` whose stored `config.prompt_version` matches the current `PROMPT_VERSION`. |
| Bump `prompt_version` | Existing entries (old version) are kept; the new run appends new entries keyed by the new version. Either version can be queried; downstream analysis filters by `config.prompt_version`. |

## Cost and runtime

- Per full run: 91 traces × ~2.5K input tokens + ~300 output tokens.
- At qwen3-32b pricing (Groq: ~$0.085/M input, ~$0.35/M output): ~**$0.05 per run**.
- Sequential calls in thinking mode at ~3-5s each: **~5-8 min wall time**.
- No concurrency in v1 (user-confirmed). If runtime becomes a friction point later, a 4-way `asyncio.gather` cuts it to ~2 min — trivial follow-up.

## Reproducibility

- `JUDGE_MODEL = "qwen/qwen3-32b"` and `PROMPT_VERSION = "v1"` are module constants in `core/phosita_eval.py`; both are written into every output line's `config` field.
- `temperature=0.2` and `max_tokens=1024` are fixed in `_call_judge`.
- `traces/phosita_eval_full.jsonl` lines are append-only and idempotent on `(run_id, prompt_version)` so re-runs converge to the same file.

## Rollback

- Pure additive change. Revert by deleting `core/phosita_eval.py`, `scripts/run_phosita_eval.py`, `traces/phosita_eval_full.jsonl`, and reverting the single-line `classify_human` signature change. No data migration.

## Risks

- **Risk: qwen3-32b in thinking mode is non-deterministic even at `temperature=0.2`.** Two runs on the same trace may disagree on borderline cases. Mitigation: judge_raw is persisted, so disagreements can be diffed; if seen in practice, switch to non-thinking mode or sample multiple judgments.
- **Risk: judge confuses the two FAIL paths and overweights one.** Without sub-verdicts, you can't tell whether FAILs come from presence-failure or consistency-failure. Mitigation: the `comment` field cites specific elements/phrases; manual review of 5-10 FAILs surfaces the dominant pattern. If consistently miscalibrated, this spec's design upgrades cleanly to Approach B (structured sub-verdicts) or Approach C (two sequential calls) without changing the eval contract.
- **Risk: judge over-credits short overall_opinions** that name obviousness without depth. Mitigation: explicit "doesn't just state a conclusion" wording in the system prompt; iterate `PROMPT_VERSION` if needed.
- **Risk: filtering on `novelty=Y` excludes legitimate cases where the model wrongly marked something novel.** Out of scope for this eval — that's a separate failure mode (novelty miscalibration), not absent PHOSITA reasoning.
