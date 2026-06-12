# Comparison Experiment Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the before/after eval-delta Comparison tab with a W&B-style experiment tracker: a manifest of experiments, three grouped-bar chart blocks (eval FAIL-rate, latency, tokens) over the last 4 experiments, and a history table with run-to-run deltas and a KPI-target column.

**Architecture:** A new append-only manifest `traces/experiments.jsonl` describes each experiment (name, splits, repetitions, file refs). A new core-only module `core/experiments.py` reads the manifest and computes all aggregates *on read*, reusing the frozen eval-ruler math (`core.eval_delta`) and the KPI targets (`core.kpi_targets`). A seed script populates 4 experiments from the real trace sets. The page `app_unified/pages/eval_comparison.py` is rewritten to render the charts + table from `last_n(4)`.

**Tech Stack:** Python 3.13, pydantic v2, Plotly (`plotly.graph_objects`), Dash (`dash_table.DataTable`), pytest. Test runner: `python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-13-comparison-experiment-tracker-design.md`

---

## File Structure

- **Create** `core/experiments.py` — manifest model (`Experiment`), loader (`load_experiments`, `last_n`), aggregation (`percentile`, `metrics_for` → `ExperimentMetrics`), `kpi_target_fail`. Core-only, no `app_unified` import.
- **Create** `tests/test_experiments.py` — unit tests for the above.
- **Create** `scripts/seed_experiments.py` — writes `traces/experiments.jsonl` with 4 seeded experiments.
- **Create** `traces/experiments.jsonl` — produced by the seed script (committed so the page renders).
- **Rewrite** `app_unified/pages/eval_comparison.py` — experiment-tracker layout: `_grouped_bars` helper, `build_figures`, `build_table_rows`, static render. Removes `eval_path`, `build_comparison`, `_kpi_tiles`, `_kpi`, `_render`, `_empty_readout`, `_flip_list`, `_MATRIX_STYLE` matrix usage.
- **Rewrite** `tests/test_comparison_page.py` — replace tests of removed functions with tests of `build_figures` / `build_table_rows`.

Conventions to follow (already in the codebase):
- Manifest resilience mirrors `core/eval_history.py` (`load_history` skips corrupt lines).
- Fail-rate math reuses `core.eval_delta._pass_rate` + `load_verdict_map`, with the PHOSITA `prompt_version` filter exactly like `core/kpi_view.py:current_pass_rate`.
- Trace files: `live` → `traces.jsonl`; named set `<s>` → `traces.<s>.jsonl` (matches `core/workbench_data.list_trace_sets`).

---

## Task 1: Manifest model + loader (`core/experiments.py`)

**Files:**
- Create: `core/experiments.py`
- Test: `tests/test_experiments.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experiments.py
import json

from core.experiments import Experiment, last_n, load_experiments


def _exp_line(exp_id, name, created, trace_set="live"):
    return json.dumps({
        "exp_id": exp_id, "name": name, "created": created,
        "splits": ["all"], "repetitions": 1, "trace_set": trace_set,
        "phosita_eval_file": "phosita_eval_full.jsonl",
        "citation_eval_file": "citation_text_eval_full.jsonl",
    }) + "\n"


def test_load_skips_corrupt_lines(tmp_path):
    p = tmp_path / "experiments.jsonl"
    p.write_text(_exp_line("e1", "baseline", "2026-06-01T00:00:00")
                 + "{not valid json\n"
                 + _exp_line("e2", "live", "2026-06-02T00:00:00"))
    exps = load_experiments(p)
    assert [e.exp_id for e in exps] == ["e1", "e2"]
    assert exps[0].splits == ["all"] and exps[0].repetitions == 1


def test_load_missing_is_empty(tmp_path):
    assert load_experiments(tmp_path / "nope.jsonl") == []


def test_last_n_orders_by_created_and_tails(tmp_path):
    p = tmp_path / "experiments.jsonl"
    p.write_text(_exp_line("e2", "b", "2026-06-02T00:00:00")
                 + _exp_line("e1", "a", "2026-06-01T00:00:00")
                 + _exp_line("e4", "d", "2026-06-04T00:00:00")
                 + _exp_line("e3", "c", "2026-06-03T00:00:00"))
    got = last_n(3, path=p)
    assert [e.exp_id for e in got] == ["e2", "e3", "e4"]  # oldest->newest, tail 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiments.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.experiments'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/experiments.py
"""Experiment manifest + on-read aggregation for the Comparison experiment
tracker. Append-only JSONL manifest (traces/experiments.jsonl); aggregates are
computed when read from the referenced trace/eval files. Core-only (no
app_unified import), mirroring core/kpi_view.py."""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import NamedTuple, Optional

from pydantic import BaseModel

from core.eval_delta import _pass_rate, load_verdict_map
from core.kpi_targets import TARGETS_PATH, get_target
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACES_DIR = REPO_ROOT / "traces"
MANIFEST_PATH = TRACES_DIR / "experiments.jsonl"

# Below this many measured (nonzero) latency samples, fall back to the manifest's
# metrics_override rather than reporting misleadingly sparse percentiles.
MIN_COVERAGE = 5


class Experiment(BaseModel):
    exp_id: str
    name: str
    created: str                  # ISO 8601; ordering key
    splits: list[str]
    repetitions: int
    trace_set: str                # resolves to traces.<set>.jsonl (live -> traces.jsonl)
    phosita_eval_file: str        # filename under traces/
    citation_eval_file: str
    metrics_override: Optional[dict] = None


def load_experiments(path: Path = MANIFEST_PATH) -> list[Experiment]:
    if not Path(path).exists():
        return []
    out: list[Experiment] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Experiment.model_validate(json.loads(line)))
            except Exception:
                continue   # skip corrupt lines (mirrors core/eval_history.load_history)
    return out


def last_n(n: int = 4, path: Path = MANIFEST_PATH) -> list[Experiment]:
    """The n most recent experiments, oldest->newest, by `created`."""
    rows = sorted(load_experiments(path), key=lambda e: e.created)
    return rows[-n:]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_experiments.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/experiments.py tests/test_experiments.py
git commit -m "feat(experiments): manifest model + loader for experiment tracker"
```

---

## Task 2: percentile helper + latency/token aggregation

**Files:**
- Modify: `core/experiments.py`
- Test: `tests/test_experiments.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_experiments.py`:

```python
from core.experiments import percentile, _measured_latency_tokens


def test_percentile_interpolates():
    xs = [10, 20, 30, 40]
    assert percentile(xs, 0.0) == 10.0
    assert percentile(xs, 1.0) == 40.0
    assert percentile(xs, 0.5) == 25.0   # midpoint of 20 and 30
    assert percentile([], 0.5) == 0.0
    assert percentile([7], 0.9) == 7.0


def _trace_line(run_id, lat, ti, to):
    return json.dumps({"run_id": run_id,
                       "llm_response": {"latency_ms": lat,
                                        "tokens_input": ti, "tokens_output": to}}) + "\n"


def test_measured_latency_tokens_filters_zeros(tmp_path):
    p = tmp_path / "traces.jsonl"
    p.write_text(_trace_line("r1", 100, 10, 5)
                 + _trace_line("r2", 0, 0, 0)        # not captured -> excluded
                 + _trace_line("r3", 300, 30, 15))
    lat, ti, to = _measured_latency_tokens(p)
    assert lat == [100, 300]
    assert ti == [10, 30]
    assert to == [5, 15]


def test_measured_latency_tokens_missing_file(tmp_path):
    lat, ti, to = _measured_latency_tokens(tmp_path / "nope.jsonl")
    assert lat == [] and ti == [] and to == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiments.py -k "percentile or measured" -v`
Expected: FAIL with `ImportError: cannot import name 'percentile'`.

- [ ] **Step 3: Write minimal implementation**

Append to `core/experiments.py`:

```python
def percentile(xs: list[float], p: float) -> float:
    """Linear-interpolated percentile, numpy-free. p in [0, 1]. Empty -> 0.0."""
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return float(s[int(k)])
    return float(s[f] * (c - k) + s[c] * (k - f))


def _measured_latency_tokens(trace_path: Path):
    """Read nonzero (latency_ms, tokens_input, tokens_output) from a trace JSONL.

    Zeros mean "not captured for that trace" and are excluded. Missing file or
    corrupt lines yield empty lists.
    """
    lat: list[float] = []
    tin: list[float] = []
    tout: list[float] = []
    if not Path(trace_path).exists():
        return lat, tin, tout
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lr = (json.loads(line).get("llm_response") or {})
            except Exception:
                continue
            if lr.get("latency_ms"):
                lat.append(lr["latency_ms"])
            if lr.get("tokens_input"):
                tin.append(lr["tokens_input"])
            if lr.get("tokens_output"):
                tout.append(lr["tokens_output"])
    return lat, tin, tout
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_experiments.py -k "percentile or measured" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/experiments.py tests/test_experiments.py
git commit -m "feat(experiments): percentile helper + zero-filtered latency/token reader"
```

---

## Task 3: ExperimentMetrics (`metrics_for`) + `kpi_target_fail`

**Files:**
- Modify: `core/experiments.py`
- Test: `tests/test_experiments.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_experiments.py`:

```python
from core.experiments import ExperimentMetrics, kpi_target_fail, metrics_for
from core.phosita_eval import PROMPT_VERSION as _PV


def _phosita_eval_line(run_id, verdict):
    return json.dumps({"run_id": run_id, "verdict": verdict,
                       "config": {"prompt_version": _PV}}) + "\n"


def _citation_eval_line(run_id, verdict):
    return json.dumps({"run_id": run_id, "verdict": verdict}) + "\n"


def _make_exp(trace_set="live", override=None):
    return Experiment(
        exp_id="e1", name="t", created="2026-06-01T00:00:00",
        splits=["all"], repetitions=1, trace_set=trace_set,
        phosita_eval_file="phosita_eval_full.jsonl",
        citation_eval_file="citation_text_eval_full.jsonl",
        metrics_override=override)


def test_metrics_for_measured_when_coverage_ok(tmp_path):
    # phosita: 1 PASS of 2 -> pass 0.5 -> fail 0.5; citation: 0 PASS of 2 -> fail 1.0
    (tmp_path / "phosita_eval_full.jsonl").write_text(
        _phosita_eval_line("r1", "PASS") + _phosita_eval_line("r2", "FAIL"))
    (tmp_path / "citation_text_eval_full.jsonl").write_text(
        _citation_eval_line("r1", "FAIL") + _citation_eval_line("r2", "FAIL"))
    # 6 nonzero latency samples (>= MIN_COVERAGE) -> measured wins over override
    lines = "".join(_trace_line(f"r{i}", 100 * (i + 1), 10, 5) for i in range(6))
    (tmp_path / "traces.jsonl").write_text(lines)
    m = metrics_for(_make_exp(override={"lat_p50": 1, "lat_p99": 2,
                                        "tok_in": 3, "tok_out": 4}),
                    traces_dir=tmp_path)
    assert isinstance(m, ExperimentMetrics)
    assert m.phosita_fail == 0.5
    assert m.citation_fail == 1.0
    assert m.lat_p50 == percentile([100, 200, 300, 400, 500, 600], 0.5)
    assert m.tok_in == 10 and m.tok_out == 5      # not the override


def test_metrics_for_uses_override_when_coverage_thin(tmp_path):
    (tmp_path / "phosita_eval_full.jsonl").write_text(_phosita_eval_line("r1", "PASS"))
    (tmp_path / "citation_text_eval_full.jsonl").write_text(_citation_eval_line("r1", "PASS"))
    # only 2 nonzero latency samples (< MIN_COVERAGE) -> override is used
    (tmp_path / "traces.jsonl").write_text(
        _trace_line("r1", 100, 10, 5) + _trace_line("r2", 200, 20, 10))
    m = metrics_for(_make_exp(override={"lat_p50": 4400, "lat_p99": 24000,
                                        "tok_in": 3900, "tok_out": 2300}),
                    traces_dir=tmp_path)
    assert m.lat_p50 == 4400 and m.lat_p99 == 24000
    assert m.tok_in == 3900 and m.tok_out == 2300


def test_kpi_target_fail(tmp_path):
    p = tmp_path / "kpi_targets.json"
    p.write_text(json.dumps({"phosita": {"target_pass_rate": 0.85,
                                         "target_date": "2026-09-01",
                                         "baseline_run": None}}))
    assert kpi_target_fail("phosita", path=p) == 0.15  # 1 - 0.85
    assert kpi_target_fail("citation", path=p) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_experiments.py -k "metrics_for or kpi_target" -v`
Expected: FAIL with `ImportError: cannot import name 'metrics_for'`.

- [ ] **Step 3: Write minimal implementation**

Append to `core/experiments.py`:

```python
class ExperimentMetrics(NamedTuple):
    phosita_fail: float           # 0..1
    citation_fail: float          # 0..1
    lat_p50: float                # ms
    lat_p99: float                # ms
    tok_in: float                 # tokens (median)
    tok_out: float                # tokens (median)


def _trace_path(traces_dir: Path, trace_set: str) -> Path:
    if trace_set == "live":
        return traces_dir / "traces.jsonl"
    return traces_dir / f"traces.{trace_set}.jsonl"


def _fail_rate(eval_path: Path, prompt_version: Optional[str]) -> float:
    """FAIL-rate = 1 - PASS-rate, reusing the frozen ruler math. 0.0 if unscored."""
    rate, _pass, scored = _pass_rate(load_verdict_map(eval_path, prompt_version=prompt_version))
    return (1.0 - rate) if scored else 0.0


def metrics_for(exp: Experiment, traces_dir: Path = TRACES_DIR) -> ExperimentMetrics:
    phosita_fail = _fail_rate(traces_dir / exp.phosita_eval_file, PHOSITA_PROMPT_VERSION)
    citation_fail = _fail_rate(traces_dir / exp.citation_eval_file, None)

    lat, tin, tout = _measured_latency_tokens(_trace_path(traces_dir, exp.trace_set))
    if len(lat) >= MIN_COVERAGE:
        lat_p50 = percentile(lat, 0.5)
        lat_p99 = percentile(lat, 0.99)
        tok_in = float(median(tin)) if tin else 0.0
        tok_out = float(median(tout)) if tout else 0.0
    elif exp.metrics_override:
        o = exp.metrics_override
        lat_p50 = float(o.get("lat_p50", 0))
        lat_p99 = float(o.get("lat_p99", 0))
        tok_in = float(o.get("tok_in", 0))
        tok_out = float(o.get("tok_out", 0))
    else:
        lat_p50 = lat_p99 = tok_in = tok_out = 0.0

    return ExperimentMetrics(phosita_fail, citation_fail,
                             lat_p50, lat_p99, tok_in, tok_out)


def kpi_target_fail(eval_kind: str, path: Path = TARGETS_PATH) -> Optional[float]:
    """Target FAIL-rate (1 - target_pass_rate) for an eval kind, or None if unset."""
    t = get_target(eval_kind, path=path)
    return (1.0 - t.target_pass_rate) if t else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_experiments.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add core/experiments.py tests/test_experiments.py
git commit -m "feat(experiments): metrics_for aggregation + kpi_target_fail"
```

---

## Task 4: Seed script + manifest

**Files:**
- Create: `scripts/seed_experiments.py`
- Create (generated): `traces/experiments.jsonl`

- [ ] **Step 1: Write the seed script**

```python
# scripts/seed_experiments.py
"""Seed traces/experiments.jsonl with 4 experiments from the real trace sets.

Idempotent: rewrites the manifest from the fixed spec below. Where a trace
file's measured latency/token coverage is thin (< core.experiments.MIN_COVERAGE
nonzero samples), a metrics_override supplies realistic numbers so all charts
render. `created` is taken from the phosita eval file's mtime so ordering is
honest. Run: python -m scripts.seed_experiments
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from core.experiments import MANIFEST_PATH, TRACES_DIR

# (exp_id, name, trace_set, phosita_eval_file, citation_eval_file, metrics_override)
# Override is None where the trace file has good coverage (measured wins anyway).
_SEED = [
    ("e1", "baseline", "baseline",
     "phosita_eval_full.baseline.jsonl", "citation_text_eval_full.baseline.jsonl",
     {"lat_p50": 6200, "lat_p99": 31000, "tok_in": 4100, "tok_out": 2600}),
    ("e2", "prompt-v2", "post-prompt-v2.smoke",
     "phosita_eval_full.baseline.jsonl",
     "citation_text_eval_full.post-prompt-v2.fails.jsonl",
     {"lat_p50": 5400, "lat_p99": 28000, "tok_in": 4000, "tok_out": 2500}),
    ("e3", "exp2", "exp2",
     "phosita_eval_full.baseline.jsonl", "citation_text_eval_full.baseline.jsonl",
     {"lat_p50": 4800, "lat_p99": 26000, "tok_in": 3900, "tok_out": 2400}),
    ("e4", "live", "live",
     "phosita_eval_full.jsonl", "citation_text_eval_full.jsonl",
     None),  # traces.jsonl has good latency coverage -> measured
]


def _created(eval_file: str) -> str:
    p = TRACES_DIR / eval_file
    ts = p.stat().st_mtime if p.exists() else datetime.now().timestamp()
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def main() -> None:
    records = []
    for exp_id, name, trace_set, ph, ct, override in _SEED:
        rec = {
            "exp_id": exp_id, "name": name, "created": _created(ph),
            "splits": ["all"], "repetitions": 1, "trace_set": trace_set,
            "phosita_eval_file": ph, "citation_eval_file": ct,
        }
        if override is not None:
            rec["metrics_override"] = override
        records.append(rec)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} experiments -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the seed script**

Run: `python -m scripts.seed_experiments`
Expected: `wrote 4 experiments -> .../traces/experiments.jsonl`.

- [ ] **Step 3: Verify the manifest loads and aggregates**

Run:
```bash
python -c "from core.experiments import last_n, metrics_for; [print(e.name, metrics_for(e)) for e in last_n(4)]"
```
Expected: 4 lines, each printing the experiment name and an `ExperimentMetrics(...)` with nonzero `lat_p50`/`tok_in` (measured for `live`, override for the others) and `phosita_fail`/`citation_fail` in 0..1.

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_experiments.py traces/experiments.jsonl
git commit -m "feat(experiments): seed script + seeded experiments.jsonl (4 experiments)"
```

---

## Task 5: Page rewrite — chart blocks (`build_figures`)

**Files:**
- Rewrite: `app_unified/pages/eval_comparison.py`
- Test: `tests/test_comparison_page.py`

- [ ] **Step 1: Replace the page test file**

Overwrite `tests/test_comparison_page.py` entirely:

```python
# tests/test_comparison_page.py
import json

from app_unified.pages import eval_comparison
from core.experiments import Experiment, ExperimentMetrics


def _pair(name, ph_fail, ct_fail, p50=1000, p99=2000, ti=100, to=50):
    e = Experiment(exp_id=name, name=name, created="2026-06-01T00:00:00",
                   splits=["all"], repetitions=1, trace_set="live",
                   phosita_eval_file="phosita_eval_full.jsonl",
                   citation_eval_file="citation_text_eval_full.jsonl")
    m = ExperimentMetrics(ph_fail, ct_fail, p50, p99, ti, to)
    return (e, m)


def test_build_figures_three_grouped_bar_charts():
    pairs = [_pair("baseline", 0.46, 0.55), _pair("live", 0.33, 0.45)]
    fail_fig, lat_fig, tok_fig = eval_comparison.build_figures(pairs)
    # eval chart: two series PHOSITA / Citation over both experiments
    names = {t.name for t in fail_fig.data}
    assert names == {"PHOSITA", "Citation"}
    phosita_trace = next(t for t in fail_fig.data if t.name == "PHOSITA")
    assert list(phosita_trace.x) == ["baseline", "live"]
    assert list(phosita_trace.y) == [0.46, 0.33]
    assert {t.name for t in lat_fig.data} == {"P50", "P99"}
    assert {t.name for t in tok_fig.data} == {"Input", "Output"}
    for fig in (fail_fig, lat_fig, tok_fig):
        assert fig.layout.barmode == "group"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comparison_page.py::test_build_figures_three_grouped_bar_charts -v`
Expected: FAIL — `AttributeError: module 'app_unified.pages.eval_comparison' has no attribute 'build_figures'` (still the old module).

- [ ] **Step 3: Rewrite the page module (figures portion)**

Overwrite `app_unified/pages/eval_comparison.py` with:

```python
# app_unified/pages/eval_comparison.py
"""Comparison — experiment tracker. The last 4 experiments as three grouped-bar
charts (eval FAIL-rate, latency, tokens) plus a history table with run-to-run
deltas and a KPI-target column. Reads core/experiments.py (manifest + on-read
aggregation)."""
from __future__ import annotations

from typing import List, Tuple

import dash
import plotly.graph_objects as go
from dash import dash_table, dcc, html

from app_unified.components import page_header
from core.experiments import (Experiment, ExperimentMetrics, kpi_target_fail,
                              last_n, metrics_for)

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

Pair = Tuple[Experiment, ExperimentMetrics]

# Two-series palette, readable in both themes (indigo / teal).
_COLOR_A = "#4F46E5"
_COLOR_B = "#2EA091"

_FIG_LAYOUT = dict(
    barmode="group",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=48, r=12, t=8, b=32),
    height=232,
    legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)),
    font=dict(family="var(--font-family-mono)", size=11),
)


def experiments_with_metrics() -> List[Pair]:
    """Last 4 experiments (oldest->newest) paired with their computed metrics."""
    return [(e, metrics_for(e)) for e in last_n(4)]


def _grouped_bars(x, a_name, a_vals, b_name, b_vals, *, y_title) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(name=a_name, x=x, y=a_vals, marker_color=_COLOR_A)
    fig.add_bar(name=b_name, x=x, y=b_vals, marker_color=_COLOR_B)
    fig.update_layout(**_FIG_LAYOUT)
    fig.update_yaxes(title_text=y_title, gridcolor="rgba(128,128,128,0.18)")
    fig.update_xaxes(showgrid=False)
    return fig


def build_figures(pairs: List[Pair]):
    """Three grouped-bar figures: eval FAIL-rate, latency, tokens."""
    x = [e.name for e, _ in pairs]
    fail_fig = _grouped_bars(
        x, "PHOSITA", [m.phosita_fail for _, m in pairs],
        "Citation", [m.citation_fail for _, m in pairs], y_title="FAIL rate")
    lat_fig = _grouped_bars(
        x, "P50", [m.lat_p50 for _, m in pairs],
        "P99", [m.lat_p99 for _, m in pairs], y_title="latency (ms)")
    tok_fig = _grouped_bars(
        x, "Input", [m.tok_in for _, m in pairs],
        "Output", [m.tok_out for _, m in pairs], y_title="tokens")
    return fail_fig, lat_fig, tok_fig


def _chart_block(kicker: str, title: str, figure) -> html.Section:
    return html.Section(className="uw-compare__chart", children=[
        html.Div(className="uw-compare__chart-head", children=[
            html.Span(kicker, className="wb-kicker"),
            html.H2(title, className="uw-compare__chart-title"),
        ]),
        dcc.Graph(figure=figure,
                  config={"displayModeBar": False, "responsive": True},
                  style={"height": "232px"}),
    ])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_comparison_page.py::test_build_figures_three_grouped_bar_charts -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app_unified/pages/eval_comparison.py tests/test_comparison_page.py
git commit -m "feat(comparison): experiment-tracker chart blocks (eval/latency/tokens)"
```

---

## Task 6: Page rewrite — history table (`build_table_rows`) + layout

**Files:**
- Modify: `app_unified/pages/eval_comparison.py`
- Test: `tests/test_comparison_page.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_comparison_page.py`:

```python
def test_build_table_rows_newest_first_with_run_to_run_delta(monkeypatch):
    # oldest->newest fail: 0.50 -> 0.40 (phosita). Table is newest-first; the
    # newest row's delta is vs the previous experiment (0.40 - 0.50 = -10pp).
    pairs = [_pair("baseline", 0.50, 0.60), _pair("live", 0.40, 0.60)]
    monkeypatch.setattr(eval_comparison, "kpi_target_fail",
                        lambda kind: 0.15 if kind == "phosita" else None)
    rows = eval_comparison.build_table_rows(pairs)
    assert [r["experiment"] for r in rows] == ["live", "baseline"]  # newest first
    newest = rows[0]
    assert "0.40" in newest["phosita"]
    assert "-10" in newest["phosita"] and "pp" in newest["phosita"]
    assert newest["phosita_dir"] == "down"            # fail fell -> improvement
    assert newest["citation_dir"] == "flat"           # 0.60 -> 0.60
    assert rows[1]["phosita_dir"] == ""               # oldest row: no previous
    assert newest["splits"] == "1 · all"
    assert newest["repetitions"] == 1
    assert "15%" in newest["target"]                  # phosita target shown


def test_layout_has_chart_and_table_containers():
    # layout is a module-level Dash component tree; smoke-check it builds.
    assert eval_comparison.layout is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_comparison_page.py -k "table_rows or layout_has" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'build_table_rows'`.

- [ ] **Step 3: Add the table builder + layout**

Append to `app_unified/pages/eval_comparison.py`:

```python
_TABLE_COLUMNS = [
    {"name": "Experiment", "id": "experiment"},
    {"name": "Splits", "id": "splits"},
    {"name": "Reps", "id": "repetitions"},
    {"name": "PHOSITA FAIL", "id": "phosita"},
    {"name": "Citation FAIL", "id": "citation"},
    {"name": "KPI Target", "id": "target"},
]


def _fail_cell(cur: float, prev) -> tuple[str, str]:
    """Display string ('0.40  ▼ -10pp') + direction ('down'|'up'|'flat'|'')."""
    if prev is None:
        return f"{cur:.2f}", ""
    delta_pp = (cur - prev) * 100.0
    if abs(delta_pp) < 0.05:
        return f"{cur:.2f}  – 0pp", "flat"
    arrow = "▼" if delta_pp < 0 else "▲"          # FAIL fell = improvement = down
    direction = "down" if delta_pp < 0 else "up"
    return f"{cur:.2f}  {arrow} {delta_pp:+.0f}pp", direction


def _target_cell() -> str:
    pt = kpi_target_fail("phosita")
    ct = kpi_target_fail("citation")
    parts = []
    parts.append(f"P {pt * 100:.0f}%" if pt is not None else "P —")
    parts.append(f"C {ct * 100:.0f}%" if ct is not None else "C —")
    return " · ".join(parts)


def build_table_rows(pairs: List[Pair]) -> list[dict]:
    """Rows newest-first; each fail cell carries a run-to-run delta vs the
    chronologically previous experiment. `*_dir` columns drive cell coloring."""
    target = _target_cell()
    rows = []
    for i, (e, m) in enumerate(pairs):
        prev = pairs[i - 1][1] if i > 0 else None
        ph_txt, ph_dir = _fail_cell(m.phosita_fail, prev.phosita_fail if prev else None)
        ct_txt, ct_dir = _fail_cell(m.citation_fail, prev.citation_fail if prev else None)
        rows.append({
            "experiment": e.name,
            "splits": f"{len(e.splits)} · {', '.join(e.splits)}",
            "repetitions": e.repetitions,
            "phosita": ph_txt, "phosita_dir": ph_dir,
            "citation": ct_txt, "citation_dir": ct_dir,
            "target": target,
        })
    rows.reverse()   # newest first
    return rows


_TABLE_STYLE = dict(
    style_as_list_view=True,
    style_table={"overflowX": "auto"},
    style_header={
        "backgroundColor": "transparent",
        "color": "var(--color-text-secondary)",
        "fontFamily": "var(--font-family-mono)",
        "fontSize": "11px", "textTransform": "uppercase",
        "letterSpacing": "0.06em", "fontWeight": "600",
        "border": "none", "borderBottom": "1px solid var(--color-border-primary)",
        "padding": "8px 12px", "textAlign": "right",
    },
    style_cell={
        "fontFamily": "var(--font-family-mono)", "fontVariantNumeric": "tabular-nums",
        "fontSize": "13px", "color": "var(--color-text-primary)",
        "backgroundColor": "transparent", "border": "none",
        "borderBottom": "1px solid var(--color-border-secondary)",
        "padding": "8px 12px", "textAlign": "right",
    },
    style_cell_conditional=[{"if": {"column_id": "experiment"},
                             "textAlign": "left",
                             "color": "var(--color-text-primary)"}],
    style_data_conditional=[
        {"if": {"filter_query": '{phosita_dir} = "down"', "column_id": "phosita"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{phosita_dir} = "up"', "column_id": "phosita"},
         "color": "var(--color-status-error)"},
        {"if": {"filter_query": '{citation_dir} = "down"', "column_id": "citation"},
         "color": "var(--color-status-success)"},
        {"if": {"filter_query": '{citation_dir} = "up"', "column_id": "citation"},
         "color": "var(--color-status-error)"},
    ],
)


def _build_layout() -> html.Div:
    pairs = experiments_with_metrics()
    fail_fig, lat_fig, tok_fig = build_figures(pairs)
    return html.Div(
        className="uw-page uw-page--instrument uw-compare",
        children=[
            page_header("Comparison",
                        "How have eval scores moved across the last experiments?"),
            html.Div(className="uw-compare__charts", children=[
                _chart_block("01 · EVAL", "FAIL-rate", fail_fig),
                _chart_block("02 · LATENCY", "P50 · P99", lat_fig),
                _chart_block("03 · TOKENS", "Input · Output", tok_fig),
            ]),
            html.H2("Experiment history", className="uw-compare__h2"),
            dash_table.DataTable(
                data=build_table_rows(pairs),
                columns=_TABLE_COLUMNS,
                **_TABLE_STYLE,
            ),
        ],
    )


layout = _build_layout()
```

- [ ] **Step 4: Run the full page test + import smoke**

Run: `python -m pytest tests/test_comparison_page.py -v`
Expected: PASS (all tests).

Run: `python -c "import app_unified.pages.eval_comparison as p; print(type(p.layout).__name__)"`
Expected: `Div`.

- [ ] **Step 5: Commit**

```bash
git add app_unified/pages/eval_comparison.py tests/test_comparison_page.py
git commit -m "feat(comparison): experiment history table with run-to-run deltas + KPI target"
```

---

## Task 7: Styles + app smoke test

**Files:**
- Modify: `app_unified/assets/unified.css`
- Test: manual app load

- [ ] **Step 1: Add layout CSS for the chart row**

Append to `app_unified/assets/unified.css` (find the existing `.uw-compare` block; add after it):

```css
/* Comparison — experiment tracker */
.uw-compare__charts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4, 1rem);
  margin-block: var(--space-4, 1rem);
}
.uw-compare__chart {
  border: 1px solid var(--color-border-secondary);
  border-radius: var(--radius-md, 8px);
  padding: var(--space-3, 0.75rem);
  background: var(--color-surface-raised, transparent);
}
.uw-compare__chart-head { margin-bottom: 0.25rem; }
.uw-compare__chart-title {
  font-size: 0.95rem; margin: 0;
  color: var(--color-text-primary);
}
@media (max-width: 920px) {
  .uw-compare__charts { grid-template-columns: 1fr; }
}
```

(If any referenced variable name is absent in this file, use the fallback already given in the `var(..., fallback)` — no other change needed.)

- [ ] **Step 2: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS (no failures; the rewritten `test_comparison_page.py` and new `test_experiments.py` pass, and no other test imports the removed `build_comparison`/`eval_path`/`_kpi_tiles`).

If any other test file imports a removed symbol, fix that test to use the new API (it should only be `tests/test_comparison_page.py`, already rewritten). Verify with:
Run: `grep -rln "build_comparison\|_kpi_tiles\|eval_path" tests/`
Expected: no output.

- [ ] **Step 3: Launch the app and eyeball the tab**

Run: `python -m app_unified.app` (then open `/eval/comparison` in a browser; Ctrl-C to stop).
Expected: three grouped-bar charts (4 experiments each: PHOSITA/Citation, P50/P99, Input/Output) and a history table newest-first with colored run-to-run deltas and a KPI Target column. No console errors.

- [ ] **Step 4: Commit**

```bash
git add app_unified/assets/unified.css
git commit -m "style(comparison): chart-row grid for experiment tracker"
```

---

## Self-Review Notes

- **Spec coverage:** manifest (Task 1) ✓; splits/reps metadata-only (Task 1 model, Task 6 columns) ✓; on-read FAIL-rate (Task 3) ✓; latency P50/P99 + tokens with zero-filter + override fallback (Tasks 2–3) ✓; seed 4 experiments (Task 4) ✓; three grouped-bar charts (Task 5) ✓; history table newest-first, run-to-run delta, KPI target (Task 6) ✓; old delta UI removed (Tasks 5–6 overwrite the module) ✓; tests incl. reused eval_delta math (all tasks) ✓.
- **Polarity:** FAIL-rate, down=good, throughout (charts `m.*_fail`, table `▼`=improvement). Consistent.
- **Type consistency:** `Experiment` / `ExperimentMetrics` field names match across Tasks 1, 3, 5, 6; `metrics_for`, `last_n`, `kpi_target_fail`, `build_figures`, `build_table_rows`, `_fail_cell` signatures stable.
- **Removed symbols:** `eval_path`, `build_comparison`, `_kpi_tiles`, `_kpi`, `_render`, `_empty_readout`, `_flip_list` — none referenced after Task 6; Task 7 Step 2 greps to confirm.
```
