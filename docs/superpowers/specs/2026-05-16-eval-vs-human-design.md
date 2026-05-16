# Coded Eval vs Human Eval — Comparison Report

**Date:** 2026-05-16
**Eval compared:** `citation_text` (coded eval from prior spec)
**Comparator:** human annotations in `traces/traces_annotations.jsonl`

## Goal

Quantify how well the `citation_text` coded eval agrees with human expert labels on the 30 real
human-annotated traces. Produce a confusion matrix plus TPR and TNR, written to
`traces/eval_vs_human_report.md`.

## Scope

In scope:
- One new pure-function module with the comparison logic.
- One CLI runner that produces the markdown report.
- Schema change to `AnnotationRecord` adding a `source` field.
- One-off backfill of existing `traces_annotations.jsonl` rows.
- Update to the merge script so future coded-eval rows get `source="coded"`.

Out of scope:
- Tuning the coded eval's threshold.
- Re-labeling human annotations.
- Extending the analysis dashboard in `app_annotation.py` (filtering by `source` is a follow-up if
  needed).

## Sample-size note (read first)

Among the 30 real human annotations:
- 19 PASS, 11 FAIL
- Only **2 traces are tagged `citation_text`** (`b247f372`, `a0df6f16`); 9 FAIL traces are tagged
  `absent_phosita_reasoning` only.

TPR has a denominator of 2, so it can only land at 0%, 50%, or 100%. TNR has a denominator of 28
and is the more informative number on this sample. The report should not be over-interpreted as
proof of accuracy — it is a sanity check, not a definitive evaluation.

## Schema change — `source` field

`AnnotationRecord` (in `core/annotation.py`) gains an optional field:

```python
source: Optional[str] = "human"   # "human" | "coded"
```

- Default `"human"` so existing code paths and tests don't break.
- Persisted in JSON via `to_dict` / `from_dict`.
- The annotation tool UI continues to call `AnnotationRecord(...)` without `source` — it gets
  `"human"` automatically.

### One-off backfill

`scripts/backfill_annotation_source.py` rewrites `traces/traces_annotations.jsonl` exactly once:

- Back up the current file to `.jsonl.backup.backfill.<UTC timestamp>` before writing.
- For each row:
  - If `comment` starts with `[code]` → `source="coded"`.
  - Otherwise → `source="human"`.
- Save the file in place.

The script is idempotent — running it again is a no-op because rows already have `source` set; the
script preserves whatever value is there and only sets it for rows missing the field.

### Merge-script update

`scripts/merge_coded_eval_into_annotations.py` adds `source="coded"` to every
`AnnotationRecord` it constructs.

## Architecture

```
scripts/run_eval_vs_human.py            # CLI: loads, scores, writes report
└── core/eval_vs_human.py               # pure functions, no I/O
    ├── load_human_annotations(path)    # filter source=="human" -> dict[run_id -> ann]
    ├── classify_coded(verdict)         # PASS, NO_CITATIONS -> 0;  FAIL -> 1
    ├── classify_human(failure_modes)   # "citation_text" in list -> 1; else 0
    ├── confusion(pairs)                # -> {"tp": …, "fp": …, "fn": …, "tn": …}
    └── tpr(tp, fn) / tnr(tn, fp)       # safe division, returns None when denominator is 0
```

## Data flow

1. Backfill is run once before any comparison (idempotent — safe to re-run).
2. Comparison CLI:
   - Load `traces/traces_annotations.jsonl`; keep rows with `source == "human"`.
   - Load `traces/traces.jsonl`. Drop human annotations whose `run_id` is **not** present in the
     trace file (this naturally removes the 3 test rows, whose `run_id`s are fabricated). After
     filtering, expect exactly **30** rows; assert this and fail loudly on mismatch.
   - For each (annotation, trace) pair, call `core.citation_eval.evaluate_trace(trace)`.
   - Build `pairs = [(human_label, coded_label, run_id), ...]` using `classify_human` and
     `classify_coded`.
3. Compute `confusion(pairs)`, then `tpr` and `tnr`.
4. Render the markdown report; write to file and print to stdout.

## Report format

`traces/eval_vs_human_report.md`:

```markdown
# Citation Text — Coded Eval vs Human Eval

**Sample:** 30 human-annotated traces (`source="human"`, run_id present in traces.jsonl)
**Positive class:** human tagged `citation_text`
**Coded mapping:** FAIL → positive; PASS and NO_CITATIONS → negative
**Config:** ngram_n=5, threshold=0.75

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** |             TP |             FP |
| **Coded negative** |             FN |             TN |

## Metrics

- **TPR (sensitivity)** = TP / (TP + FN) = `<numerator>` / `<denominator>` = `XX.X%`
- **TNR (specificity)** = TN / (TN + FP) = `<numerator>` / `<denominator>` = `XX.X%`
```

If TPR or TNR denominator is 0, render `N/A (no positives in sample)` or
`N/A (no negatives in sample)` in place of the percentage.

## Testing

Unit tests for `core/eval_vs_human.py`:
- `classify_coded("PASS") == 0`; `classify_coded("FAIL") == 1`; `classify_coded("NO_CITATIONS") == 0`.
- `classify_human(["citation_text"]) == 1`; `classify_human(["absent_phosita_reasoning"]) == 0`;
  `classify_human([]) == 0`; `classify_human(["citation_text", "x"]) == 1`.
- `confusion` returns the right counts on a hand-built list of pairs.
- `tpr(0, 0)` returns `None`; same for `tnr(0, 0)`. Non-zero denominators return correct ratio.

Unit tests for `AnnotationRecord.source`:
- New record without `source` keyword defaults to `"human"`.
- `to_dict` / `from_dict` round-trip preserves the field.
- Loading a JSON line without `source` (the legacy on-disk shape) yields `source == "human"`.

One end-to-end smoke test for the CLI:
- Running on the actual repo yields exactly 30 pairs and writes a non-empty markdown report
  containing `TPR` and `TNR` and the four matrix counts.

No regression fixtures on the metrics themselves — the citation_eval already has its own fixtures,
and the new code is arithmetic + filtering.

## Failure modes / edge cases

- **`source` field missing from a row** — `from_dict` defaults to `"human"`. The legacy backup
  files still load correctly.
- **A human annotation's `run_id` is not in `traces.jsonl`** — silently excluded (this is how the
  3 test rows drop out). Logged in the CLI summary as "Skipped (run_id not in traces): N".
- **The expected sample size of 30 is wrong** — assertion failure with a clear error message; the
  user must investigate before the report is written.
- **All-positive or all-negative samples** — TPR or TNR reported as `N/A` with the reason.
- **Backfill run twice** — no-op; existing `source` values are preserved.

## Reproducibility

- Pure stdlib (`json`, `pathlib`). No new pip deps.
- Deterministic: same inputs → byte-for-byte same report.
- Each run logs its config (ngram_n, threshold) inside the report header so a regenerated report
  can be diffed against an older one.
