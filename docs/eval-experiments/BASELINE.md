# Eval Baseline — 2026-06-03 (PatentDiff prompt: pre-experiment)

Frozen reference for the one-change-at-a-time error-rate experiments. The eval
suite (the "ruler") is fixed; these numbers are what each experiment is measured
against. Snapshots:
- `traces/citation_text_eval_full.baseline.jsonl` (87 rows: 32 PASS, 39 FAIL, 16 NO_CITATIONS)
- `traces/phosita_eval_full.baseline.jsonl` (87 rows, v3-only)

## Headline error rates
- **Citation Text FAIL: 39/71 = 55%** (scored = PASS+FAIL; NO_CITATIONS excluded)
- **PHOSITA (v3) FAIL: 39/87 = 45%**
- PHOSITA judge-vs-human (ruler calibration — must stay ~constant): **TPR 77.8% / TNR 60.0%**

## Worst dimension cells (from the dashboard heatmap)
- PHOSITA: System·Long·Novel **67%** (n=15), System·Short·Novel **83%** (n=6)
- PHOSITA gradient by relationship: Anticipation 17% → Implicit 50% → Novel 68%
- Citation: roughly **uniform ~55%** across all dimension cells

## The PatentDiff system prompt being experimented on
`core/llm.py::build_system_prompt()` (in this repo — the prototype is local).
Generation model: `openai/gpt-oss-120b` (env `PATENTDIFF_MODEL`), temp 0.2.
