# Comparison Tab → Experiment Tracker — Design

**Date:** 2026-06-13
**Status:** Approved (brainstorm), pending implementation plan
**Route:** `/eval/comparison` (`app_unified/pages/eval_comparison.py`)
**Supersedes:** the Spec-1 before/after eval-delta Comparison view (verdict matrix + flipped-traces).

## Problem

The Comparison tab today is a two-trace-set before/after delta (`core/eval_delta.py`): pick a
baseline set and an experiment set, see a verdict-transition matrix and the list of flipped traces.
It answers "what changed between *these two*", not "how is the metric trending across the
experiments the PM has been running to improve it."

The PM needs a W&B-style **experiment tracker**: the last few experiments, how eval scores
(and cost/latency) moved across them, and a history table. This is the long-deferred **Spec 2**
(see memory `unified-workbench-spec2-experiment-tracker`).

## Decisions (from brainstorm)

1. **Experiment storage:** a new append-only manifest `traces/experiments.jsonl`. One row per
   experiment, referencing existing trace/eval files. Aggregates are computed *on read*, not stored.
2. **Splits/repetitions:** descriptive metadata only. One experiment maps to ONE trace file + ONE
   eval-file pair. `splits` is a label list; `repetitions` is an integer. No per-split/per-rep file
   fan-out.
3. **Metric polarity:** FAIL-rate, lower is better (matches commit `fe8d3a0`, which flipped the
   KPIs from pass-rate to failure-rate). Charts and table show FAIL-rate as a decimal; a falling
   trend is improvement.
4. **Seeding:** seed 4 experiments from the real trace sets that exist (baseline, prompt-v2, exp2,
   live). Where a trace file's latency/token coverage is too thin, the manifest carries a
   `metrics_override` so all charts render fully.
5. **Table delta:** run-to-run — each experiment's eval cell shows the delta vs the **previous
   experiment** (chronologically prior), not vs a fixed baseline.

## Data layer

### Manifest — `traces/experiments.jsonl`

Append-only JSONL (same resilience contract as `eval_history.jsonl` / `load_verdict_map`: skip
corrupt lines). One record per experiment:

```json
{
  "exp_id": "e3",
  "name": "prompt-v2",
  "created": "2026-06-03T06:14:48",
  "splits": ["all"],
  "repetitions": 1,
  "trace_set": "exp2",
  "phosita_eval_file": "phosita_eval_full.baseline.jsonl",
  "citation_eval_file": "citation_text_eval_full.baseline.jsonl",
  "metrics_override": {
    "lat_p50": 4400, "lat_p99": 24000,
    "tok_in": 3900, "tok_out": 2300
  }
}
```

- `created` is the ordering key. "Last 4 experiments" = sort ascending by `created`, take the tail.
- `trace_set` resolves to the trace JSONL used for latency/token aggregation
  (`traces.jsonl` for `live`, `traces.<set>.jsonl` otherwise) — the same suffix convention the page
  already uses for eval files.
- `phosita_eval_file` / `citation_eval_file` are filenames under `traces/`.
- `metrics_override` is **optional**. It is consulted only when the trace file's measured coverage
  is insufficient (see below). Real data is always preferred.

### Reader/aggregation — new `core/experiments.py`

Core-only (no `app_unified` import), mirroring `core/kpi_view.py`. Reuses the frozen eval ruler
math; does not reimplement rate logic.

- `load_experiments(path=MANIFEST_PATH) -> list[Experiment]` — parse manifest, skip corrupt lines.
- `last_n(n=4, ...) -> list[Experiment]` — tail by `created`.
- `ExperimentMetrics` (NamedTuple/dataclass) per experiment, computed on read:
  - **`phosita_fail`, `citation_fail`** (0–1): `1 - pass` where `pass` comes from
    `core.eval_delta._pass_rate(load_verdict_map(<eval_file>, prompt_version=...))`. PHOSITA passes
    `PROMPT_VERSION`; citation passes `None` — identical to `kpi_view.current_pass_rate`.
  - **`lat_p50`, `lat_p99`** (ms): percentiles over `llm_response.latency_ms` across the
    experiment's trace file, **filtering zeros** (zero = latency not captured for that trace).
  - **`tok_in`, `tok_out`**: median over `llm_response.tokens_input` / `tokens_output`, filtering
    zeros.
  - **Coverage fallback:** if fewer than `MIN_COVERAGE` (e.g. 5) nonzero latency samples exist, use
    `metrics_override` for the latency/token fields. This is what makes the sparse sets (e.g. exp2,
    7/91 nonzero) render real-looking bars while real-coverage sets (live, 90/94) use measured data.
- `percentile(xs, p)` — pure-python helper (linear interpolation), no numpy dependency.
- `kpi_target_fail(eval_kind, path=...) -> Optional[float]` — `1 - target_pass_rate` from
  `core.kpi_targets.get_target`. Returns `None` when no target set.

### Seed script — `scripts/seed_experiments.py`

Idempotent (rewrites the manifest from a fixed spec). Writes 4 rows:

| exp_id | name      | trace_set | eval files (suffix) | metrics |
|--------|-----------|-----------|---------------------|---------|
| e1     | baseline  | baseline  | `*.baseline.jsonl`  | measured if covered, else override |
| e2     | prompt-v2 | (smoke/fails set) | `*.post-prompt-v2.*` / baseline | override |
| e3     | exp2      | exp2      | `*.baseline.jsonl`  | override (7/91 nonzero) |
| e4     | live      | live      | `*_full.jsonl`      | measured (90/94 nonzero) |

`created` timestamps are set from the source files' mtimes (oldest→newest) so ordering is honest.
Override numbers are realistic and trend with an improving experiment series.

## Tab structure — `app_unified/pages/eval_comparison.py` (rewrite)

Two stacked sections. The before/after delta UI (the `cmp-before`/`cmp-after`/`cmp-eval`
dropdowns, `_render` callback, `build_comparison`, verdict matrix, flipped-traces) is removed.
Visual polish (card styling, palette, spacing) is deferred to the design-flow pass; this fixes
structure and wiring only.

### Top — three chart blocks (one row, equal thirds)

Grouped bar charts over the last 4 experiments (x = experiment name, oldest→newest), built by a
shared `_grouped_bars(x, series_a, series_b, ...)` Plotly helper. `config={"displayModeBar":
False, "responsive": True}`, fixed height. Two color-coded series per chart:

| Block | Title | Y-axis | Series A | Series B |
|-------|-------|--------|----------|----------|
| 01 | Eval FAIL-rate | FAIL-rate 0–1 | PHOSITA | Citation |
| 02 | Latency | ms | P50 | P99 |
| 03 | Tokens | tokens | Input | Output |

### Bottom — experiment history table

`dash_table.DataTable`, reusing the page's existing mono/hairline `_MATRIX_STYLE` idiom. Rows =
experiments **newest first**. Columns:

`Experiment · Splits · Repetitions · PHOSITA FAIL · Citation FAIL · KPI Target`

- **PHOSITA FAIL / Citation FAIL:** FAIL-rate decimal + delta vs the previous (chronologically
  prior) experiment, rendered via `style_data_conditional`: `▼ -8pp` green = improvement (FAIL
  fell), `▲ +5pp` red = regression. The oldest experiment shows no delta.
- **KPI Target:** target FAIL% per eval kind from `kpi_targets.json`, both shown (e.g. `P 15% ·
  C 15%`). `—` when unset.
- **Splits:** count + names (e.g. `1 · all`). **Repetitions:** integer.

### Wiring

No selectors remain, so the page can render statically at import from `last_n(4)`, or via a
single no-input `@callback` if a refresh signal is wanted later. The three figures and the table
all derive from the same `last_n(4)` + `ExperimentMetrics` pass.

## Testing

- `tests/test_experiments.py` (new): manifest load + skip-corrupt; `last_n` ordering by `created`;
  fail-rate aggregation (reuses ruler math, asserts `1 - pass`); `percentile` correctness;
  zero-filtering; `metrics_override` coverage fallback; `kpi_target_fail` lookup + `None` case.
- Page-level test: from a seeded fixture manifest, assert the three figures and the table render
  with the expected number of bars/rows (no live file dependency — point the reader at a tmp dir).
- `tests/test_eval_delta.py` stays — the rate math it covers is still reused by `core/experiments.py`.

## Out of scope

- Per-split / per-repetition file fan-out and variance bands (reps are a count only).
- A shared global "active trace set" across eval views (still deferred).
- Writing the manifest from the live run pipeline — the seed script populates it for now; a future
  change can append on real experiment runs.
