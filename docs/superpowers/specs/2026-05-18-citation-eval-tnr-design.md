# Citation Text Eval — TNR Improvement Design

**Date:** 2026-05-18
**Eval affected:** `citation_text` (see `2026-05-16-citation-text-eval-design.md`)
**Target metric:** TNR (specificity) on the 30 human-annotated traces

## Goal

Lift the coded `citation_text` eval's TNR from 39.3% (11/28) without sacrificing TPR (currently 100%, 2/2). The fix is contained inside `core/citation_eval.score_corresponding`; the trace-level rollup and the eval/output pipeline are unchanged.

## Motivation

Inspection of all 17 false positives shows one dominant pattern: the model emits a `corresponding_text` that stitches together discontinuous verbatim quotes from the target patent using `...`, `…`, or `;` as separators. Each fragment is literally present in the source, but joined together the CT no longer has a long contiguous match or matching 5-grams, so `quotation_score` collapses below the 0.75 threshold even though every piece is verbatim.

Representative examples (all current FPs):

| run_id (prefix) | Current CT score | Fragments after split | Per-fragment scores |
|-----------------|------------------:|------------------------|----------------------|
| `adb8892f` | 0.74 | 2 (`...`) | 1.0, 1.0 |
| `19ae3684` | 0.69 | 2 (`...`) | 1.0, 1.0 |
| `4b409ef1` | 0.50 | 2 (`...`) | 1.0, 1.0 |
| `1a7dd4d4` | 0.66 | 2 (`...`) | 1.0, 0.91 |
| `d0044b02` | 0.68 / 0.58 / 0.74 | 2 / 3 / 2 (`...`) | all 1.0 (except 0.88) |
| `161f8d2c` | 0.52 | 2 (`...`) | 1.0, 1.0 |
| `7acff2e7` | 0.72 | 2 (`;`) | 1.0, 1.0 |
| `ad420124` | 0.60 / 0.72 | 2 (`...`) | all 1.0 |

User decision (brainstorm 2026-05-18): ellipsis- and semicolon-joined verbatim fragments should count as a quote. Meta-narration/parenthetical handling is **not** changed. Trace-level rollup stays strict.

## Scope

**In scope:**
- Modify `score_corresponding` in `core/citation_eval.py` to split CT into fragments before scoring.
- Add unit tests and two new fixture tests in `tests/test_citation_eval.py`.
- Regenerate `traces/citation_text_eval.jsonl` and `traces/eval_vs_human_report.md`.

**Out of scope:**
- Stripping parentheticals or leading meta-phrases (user-rejected).
- Softening the strict trace rollup (user-rejected).
- Lowering `THRESHOLD` (rejected as low-leverage in brainstorm).
- Any LLM-based grading.
- Changes to `core/eval_vs_human.py` or either CLI script.
- Schema changes to `traces_annotations.jsonl`.

## Architecture

```
core/citation_eval.py
├── normalize(text)                # unchanged
├── _ngrams(tokens, n)             # unchanged
├── _contiguous_ratio(...)         # unchanged
├── _ngram_ratio(...)              # unchanged
├── _split_into_fragments(ct_norm) # NEW
├── score_corresponding(ct, ...)   # MODIFIED: splits then scores
└── evaluate_trace(trace)          # unchanged
```

No new files. No new dependencies. `evaluate_trace` continues to consume the same dict shape from `score_corresponding`.

## Fragment splitter

```python
_FRAGMENT_SPLIT_RE = re.compile(r"\s*(?:\.\.\.|…|;)\s*")

def _split_into_fragments(ct_norm: str) -> list[str]:
    if not ct_norm:
        return []
    parts = [p for p in _FRAGMENT_SPLIT_RE.split(ct_norm) if p.strip()]
    return parts if parts else [ct_norm]
```

- Operates on the already-normalized CT (lowercase, NFKC, single-spaced).
- Drops empty / whitespace-only pieces (e.g. trailing `;`, doubled separators).
- A CT with no separator returns a single-element list — same content as today.
- An entirely-empty CT returns `[]` (caller already handles this via the empty-CT short-circuit).

## Updated `score_corresponding`

```python
def score_corresponding(ct: str, target_text: str) -> dict:
    ct_norm = normalize(ct)
    target_norm = normalize(target_text)
    if not target_norm or not ct_norm:
        return {
            "contiguous_ratio": 0.0,
            "ngram_ratio": 0.0,
            "quotation_score": 0.0,
            "verdict": "summarised",
            "num_fragments": 0,
        }

    fragments = _split_into_fragments(ct_norm)
    frag_results = []
    for frag in fragments:
        contiguous = _contiguous_ratio(frag, target_norm)
        ngram = _ngram_ratio(frag, target_norm)
        frag_results.append({
            "contiguous_ratio": contiguous,
            "ngram_ratio": ngram,
            "quotation_score": max(contiguous, ngram),
        })

    worst = min(frag_results, key=lambda r: r["quotation_score"])
    score = worst["quotation_score"]
    verdict = "quoted" if score >= THRESHOLD else "summarised"
    return {
        "contiguous_ratio": worst["contiguous_ratio"],
        "ngram_ratio": worst["ngram_ratio"],
        "quotation_score": score,
        "verdict": verdict,
        "num_fragments": len(fragments),
    }
```

Rationale for per-element output keys mirroring the *worst* fragment: `contiguous_ratio` and `ngram_ratio` in the JSON line should explain *why* the verdict came out the way it did. Returning the worst fragment's components makes a FAIL row immediately diagnosable (you see which sub-score sank it). For PASS rows, the worst fragment is also the limiting one, so the values remain interpretable.

`evaluate_trace` does not need to change — it forwards `quotation_score` and `verdict` from `score_corresponding` and uses them in its existing strict rollup.

## Output schema

`per_element[i]` gains one new key, `num_fragments` (int ≥ 0). Existing keys unchanged. Consumers (`run_eval_vs_human.py`) only read `verdict`, so this is additive.

`config` block in each output row gains a `splitter` field:

```json
"config": {
  "ngram_n": 5,
  "threshold": 0.75,
  "splitter": "\\s*(?:\\.\\.\\.|…|;)\\s*"
}
```

Two `config` constants in `core/citation_eval.py`:

```python
NGRAM_N = 5
NGRAM_FALLBACK_N = 3
THRESHOLD = 0.75
FRAGMENT_SPLITTER = r"\s*(?:\.\.\.|…|;)\s*"
```

`evaluate_trace` reads `FRAGMENT_SPLITTER` to populate the `config` dict.

## Trace-level rollup

Unchanged. Any element with verdict `summarised` makes the trace `FAIL`. `NO_CITATIONS` is unchanged.

## Testing

`tests/test_citation_eval.py` — new and modified tests.

### New unit tests (synthetic targets, deterministic)

1. `test_ellipsis_joined_fragments_count_as_quoted`
   Target: `"the quick brown fox jumps over the lazy dog. an apple a day keeps the doctor away."`
   CT: `"the quick brown fox jumps over ... an apple a day keeps the doctor away"`
   Assert `verdict == "quoted"` and `num_fragments == 2`.

2. `test_semicolon_joined_fragments_count_as_quoted`
   Same target; CT: `"the quick brown fox; an apple a day keeps the doctor away"`
   Assert `verdict == "quoted"` and `num_fragments == 2`.

3. `test_mixed_quoted_and_paraphrased_fragment_is_summarised`
   Target as above; CT: `"the quick brown fox jumps over ... a fabricated phrase not in target"`
   Assert `verdict == "summarised"` (worst fragment fails).

4. `test_no_separator_unchanged_behaviour`
   Same target; CT: `"the quick brown fox jumps over"`
   Assert `verdict == "quoted"`, `num_fragments == 1`, and `quotation_score == 1.0` (regression check against pre-change behavior).

5. `test_trailing_separator_dropped`
   CT: `"the quick brown fox jumps over;"` against same target.
   Assert `num_fragments == 1` (the empty trailing piece is dropped).

6. `test_empty_ct_returns_summarised_with_zero_fragments`
   CT: `""`. Assert `verdict == "summarised"`, `num_fragments == 0`.

### New fixture tests (regression anchors against real traces)

7. `test_adb8892f_flips_to_pass`
   The current FP `adb8892f-...` should now evaluate to `verdict == "PASS"`.

8. `test_1a7dd4d4_flips_to_pass`
   The current FP `1a7dd4d4-...` should now evaluate to `verdict == "PASS"`.

### Preserved existing fixtures (TPR check)

9. `test_b247f372_still_fails` — existing known-FAIL fixture remains `FAIL`.
10. `test_8992c05a_still_passes` — existing known-PASS fixture remains `PASS`.
11. `test_a0df6f16_still_fails` — second known-FAIL fixture remains `FAIL`.

If any of 9–11 regress, the change is rejected; fragment splitting must not introduce false negatives on real annotated FAILs.

## Verification

After the code change:

1. Run `pytest tests/test_citation_eval.py` — all tests pass.
2. Run `python scripts/run_citation_eval.py` — regenerates `traces/citation_text_eval.jsonl`.
3. Run `python scripts/run_eval_vs_human.py` — regenerates `traces/eval_vs_human_report.md`.
4. Inspect the new report:
   - TPR remains 100% (2/2).
   - TNR rises to at least 17/28 = 60.7% (minimum acceptance bar); expected 19–22/28 = 67.9%–78.6% based on FP analysis.

If TPR drops or TNR fails the 60.7% floor, abort and revisit. Commit the regenerated JSONL and markdown report alongside the code change so the improvement appears in the diff.

## Failure modes / edge cases

- **CT ending in `;`** — empty trailing piece is dropped by `_split_into_fragments`. Regression-protected by test 5.
- **Multiple consecutive separators (`A;; B` or `A; ... ; B`)** — all empty intermediate pieces dropped.
- **Both `;` and `...` in the same CT** — single regex pass splits on either.
- **Very short fragment (e.g. `"the"`)** — falls into the existing short-CT fallback in `_ngram_ratio` (≤2 tokens → substring check returns 1.0). User-confirmed acceptable (`fragments count as quotes`). Not adding a minimum-fragment-length filter.
- **`;` inside a verbatim claim element** — typical of patent claims (`method comprising: step A; step B; step C`). Splitting is safe because the combiner (`min` of fragment scores) only flips a CT to `quoted` when *every* fragment is independently verbatim — the splitter cannot fabricate matches.
- **`…` (U+2026) vs `...` (three dots)** — both handled in the same regex. NFKC normalization in `normalize` does **not** fold `…` to `...`, so explicit handling is required.
- **Single-fragment CT must remain bit-identical to current output (except for the new `num_fragments` field)** — guarded by test 4.

## Reproducibility

- Pure stdlib (`difflib`, `unicodedata`, `re`). No new deps.
- Deterministic: same input → same output byte-for-byte.
- `config` block records `ngram_n`, `threshold`, and `splitter` so a future rerun with different separators is distinguishable from this one.

## Success criteria

- All 11 tests in `tests/test_citation_eval.py` pass.
- TPR in `traces/eval_vs_human_report.md` stays at 100% (2/2).
- TNR in the same report is ≥ 60.7% (17/28); the design predicts 67.9%–78.6%.
- `core/citation_eval.py` change is < 40 lines (new helper + modified function).
- No changes outside `core/citation_eval.py`, `tests/test_citation_eval.py`, `traces/citation_text_eval.jsonl`, and `traces/eval_vs_human_report.md`.
