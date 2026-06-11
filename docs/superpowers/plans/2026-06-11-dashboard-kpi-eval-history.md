# Dashboard KPI Metrics & Eval-History Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dated eval-history log, PM-set KPI targets, and a small assembly API so the Dashboard's KPI blocks (4–6) have data to read — without touching the eval "ruler."

**Architecture:** Three new `core/` modules (`eval_history`, `kpi_targets`, `kpi_view`) backed by `traces/eval_history.jsonl` and `traces/kpi_targets.json`. PASS-rate math reuses `core.eval_delta.load_verdict_map` + `_pass_rate`. Paths resolve via `core.workbench_data.list_trace_sets` → `TraceSet`. The guarded real-run path of `run_eval` appends history; a CLI backfills existing eval files.

**Tech Stack:** Python, pydantic v2 (models), pytest. JSONL/JSON files under `traces/`.

Spec: `docs/superpowers/specs/2026-06-11-dashboard-kpi-eval-history-design.md`

---

## File Structure

- Create `core/eval_history.py` — history record model, append/load/query, backfill.
- Create `core/kpi_targets.py` — target model, load/get/set with validation.
- Create `core/kpi_view.py` — assembly: current rate, series, trajectory.
- Create `scripts/backfill_eval_history.py` — one-shot CLI seeding history from existing eval files.
- Modify `app_workbench/callbacks.py` — append history on a real eval run.
- Tests: `tests/test_eval_history.py`, `tests/test_kpi_targets.py`, `tests/test_kpi_view.py`, extend `tests/test_workbench_run_eval.py`.

---

## Task 1: eval_history — record model, append, load, query

**Files:**
- Create: `core/eval_history.py`
- Test: `tests/test_eval_history.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_history.py
from core.eval_history import HistoryRecord, append_run, load_history, history_for


def _rec(ts, kind, rate, run_id, trace_set="live"):
    return HistoryRecord(timestamp=ts, eval_kind=kind, trace_set=trace_set,
                         pass_rate=rate, scored=10, prompt_version=None, run_id=run_id)


def test_append_and_load_round_trip(tmp_path):
    p = tmp_path / "hist.jsonl"
    append_run([_rec("2026-06-01T10:00:00", "phosita", 0.5, "a"),
                _rec("2026-06-01T10:00:00", "citation", 0.6, "a")], path=p)
    rows = load_history(p)
    assert len(rows) == 2
    assert rows[0].eval_kind == "phosita" and rows[0].pass_rate == 0.5


def test_load_missing_is_empty(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == []


def test_history_for_filters_and_sorts(tmp_path):
    p = tmp_path / "hist.jsonl"
    append_run([_rec("2026-06-03T10:00:00", "phosita", 0.7, "c")], path=p)
    append_run([_rec("2026-06-01T10:00:00", "phosita", 0.5, "a"),
                _rec("2026-06-02T10:00:00", "citation", 0.6, "b")], path=p)
    ph = history_for("phosita", path=p)
    assert [r.run_id for r in ph] == ["a", "c"]   # sorted by timestamp asc
    assert all(r.eval_kind == "phosita" for r in ph)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_eval_history.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.eval_history'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/eval_history.py
"""Dated history of eval PASS-rates. Append-only JSONL; the eval ruler is frozen,
we only record the rates it produces (via core.eval_delta)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "traces" / "eval_history.jsonl"


class HistoryRecord(BaseModel):
    timestamp: str            # ISO 8601
    eval_kind: str            # "phosita" | "citation"
    trace_set: str
    pass_rate: float          # 0..1
    scored: int               # PASS + FAIL count
    prompt_version: Optional[str] = None
    run_id: str


def append_run(records: list[HistoryRecord], path: Path = HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def load_history(path: Path = HISTORY_PATH) -> list[HistoryRecord]:
    if not Path(path).exists():
        return []
    out: list[HistoryRecord] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(HistoryRecord.model_validate(json.loads(line)))
            except Exception:
                continue   # skip corrupt lines (mirrors load_verdict_map)
    return out


def history_for(eval_kind: str, trace_set: Optional[str] = None,
                path: Path = HISTORY_PATH) -> list[HistoryRecord]:
    rows = [r for r in load_history(path) if r.eval_kind == eval_kind
            and (trace_set is None or r.trace_set == trace_set)]
    return sorted(rows, key=lambda r: r.timestamp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_eval_history.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/eval_history.py tests/test_eval_history.py
git commit -m "feat(history): eval-history record model + append/load/query"
```

---

## Task 2: eval_history — backfill from existing eval files

**Files:**
- Modify: `core/eval_history.py`
- Test: `tests/test_eval_history.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_eval_history.py
from core.eval_history import backfill_from_eval_files


def _write_eval(path, verdicts):
    import json
    with open(path, "w", encoding="utf-8") as f:
        for i, v in enumerate(verdicts):
            f.write(json.dumps({"run_id": f"r{i}", "verdict": v}) + "\n")


def test_backfill_computes_rate_and_is_idempotent(tmp_path):
    # live set: phosita_eval_full.jsonl with 1 PASS of 2 -> rate 0.5
    _write_eval(tmp_path / "phosita_eval_full.jsonl", ["PASS", "FAIL"])
    hist = tmp_path / "hist.jsonl"
    added = backfill_from_eval_files(tmp_path, path=hist)
    assert added == 1
    rows = load_history(hist)
    assert rows[0].eval_kind == "phosita" and rows[0].trace_set == "live"
    assert rows[0].pass_rate == 0.5 and rows[0].scored == 2
    # running again adds nothing (idempotent)
    assert backfill_from_eval_files(tmp_path, path=hist) == 0
    assert len(load_history(hist)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_eval_history.py::test_backfill_computes_rate_and_is_idempotent -q`
Expected: FAIL — `ImportError: cannot import name 'backfill_from_eval_files'`

- [ ] **Step 3: Write minimal implementation**

```python
# add imports near the top of core/eval_history.py
from datetime import datetime

from core.eval_delta import _pass_rate, load_verdict_map
from core.phosita_eval import PROMPT_VERSION as _PHOSITA_PV
from core.workbench_data import list_trace_sets

# best-effort prompt version per eval kind (citation eval exposes none)
PROMPT_VERSIONS = {"phosita": _PHOSITA_PV, "citation": None}


def backfill_from_eval_files(traces_dir: Path, path: Path = HISTORY_PATH) -> int:
    """Seed history from existing eval files (timestamp = file mtime).

    Idempotent: dedup on (eval_kind, trace_set, timestamp). Returns count added.
    """
    existing = {(r.eval_kind, r.trace_set, r.timestamp) for r in load_history(path)}
    new: list[HistoryRecord] = []
    for ts in list_trace_sets(Path(traces_dir)):
        for kind, p in (("phosita", ts.phosita_path), ("citation", ts.citation_path)):
            if not p.exists():
                continue
            rate, _pass, scored = _pass_rate(load_verdict_map(p))
            if scored == 0:
                continue
            stamp = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
            key = (kind, ts.name, stamp)
            if key in existing:
                continue
            existing.add(key)
            new.append(HistoryRecord(
                timestamp=stamp, eval_kind=kind, trace_set=ts.name,
                pass_rate=rate, scored=scored,
                prompt_version=PROMPT_VERSIONS.get(kind),
                run_id=f"backfill-{kind}-{ts.name}"))
    if new:
        append_run(new, path=path)
    return len(new)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_eval_history.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/eval_history.py tests/test_eval_history.py
git commit -m "feat(history): idempotent backfill from existing eval files"
```

---

## Task 3: kpi_targets — model + load/get/set with validation

**Files:**
- Create: `core/kpi_targets.py`
- Test: `tests/test_kpi_targets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kpi_targets.py
import pytest

from core.kpi_targets import Target, get_target, load_targets, set_target


def test_set_get_round_trip(tmp_path):
    p = tmp_path / "kpi.json"
    set_target("phosita", 0.85, "2026-09-01", path=p)
    t = get_target("phosita", path=p)
    assert isinstance(t, Target)
    assert t.target_pass_rate == 0.85 and t.target_date == "2026-09-01"
    assert t.baseline_run is None


def test_missing_file(tmp_path):
    assert load_targets(tmp_path / "nope.json") == {}
    assert get_target("phosita", path=tmp_path / "nope.json") is None


def test_set_validates_rate_and_date(tmp_path):
    p = tmp_path / "kpi.json"
    with pytest.raises(ValueError):
        set_target("phosita", 1.5, "2026-09-01", path=p)
    with pytest.raises(ValueError):
        set_target("phosita", 0.8, "not-a-date", path=p)


def test_set_upserts_without_clobbering_others(tmp_path):
    p = tmp_path / "kpi.json"
    set_target("phosita", 0.85, "2026-09-01", path=p)
    set_target("citation", 0.90, "2026-10-01", path=p)
    assert set(load_targets(p)) == {"phosita", "citation"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kpi_targets.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.kpi_targets'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/kpi_targets.py
"""PM-set KPI targets per eval kind. Stored as a small JSON dict the dashboard
block 6 edits."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = REPO_ROOT / "traces" / "kpi_targets.json"


class Target(BaseModel):
    target_pass_rate: float       # 0..1
    target_date: str              # ISO date "YYYY-MM-DD"
    baseline_run: Optional[str] = None


def load_targets(path: Path = TARGETS_PATH) -> dict[str, Target]:
    if not Path(path).exists():
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
    return {k: Target.model_validate(v) for k, v in raw.items()}


def get_target(eval_kind: str, path: Path = TARGETS_PATH) -> Optional[Target]:
    return load_targets(path).get(eval_kind)


def set_target(eval_kind: str, target_pass_rate: float, target_date: str,
               baseline_run: Optional[str] = None, path: Path = TARGETS_PATH) -> None:
    if not 0.0 <= target_pass_rate <= 1.0:
        raise ValueError("target_pass_rate must be between 0 and 1")
    date.fromisoformat(target_date)  # raises ValueError on a bad date
    targets = load_targets(path)
    targets[eval_kind] = Target(target_pass_rate=target_pass_rate,
                                target_date=target_date, baseline_run=baseline_run)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps({k: v.model_dump() for k, v in targets.items()}, indent=2),
        encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kpi_targets.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/kpi_targets.py tests/test_kpi_targets.py
git commit -m "feat(kpi): KPI targets store (load/get/set with validation)"
```

---

## Task 4: kpi_view — current rate, series, trajectory

**Files:**
- Create: `core/kpi_view.py`
- Test: `tests/test_kpi_view.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kpi_view.py
import json

from core.eval_history import HistoryRecord, append_run
from core.kpi_targets import set_target
from core.kpi_view import Point, current_pass_rate, series, trajectory


def _rec(ts, rate, run_id, kind="phosita"):
    return HistoryRecord(timestamp=ts, eval_kind=kind, trace_set="live",
                         pass_rate=rate, scored=10, prompt_version=None, run_id=run_id)


def test_current_pass_rate_reads_live_eval_file(tmp_path):
    with open(tmp_path / "phosita_eval_full.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"run_id": "r0", "verdict": "PASS"}) + "\n")
        f.write(json.dumps({"run_id": "r1", "verdict": "FAIL"}) + "\n")
    rate, scored = current_pass_rate(tmp_path, "live", "phosita")
    assert rate == 0.5 and scored == 2


def test_series_returns_time_ordered_points(tmp_path):
    h = tmp_path / "hist.jsonl"
    append_run([_rec("2026-06-02T10:00:00", 0.6, "b"),
                _rec("2026-06-01T10:00:00", 0.5, "a")], path=h)
    assert series("phosita", history_path=h) == [
        ("2026-06-01T10:00:00", 0.5), ("2026-06-02T10:00:00", 0.6)]


def test_trajectory_assembles_baseline_current_expected(tmp_path):
    h = tmp_path / "hist.jsonl"
    t = tmp_path / "kpi.json"
    append_run([_rec("2026-06-01T10:00:00", 0.5, "a"),
                _rec("2026-06-05T10:00:00", 0.7, "c")], path=h)
    set_target("phosita", 0.9, "2026-09-01", path=t)
    tr = trajectory("phosita", history_path=h, targets_path=t)
    assert tr.baseline == Point("2026-06-01T10:00:00", 0.5)   # earliest
    assert tr.current == Point("2026-06-05T10:00:00", 0.7)    # latest
    assert tr.expected == Point("2026-09-01", 0.9)            # target


def test_trajectory_empty_history_is_all_none(tmp_path):
    tr = trajectory("phosita", history_path=tmp_path / "h.jsonl",
                    targets_path=tmp_path / "t.json")
    assert tr.baseline is None and tr.current is None and tr.expected is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kpi_view.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.kpi_view'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/kpi_view.py
"""Assembly layer the Dashboard KPI blocks read: current rate, time series, and
the baseline/current/expected trajectory. Combines eval_history + kpi_targets +
the live eval files. core-only (no app_unified dependency)."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

from core.eval_delta import _pass_rate, load_verdict_map
from core.eval_history import HISTORY_PATH, history_for
from core.kpi_targets import TARGETS_PATH, get_target
from core.workbench_data import list_trace_sets


class Point(NamedTuple):
    when: str       # ISO timestamp (history) or ISO date (expected)
    rate: float


class Trajectory(NamedTuple):
    baseline: Optional[Point]
    current: Optional[Point]
    expected: Optional[Point]


def current_pass_rate(traces_dir: Path, trace_set: str, eval_kind: str
                      ) -> tuple[float, int]:
    sets = {s.name: s for s in list_trace_sets(Path(traces_dir))}
    ts = sets.get(trace_set)
    if ts is None:
        return 0.0, 0
    path = ts.phosita_path if eval_kind == "phosita" else ts.citation_path
    rate, _pass, scored = _pass_rate(load_verdict_map(path))
    return rate, scored


def series(eval_kind: str, trace_set: Optional[str] = None,
           history_path: Path = HISTORY_PATH) -> list[tuple[str, float]]:
    return [(r.timestamp, r.pass_rate)
            for r in history_for(eval_kind, trace_set, path=history_path)]


def trajectory(eval_kind: str, history_path: Path = HISTORY_PATH,
               targets_path: Path = TARGETS_PATH) -> Trajectory:
    hist = history_for(eval_kind, path=history_path)
    target = get_target(eval_kind, path=targets_path)

    current = Point(hist[-1].timestamp, hist[-1].pass_rate) if hist else None

    baseline = None
    if hist:
        chosen = None
        if target and target.baseline_run:
            chosen = next((r for r in hist if r.run_id == target.baseline_run), None)
        chosen = chosen or hist[0]
        baseline = Point(chosen.timestamp, chosen.pass_rate)

    expected = Point(target.target_date, target.target_pass_rate) if target else None
    return Trajectory(baseline=baseline, current=current, expected=expected)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_kpi_view.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/kpi_view.py tests/test_kpi_view.py
git commit -m "feat(kpi): kpi_view assembly (current/series/trajectory)"
```

---

## Task 5: Record history on a real eval run

**Files:**
- Modify: `app_workbench/callbacks.py` (the `run_eval` function, ~lines 444–465)
- Test: `tests/test_workbench_run_eval.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_workbench_run_eval.py
def test_run_eval_records_history_on_real_click():
    import types
    import app_workbench.callbacks as cb

    captured = {}
    fake_set = types.SimpleNamespace(name="live",
                                     phosita_path="phosita.jsonl",
                                     citation_path="citation.jsonl")
    orig = (cb.run_evals, cb.resolve_set_strict, cb.load_verdict_map,
            cb._pass_rate, cb.append_run)
    cb.run_evals = lambda *a, **k: "ok"
    cb.resolve_set_strict = lambda _n: fake_set
    cb.load_verdict_map = lambda _p: {"r": "PASS"}
    cb._pass_rate = lambda _m: (1.0, 1, 1)
    cb.append_run = lambda recs, **k: captured.setdefault("recs", recs)
    try:
        cb.run_eval(lambda *_: None, 1, "live", 0)
    finally:
        (cb.run_evals, cb.resolve_set_strict, cb.load_verdict_map,
         cb._pass_rate, cb.append_run) = orig

    recs = captured["recs"]
    assert {r.eval_kind for r in recs} == {"phosita", "citation"}
    assert len({r.run_id for r in recs}) == 1          # one run group
    assert all(r.trace_set == "live" and r.pass_rate == 1.0 for r in recs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workbench_run_eval.py::test_run_eval_records_history_on_real_click -q`
Expected: FAIL — `AttributeError: module 'app_workbench.callbacks' has no attribute 'append_run'`

- [ ] **Step 3: Write minimal implementation**

Add imports near the other `core` imports at the top of `app_workbench/callbacks.py`:

```python
import uuid

from core.eval_delta import _pass_rate, load_verdict_map
from core.eval_history import PROMPT_VERSIONS, HistoryRecord, append_run
```

Then, in `run_eval`, insert the recording block between the successful
`run_evals(...)` call and the `stamp = ...` line (inside the `try`, after the
`except` that handles failure — i.e. right before `stamp = datetime.now()...`):

```python
    # Record this real run's PASS-rates to the dated history (ruler unchanged).
    rid = uuid.uuid4().hex[:8]
    now_iso = datetime.now().isoformat(timespec="seconds")
    recs = []
    for kind, p in (("phosita", ts_set.phosita_path),
                    ("citation", ts_set.citation_path)):
        rate, _pass, scored = _pass_rate(load_verdict_map(p))
        recs.append(HistoryRecord(
            timestamp=now_iso, eval_kind=kind, trace_set=ts_set.name,
            pass_rate=rate, scored=scored,
            prompt_version=PROMPT_VERSIONS.get(kind), run_id=rid))
    append_run(recs)
```

For reference, the surrounding `run_eval` tail should read:

```python
    try:
        run_evals(ts_set, set_status=lambda m: set_progress([m]))
    except Exception as exc:
        set_progress([f"⚠ Eval failed: {exc}"])
        return no_update, no_update

    # Record this real run's PASS-rates to the dated history (ruler unchanged).
    rid = uuid.uuid4().hex[:8]
    now_iso = datetime.now().isoformat(timespec="seconds")
    recs = []
    for kind, p in (("phosita", ts_set.phosita_path),
                    ("citation", ts_set.citation_path)):
        rate, _pass, scored = _pass_rate(load_verdict_map(p))
        recs.append(HistoryRecord(
            timestamp=now_iso, eval_kind=kind, trace_set=ts_set.name,
            pass_rate=rate, scored=scored,
            prompt_version=PROMPT_VERSIONS.get(kind), run_id=rid))
    append_run(recs)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    set_progress([f"Done · {stamp}"])
    return stamp, (version or 0) + 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_workbench_run_eval.py -q`
Expected: PASS (4 tests — the 3 guard tests + the new recording test)

- [ ] **Step 5: Commit**

```bash
git add app_workbench/callbacks.py tests/test_workbench_run_eval.py
git commit -m "feat(history): record eval PASS-rates on a real run"
```

---

## Task 6: Backfill CLI

**Files:**
- Create: `scripts/backfill_eval_history.py`
- Test: none (thin CLI wrapper over the unit-tested `backfill_from_eval_files`)

- [ ] **Step 1: Write the script**

```python
# scripts/backfill_eval_history.py
"""Seed traces/eval_history.jsonl from existing eval files. Idempotent."""
from pathlib import Path

from core.eval_history import backfill_from_eval_files

REPO_ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    added = backfill_from_eval_files(REPO_ROOT / "traces")
    print(f"Backfilled {added} eval-history record(s).")
```

- [ ] **Step 2: Run it (real backfill of this repo's eval files)**

Run: `python scripts/backfill_eval_history.py`
Expected: prints `Backfilled N eval-history record(s).` (N ≥ 1); a second run prints `Backfilled 0`.

- [ ] **Step 3: Verify the seeded file**

Run: `python -c "from core.eval_history import load_history; rows=load_history(); print(len(rows), 'records'); print(rows[0].model_dump() if rows else 'EMPTY')"`
Expected: a positive count and a record with `pass_rate`/`scored`/`timestamp`.

- [ ] **Step 4: Commit**

```bash
git add scripts/backfill_eval_history.py traces/eval_history.jsonl
git commit -m "feat(history): backfill CLI + seeded eval_history.jsonl"
```

---

## Final: Full suite

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS (all prior tests + the new history/targets/view/recording tests).

---

## Self-Review

- **Spec coverage:** eval_history.jsonl schema + append/load/query (Task 1), backfill by mtime + idempotent (Task 2), kpi_targets.json + validation (Task 3), kpi_view current/series/trajectory (Task 4), record-on-real-run integration (Task 5), seeding CLI (Task 6). All spec sections covered.
- **Placeholder scan:** none — every code/test step is complete.
- **Type consistency:** `HistoryRecord`, `Target`, `Point`, `Trajectory` field/signature names match across tasks; `PROMPT_VERSIONS`, `append_run`, `history_for`, `get_target` used consistently; `kpi_view` imports `HISTORY_PATH`/`TARGETS_PATH` defaults defined in Tasks 1/3.
- **Frozen ruler:** no eval-script changes; all rate math via `core.eval_delta`.
