# Design: Dashboard KPI Metrics & Eval-History Backend

Date: 2026-06-11
Status: Approved (brainstorm) — pending implementation plan
Scope: **Backend data model only.** The 6-block Dashboard UI is built afterward
(its own spec/plan) on top of this foundation.

## Context

The Overview console is being revamped into a **Dashboard** (6 blocks, "less
text, more data visualization"). Blocks 4–6 need data that does not exist today:

- **Block 4** — map current eval scores to expected KPI targets.
- **Block 5** — plot each metric over time (baseline → current → expected).
- **Block 6** — let the PM set KPI targets and chart parameters.

Today eval runs **overwrite** per-set output files
(`traces/phosita_eval_full.<set>.jsonl`, `traces/citation_text_eval_full.<set>.jsonl`);
there is **no dated history** and **no target store**. "Experiments over time"
exist only as differently-named trace sets (`baseline`, `exp2`,
`post-prompt-v2.*`). This spec adds the missing history + target data model.

This is the backend foundation of the long-planned experiment tracker.

## Goals

1. Persist a **dated history** of eval PASS-rates, appended on every real eval run.
2. Persist **PM-set KPI targets** (target rate + target date) per eval kind.
3. Provide a small **assembly/query API** the dashboard blocks consume.
4. Keep the eval scripts (the "ruler") **frozen** — only record/target the
   PASS-rates they already produce, reusing existing rate math.

## Non-Goals

- No change to eval scripts, prompts, or scoring (`core.phosita_eval`,
  `core.citation_eval`, `scripts/run_*_eval.py`).
- No FAIL-by-failure-mode metrics, no composite score, no PM-defined custom
  metrics (decided: metric unit = PASS-rate per eval kind).
- No per-(eval × trace set) targets (decided: targets are global per eval kind).
- No UI in this spec (charts/layout are the build spec's concern).

## Decisions (from brainstorm)

- **Metric unit:** PASS-rate % per eval kind — `phosita` and `citation`.
- **History model:** dated append-only log; backfill existing eval files as seed
  points (by file mtime). Wall-clock time axis; a re-run on the same set adds a
  new point.
- **Target model:** per eval kind `{target_pass_rate, target_date, baseline_run}`;
  `baseline_run` defaults to the earliest history record for that eval kind.

## Data Files & Schemas

### `traces/eval_history.jsonl` (append-only; one line per eval-kind per run)

```json
{"timestamp": "2026-06-11T14:30:00", "eval_kind": "phosita", "trace_set": "live",
 "pass_rate": 0.552, "scored": 87, "prompt_version": "phosita-v2",
 "run_id": "8f3a1c2e"}
```

| field | type | notes |
|---|---|---|
| `timestamp` | ISO 8601 str | wall-clock; for real runs = completion time, for backfill = eval-file mtime |
| `eval_kind` | `"phosita"` \| `"citation"` | |
| `trace_set` | str | e.g. `"live"`, `"baseline"` |
| `pass_rate` | float 0..1 | from `core.eval_delta._pass_rate` |
| `scored` | int | PASS+FAIL count (n) |
| `prompt_version` | str \| null | best-effort: `core.phosita_eval.PROMPT_VERSION` etc. |
| `run_id` | str | one id shared by the two records of a single run group |

### `traces/kpi_targets.json` (PM-edited via block 6)

```json
{"phosita":  {"target_pass_rate": 0.85, "target_date": "2026-09-01", "baseline_run": null},
 "citation": {"target_pass_rate": 0.90, "target_date": "2026-09-01", "baseline_run": null}}
```

Missing eval-kind key ⇒ "no target set" (UI shows an unset state). `baseline_run`
is a `run_id` (or null ⇒ earliest history record for that eval kind).

## Modules & APIs

### `core/eval_history.py`

- `append_run(records: list[HistoryRecord], path=HISTORY_PATH) -> None` — append
  JSON lines (used by the run-eval integration with both eval-kind records).
- `load_history(path=HISTORY_PATH) -> list[HistoryRecord]` — read all (empty if
  missing).
- `history_for(eval_kind, trace_set=None, path=HISTORY_PATH) -> list[HistoryRecord]`
  — filtered, sorted by timestamp ascending.
- `backfill_from_eval_files(traces_dir, path=HISTORY_PATH) -> int` — scan existing
  `*_eval_full*.jsonl`, compute `pass_rate`/`scored` via
  `core.eval_delta.load_verdict_map` + `_pass_rate`, timestamp = file mtime;
  append only records not already present (idempotent dedup key:
  `(eval_kind, trace_set, timestamp)`); returns count added.

`HistoryRecord` is a small pydantic model (mirrors the schema above).

### `core/kpi_targets.py`

- `load_targets(path=TARGETS_PATH) -> dict[str, Target]` — `{}` if missing.
- `get_target(eval_kind, path=TARGETS_PATH) -> Target | None`.
- `set_target(eval_kind, target_pass_rate, target_date, baseline_run=None,
  path=TARGETS_PATH) -> None` — upsert one eval kind, persist.

`Target` is a pydantic model `{target_pass_rate: float, target_date: date|str,
baseline_run: str|None}`.

### `core/kpi_view.py` (assembly for dashboard callbacks)

- `current_pass_rate(traces_dir, trace_set, eval_kind) -> tuple[float, int]` —
  (rate, scored) from the current eval file. Resolves paths via
  `core.workbench_data.list_trace_sets(...)` → `TraceSet.phosita_path` /
  `.citation_path` (core-only; no dependency on `app_unified`).
- `series(eval_kind, trace_set=None) -> list[tuple[str, float]]` — `(timestamp,
  pass_rate)` points from history.
- `trajectory(eval_kind, traces_dir, trace_set="live") -> Trajectory` — combines
  history + target into `{baseline: Point|None, current: Point|None,
  expected: Point|None}` where `expected = (target_date, target_pass_rate)`,
  `baseline` = the `baseline_run` (or earliest) point, `current` = latest point.

## Integration

- **Recording (real runs only):** in the `run_eval` background callback
  (`app_workbench/callbacks.py`), after `run_evals(...)` succeeds on the
  guarded `n_clicks >= 1` path, compute both PASS-rates from the freshly-written
  eval files and `append_run([phosita_rec, citation_rec])` sharing one `run_id`.
  The eval subprocess is unchanged.
- **Seeding:** `backfill_from_eval_files(TRACES_DIR)` runs once (idempotent) so
  the time chart is non-empty from existing eval files before any new run.
- **Consumption:** blocks 4/5/6 read only `kpi_view` + `kpi_targets`; block 6
  writes via `kpi_targets.set_target`. Blocks 1–3 keep using existing data.

## Error Handling

- Missing history/target files ⇒ empty results, never raise (dashboard shows
  unset/empty states).
- Corrupt/blank JSON lines in history are skipped (mirrors `load_verdict_map`).
- `set_target` validates `0 <= target_pass_rate <= 1` and a parseable date.

## Testing

- `eval_history`: append→load round-trip; `history_for` filter+sort; backfill
  idempotency (run twice ⇒ same count); backfill rate matches `_pass_rate` on a
  fixture eval file.
- `kpi_targets`: set→get round-trip; missing file ⇒ `{}`/`None`; validation
  rejects out-of-range rate and bad date.
- `kpi_view`: `trajectory` assembles baseline/current/expected from a seeded
  history + target fixture; empty history ⇒ all-None points without raising.
- Integration: `run_eval` real-click path appends two history records (mock
  `run_evals` + eval files); the existing mount-fire guard test still holds.

## Open Questions

None — all forks resolved in brainstorm.
