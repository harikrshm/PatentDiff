# Citation Text — Coded Eval Design

**Date:** 2026-05-16
**Eval name:** `citation_text`
**Failure category mirrored:** `citation_text` ("Tool summarizes prior art instead of quoting verbatim")

## Goal

For every trace in `traces/traces.jsonl` that has not been human-reviewed, decide whether each
non-empty `corresponding_text` inside `parsed_output.element_mappings[]` is a verbatim quote from
the target patent (`independent_claim` + `specification`) or a summary of it. Emit a per-trace
verdict of `PASS` (all citations quoted) or `FAIL` (at least one citation is a summary), plus a
`NO_CITATIONS` bucket for traces where every `corresponding_text` is empty.

## Scope

In scope:
- One new module with the scoring logic and one CLI runner.
- Output written to a new JSONL file kept separate from human annotations.
- Unit/fixture tests using existing annotated traces as regression anchors.

Out of scope:
- Modifying the human annotation file or the dashboard.
- LLM-based judgement (heuristic only — confirmed during brainstorm).
- A meta-phrase override list (Approach C was rejected — the overlap signal already handles it).
- Re-evaluating already-annotated traces (eval runs only on the unannotated subset).

## Architecture

```
scripts/run_citation_eval.py        # CLI: filters unannotated traces, runs eval, writes output
└── core/citation_eval.py           # pure functions, no I/O
    ├── normalize(text)             # NFKC, lowercase, collapse whitespace
    ├── score_corresponding(ct, target_text) -> dict
    └── evaluate_trace(trace) -> dict
```

`core/citation_eval.py` has no I/O so it is trivially unit-testable. The CLI in `scripts/` handles
filesystem reads/writes and the unannotated-set filtering.

## Inputs

1. `traces/traces.jsonl` — JSONL of patent-comparison traces. Each line has:
   - `run_id`
   - `inputs.target_patent.independent_claim` (string)
   - `inputs.target_patent.specification` (string)
   - `parsed_output.element_mappings[]` — each with `element_number`, `element_text`,
     `corresponding_text`, plus other fields the eval ignores.
   - Traces where `parsed_output` is `null` are skipped (model run failed).

2. `traces/traces_annotations.jsonl` — JSONL of human annotations. An entry counts as annotated
   iff `reviewed == true`. Any other state (missing row, `reviewed: false`) means unannotated.

## Selection

The eval runs over the set difference: `{traces with non-null parsed_output} \ {reviewed run_ids}`.
At time of writing this is 87 − 33 = 54 traces.

## Scoring rule (Approach B)

For each `element_mapping` whose `corresponding_text` (CT) is a non-empty string:

1. **Normalize** both CT and `target_text = independent_claim + "\n" + specification`:
   - `unicodedata.normalize("NFKC", s)` — folds non-breaking hyphens (`‑`) and similar.
   - Lowercase.
   - Collapse runs of whitespace to a single space; strip leading/trailing whitespace.

2. **`contiguous_ratio`** = length of longest contiguous matching substring between normalized CT
   and normalized `target_text`, divided by `len(CT_normalized)`. Computed with
   `difflib.SequenceMatcher(None, ct_norm, target_norm).find_longest_match()`.

3. **`ngram_ratio`** = matched 5-word n-grams of CT / total 5-grams of CT. Tokens are produced by
   `str.split()` after normalization. Fallback rules:
   - If CT has fewer than 5 tokens → use 3-grams.
   - If CT has fewer than 3 tokens → `ngram_ratio = 1.0` if every CT token appears anywhere in
     `target_text` (as a substring), else `0.0`.

4. **`quotation_score = max(contiguous_ratio, ngram_ratio)`**

5. **Per-element verdict:** `quoted` if `quotation_score >= 0.75`, else `summarised`.

## Trace verdict (strict rollup)

- Let `scored` = element_mappings whose CT is non-empty after normalization.
- If `scored` is empty → trace verdict is `NO_CITATIONS`.
- Else if every scored element is `quoted` → `PASS`.
- Else (any `summarised`) → `FAIL`.

The strict rule mirrors how the human annotator tagged `b247f372` — multiple summary citations,
whole trace tagged FAIL.

## Output

`traces/citation_text_eval.jsonl` — one line per evaluated trace:

```json
{
  "run_id": "…",
  "eval_name": "citation_text",
  "verdict": "PASS" | "FAIL" | "NO_CITATIONS",
  "num_elements_scored": 4,
  "num_quoted": 2,
  "num_summarised": 2,
  "per_element": [
    {
      "element_number": 1,
      "contiguous_ratio": 0.12,
      "ngram_ratio": 0.04,
      "quotation_score": 0.12,
      "verdict": "summarised"
    }
  ],
  "timestamp": "2026-05-16T…+00:00",
  "config": {"ngram_n": 5, "threshold": 0.75}
}
```

`config` is embedded so a rerun with a different threshold is distinguishable. The CLI prints a
single-line summary at the end: total / PASS / FAIL / NO_CITATIONS counts.

The file is rewritten on each run (not appended) so the file always reflects the latest
config/threshold across the whole eval set.

## Testing

Three fixture-based tests in `tests/test_citation_eval.py`, all sourced from real traces:

1. **Known FAIL** — `b247f372-1a0c-4218-b619-b9e0f6b84bd4` (source `US20250024222A1`). Human
   annotation: `citation_text`. Assert `verdict == "FAIL"` and at least 3 of 4 scored elements
   are `summarised`.

2. **Known PASS** — `8992c05a-2bb5-4ebd-b749-1f3118233e3a`. Human comment: "Clear reasoning and
   text citation". Every CT is a terse claim excerpt. Assert `verdict == "PASS"`.

3. **Known FAIL (second sample)** — `a0df6f16-08b2-4e90-b7bd-0e402154bb48`. Human annotation:
   `citation_text`. Assert `verdict == "FAIL"`.

Plus targeted unit tests on `core/citation_eval.py`:
- `normalize` folds `‑` to `-` and collapses whitespace.
- `score_corresponding` returns `1.0` when CT is a literal substring of target.
- `score_corresponding` returns near-0 when CT contains words absent from target (meta-narration
  like "the specification discloses that").
- Short-CT fallback path (≤4 tokens) is exercised by an explicit case.

The fixtures act as regression anchors only — they do not validate that 0.75 is the right
threshold. If the unannotated-set results look off we tune the threshold and rerun.

## Failure modes / edge cases

- **`parsed_output` is null** — trace skipped at the CLI level; not written to output.
- **`element_mappings` is empty or missing** — treated as `NO_CITATIONS`.
- **`corresponding_text` is whitespace-only** — treated as empty after normalization.
- **Target patent has empty specification** — only `independent_claim` is used; eval still runs.
- **CT is longer than the target text** — possible if model hallucinated text; `contiguous_ratio`
  caps at `len(CT_normalized)` denominator, so a fabricated CT scores low and fails.
- **CT contains a real sub-quote inside meta-narration** — the overlap signal handles this
  naturally: the meta-narration words drag the ratio below 0.75, producing `summarised`. This is
  the desired behaviour per the strict-rollup decision.

## Reproducibility

- Pure stdlib (`difflib`, `unicodedata`, `re`, `json`). No new pip deps.
- Deterministic: same input → same output, byte-for-byte.
- `config` block in each output row records the threshold and n-gram size used.
