# Eval Workbench Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Plotly **Dash** "eval workbench" — a single-user, full-BI app that carries a PM through the Notion "Dashboard → Product Decision" arc (how bad → where → why-layer → what-to-fix-first), with a drag-drop pivot heatmap, interactive Frequency × Impact × Exposure priority scoring, a hypothesis-only "shape read" diagnostic, and persisted PM rationale on every derived insight.

**Architecture:** Pure-Python Dash multi-page app (`app_workbench/`) over five new, test-covered `core/` modules that reuse the existing eval outputs and `dimension_tagger`. The eval/judge logic (the "ruler") is never modified — the app only *measures existing trace sets*. Persistence is file-based JSON under `traces/workbench_state/`. The Streamlit dashboard stays as legacy until parity, then is removed in a follow-up.

**Tech Stack:** Python 3.13, Dash 2.x, `dash-draggable` (movable/resizable grid), `dash-pivottable` (drag-drop pivot), `diskcache` (background-callback manager), pandas, pytest. Existing: `core/dimension_tagger`, `scripts/run_phosita_eval.py`, `scripts/run_citation_eval.py`.

**Reference spec:** `docs/superpowers/specs/2026-06-05-eval-workbench-dashboard-design.md`

---

## Scope note (phasing)

This is a large build. It is organized into **four phases**, each producing working, runnable software:

- **Phase 0** — dependencies + app skeleton (app boots, empty pages).
- **Phase 1** — read-only parity: `workbench_data` + KPIs + configurable pivot heatmap. *(Delivers the current dashboard's value, PM-configurable.)*
- **Phase 2** — diagnostics + decision: `diagnostics` (spread+gradient), shape-read widget, `priority` scoring, the Decision surface.
- **Phase 3** — interactivity + persistence: `workbench_state`, draggable layout, PM annotations, background eval-runner.

A reviewer may stop after any phase and have a usable app. Do not start Phase N+1 until Phase N's tasks are committed and green.

---

## File structure (locked before tasks)

| File | Responsibility |
|---|---|
| `core/workbench_data.py` | Discover trace sets; load+merge one set into a DataFrame (extract of `run_dashboard._load_data`). |
| `core/diagnostics.py` | Deterministic shape-read: FAIL pivot, dispersion, relationship gradient, templated evidence-note. |
| `core/priority.py` | Frequency tiering + Freq × Impact × Exposure priority table. |
| `core/workbench_state.py` | Read/write JSON persistence (layout, annotations, priority inputs). |
| `core/eval_runner.py` | Run the existing eval scripts on a selected set as a subprocess job. |
| `app_workbench/app.py` | Dash app entry: multi-page, DiskCache background manager, shared layout. |
| `app_workbench/pages/explore.py` | Surface ①: corpus bar, KPI tiles, pivot heatmap, shape-read, in a draggable grid. |
| `app_workbench/pages/decision.py` | Surface ②: priority inputs, live priority table, layer assignment, decision rationale. |
| `app_workbench/components.py` | Small shared render helpers (KPI tile, evidence-note block, ⚠-assumed badge). |
| `tests/test_workbench_data.py` | Parity + trace-set discovery tests. |
| `tests/test_diagnostics.py` | Dispersion, gradient, evidence-note tests. |
| `tests/test_priority.py` | Frequency tier + priority scoring/sort tests. |
| `tests/test_workbench_state.py` | Round-trip persistence tests. |
| `tests/test_eval_runner.py` | Command-construction test (no real LLM calls). |

---

# Phase 0 — Dependencies & app skeleton

### Task 0: Add dependencies and a bootable Dash skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `app_workbench/__init__.py`
- Create: `app_workbench/app.py`
- Create: `app_workbench/pages/__init__.py`
- Create: `app_workbench/pages/explore.py`
- Create: `app_workbench/pages/decision.py`

- [ ] **Step 1: Add the new dependencies**

Append to `requirements.txt`:

```
dash==2.18.2
dash-draggable==0.1.2
dash-pivottable==0.0.2
diskcache==5.6.3
```

- [ ] **Step 2: Install**

Run: `pip install -r requirements.txt`
Expected: installs dash, dash-draggable, dash-pivottable, diskcache without error.

- [ ] **Step 3: Create the package init files**

`app_workbench/__init__.py`:
```python
```
(empty file)

`app_workbench/pages/__init__.py`:
```python
```
(empty file)

- [ ] **Step 4: Create the two page stubs**

`app_workbench/pages/explore.py`:
```python
"""Surface 1 — Explore / Eval Workbench."""
from __future__ import annotations

import dash
from dash import html

dash.register_page(__name__, path="/", name="Explore")

layout = html.Div([html.H2("Explore / Eval Workbench")])
```

`app_workbench/pages/decision.py`:
```python
"""Surface 2 — Decision."""
from __future__ import annotations

import dash
from dash import html

dash.register_page(__name__, path="/decision", name="Decision")

layout = html.Div([html.H2("Decision")])
```

- [ ] **Step 5: Create the app entry point**

`app_workbench/app.py`:
```python
"""PatentDiff Eval Workbench — Dash entry point.

Run with:
    python -m app_workbench.app
"""
from __future__ import annotations

from pathlib import Path

import dash
import diskcache
from dash import DiskcacheManager, Dash, dcc, html, page_container

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / ".dash_cache"

background_callback_manager = DiskcacheManager(diskcache.Cache(str(CACHE_DIR)))

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="pages",
    background_callback_manager=background_callback_manager,
    suppress_callback_exceptions=True,
)
app.title = "PatentDiff — Eval Workbench"

app.layout = html.Div(
    [
        html.H1("PatentDiff — Eval Workbench"),
        html.Nav(
            [
                dcc.Link("Explore", href="/"),
                html.Span(" · "),
                dcc.Link("Decision", href="/decision"),
            ]
        ),
        html.Hr(),
        page_container,
    ]
)

if __name__ == "__main__":
    app.run(debug=True)
```

- [ ] **Step 6: Boot the app to verify the skeleton**

Run: `python -m app_workbench.app`
Expected: Dash dev server starts on http://127.0.0.1:8050 with no import errors; both nav links render their page heading. Stop with Ctrl+C.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt app_workbench/
git commit -m "feat(workbench): bootable Dash skeleton with two pages"
```

---

# Phase 1 — Read-only parity (data + KPIs + pivot heatmap)

### Task 1: `core/workbench_data.py` — trace-set discovery + merge

**Files:**
- Create: `core/workbench_data.py`
- Test: `tests/test_workbench_data.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_workbench_data.py`:
```python
import json
from pathlib import Path

import pandas as pd

from core.workbench_data import TraceSet, list_trace_sets, load_merged


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_list_trace_sets_discovers_live_and_suffixed(tmp_path: Path):
    (tmp_path / "traces.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "phosita_eval_full.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "citation_text_eval_full.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "phosita_eval_full.exp1.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "citation_text_eval_full.exp1.jsonl").write_text("", encoding="utf-8")

    sets = {s.name: s for s in list_trace_sets(tmp_path)}

    assert "live" in sets
    assert "exp1" in sets
    assert sets["live"].phosita_path.name == "phosita_eval_full.jsonl"
    assert sets["exp1"].phosita_path.name == "phosita_eval_full.exp1.jsonl"


def test_load_merged_one_row_per_trace_with_human_override(tmp_path: Path):
    _write_jsonl(
        tmp_path / "traces.jsonl",
        [{"run_id": "r1", "inputs": {}, "parsed_output": {"element_mappings": []}}],
    )
    _write_jsonl(
        tmp_path / "phosita_eval_full.jsonl",
        [{"run_id": "r1", "verdict": "FAIL", "config": {"prompt_version": "v3"}}],
    )
    _write_jsonl(
        tmp_path / "citation_text_eval_full.jsonl",
        [{"run_id": "r1", "verdict": "PASS"}],
    )
    _write_jsonl(
        tmp_path / "traces_annotations.jsonl",
        [{"run_id": "r1", "phase": 3,
          "dimensions": {"claim_type": "System", "claim_length": "Long",
                         "relationship": "Novel"}}],
    )

    ts = TraceSet(
        name="live",
        traces_path=tmp_path / "traces.jsonl",
        phosita_path=tmp_path / "phosita_eval_full.jsonl",
        citation_path=tmp_path / "citation_text_eval_full.jsonl",
    )
    df = load_merged(ts, annotations_path=tmp_path / "traces_annotations.jsonl")

    assert len(df) == 1
    row = df.iloc[0]
    assert row["run_id"] == "r1"
    assert row["phosita_verdict"] == "FAIL"
    assert row["citation_verdict"] == "PASS"
    assert row["claim_type"] == "System"        # human override applied
    assert row["dim_source"] == "human"


def test_load_merged_filters_phosita_to_v3(tmp_path: Path):
    _write_jsonl(tmp_path / "traces.jsonl",
                 [{"run_id": "r1", "inputs": {}, "parsed_output": {"element_mappings": []}}])
    _write_jsonl(
        tmp_path / "phosita_eval_full.jsonl",
        [{"run_id": "r1", "verdict": "FAIL", "config": {"prompt_version": "v1"}}],
    )
    _write_jsonl(tmp_path / "citation_text_eval_full.jsonl",
                 [{"run_id": "r1", "verdict": "PASS"}])

    ts = TraceSet("live", tmp_path / "traces.jsonl",
                  tmp_path / "phosita_eval_full.jsonl",
                  tmp_path / "citation_text_eval_full.jsonl")
    df = load_merged(ts, annotations_path=tmp_path / "missing.jsonl")

    # v1 phosita verdict ignored; only citation present
    assert df.iloc[0]["phosita_verdict"] is None
    assert df.iloc[0]["citation_verdict"] == "PASS"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.workbench_data'`.

- [ ] **Step 3: Implement the module**

`core/workbench_data.py`:
```python
"""Trace-set discovery and eval-data merge for the Eval Workbench.

Extracted and generalized from scripts/run_dashboard._load_data so that the
Dash app and tests can build the merged frame for ANY trace set (live, baseline,
exp1, ...). Read-only; never writes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core.dimension_tagger import tag_trace
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION

LIVE_PHOSITA = "phosita_eval_full.jsonl"
LIVE_CITATION = "citation_text_eval_full.jsonl"
LIVE_TRACES = "traces.jsonl"


@dataclass(frozen=True)
class TraceSet:
    """One selectable eval set: a phosita file, a citation file, and (optionally) traces."""

    name: str
    traces_path: Path
    phosita_path: Path
    citation_path: Path


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def list_trace_sets(traces_dir: Path) -> list[TraceSet]:
    """Discover all eval sets in `traces_dir`.

    The live set uses the unsuffixed filenames. A suffix <S> is any file named
    `phosita_eval_full.<S>.jsonl`; the matching citation/traces files are paired
    by the same suffix when present.
    """
    sets: list[TraceSet] = []

    if (traces_dir / LIVE_PHOSITA).exists():
        sets.append(
            TraceSet(
                name="live",
                traces_path=traces_dir / LIVE_TRACES,
                phosita_path=traces_dir / LIVE_PHOSITA,
                citation_path=traces_dir / LIVE_CITATION,
            )
        )

    for p in sorted(traces_dir.glob("phosita_eval_full.*.jsonl")):
        # filename: phosita_eval_full.<suffix>.jsonl  -> suffix is the middle part
        suffix = p.name[len("phosita_eval_full.") : -len(".jsonl")]
        if not suffix:
            continue
        sets.append(
            TraceSet(
                name=suffix,
                traces_path=traces_dir / f"traces.{suffix}.jsonl",
                phosita_path=p,
                citation_path=traces_dir / f"citation_text_eval_full.{suffix}.jsonl",
            )
        )
    return sets


def load_merged(trace_set: TraceSet, annotations_path: Path) -> pd.DataFrame:
    """Merge one trace set into a frame: one row per trace with >=1 eval result.

    Columns: run_id, claim_type, claim_length, relationship, dim_source,
    phosita_verdict, citation_verdict.
    """
    traces = {t["run_id"]: t for t in _iter_jsonl(trace_set.traces_path) if "run_id" in t}
    dims = {rid: tag_trace(t) for rid, t in traces.items()}

    for ann in _iter_jsonl(annotations_path):
        if ann.get("phase") == 3 and ann.get("dimensions") and ann.get("run_id") in dims:
            rid = ann["run_id"]
            hd = ann["dimensions"]
            dims[rid] = {
                "claim_type": hd.get("claim_type", dims[rid]["claim_type"]),
                "claim_length": hd.get("claim_length", dims[rid]["claim_length"]),
                "relationship": hd.get("relationship", dims[rid]["relationship"]),
                "source": "human",
            }

    phosita: dict[str, str] = {}
    for r in _iter_jsonl(trace_set.phosita_path):
        if (r.get("config") or {}).get("prompt_version") == PHOSITA_PROMPT_VERSION:
            if r.get("run_id") and r.get("verdict"):
                phosita[r["run_id"]] = r["verdict"]

    citation: dict[str, str] = {}
    for r in _iter_jsonl(trace_set.citation_path):
        if r.get("run_id") and r.get("verdict"):
            citation[r["run_id"]] = r["verdict"]

    default_dim = {"claim_type": "Unknown", "claim_length": "Unknown",
                   "relationship": "Unknown", "source": "inferred"}
    rows = []
    for rid in set(phosita) | set(citation):
        dim = dims.get(rid, default_dim)
        rows.append({
            "run_id": rid,
            "claim_type": dim["claim_type"],
            "claim_length": dim["claim_length"],
            "relationship": dim["relationship"],
            "dim_source": dim["source"],
            "phosita_verdict": phosita.get(rid),
            "citation_verdict": citation.get(rid),
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_data.py -v`
Expected: 3 passed.

- [ ] **Step 5: Verify parity with the live dashboard data**

Run:
```bash
python -c "from pathlib import Path; from core.workbench_data import list_trace_sets, load_merged; root=Path('traces'); ts=[s for s in list_trace_sets(root) if s.name=='live'][0]; df=load_merged(ts, root/'traces_annotations.jsonl'); print(len(df), 'rows;', int((df.phosita_verdict=='FAIL').sum()), 'phosita FAIL;', int((df.citation_verdict=='FAIL').sum()), 'citation FAIL')"
```
Expected: prints a non-zero row count and FAIL counts consistent with the current Streamlit Summary tab (~39 PHOSITA FAIL, ~39 citation FAIL).

- [ ] **Step 6: Commit**

```bash
git add core/workbench_data.py tests/test_workbench_data.py
git commit -m "feat(workbench): trace-set discovery + eval merge (core.workbench_data)"
```

---

### Task 2: Shared render helpers (`components.py`)

**Files:**
- Create: `app_workbench/components.py`

- [ ] **Step 1: Implement the shared components**

`app_workbench/components.py`:
```python
"""Small shared render helpers for the workbench pages."""
from __future__ import annotations

from dash import html

GREEN, YELLOW, RED = "#2e7d32", "#f9a825", "#c62828"


def fail_color(rate: float) -> str:
    """Red/yellow/green for a FAIL rate in [0,1]."""
    if rate >= 0.67:
        return RED
    if rate >= 0.34:
        return YELLOW
    return GREEN


def kpi_tile(label: str, value: str, sub: str) -> html.Div:
    """A single KPI metric tile."""
    return html.Div(
        [
            html.Div(label, style={"fontSize": "0.8rem", "color": "#555"}),
            html.Div(value, style={"fontSize": "1.8rem", "fontWeight": "700"}),
            html.Div(sub, style={"fontSize": "0.75rem", "color": "#888"}),
        ],
        style={"padding": "0.75rem", "border": "1px solid #e0e0e0",
               "borderRadius": "8px", "minWidth": "150px"},
    )


def assumed_badge() -> html.Span:
    """The ⚠ badge marking a domain-assumed (not measured) input."""
    return html.Span(
        "⚠ assumed",
        title="Placeholder until the live claim_type × relationship query "
              "distribution is instrumented.",
        style={"color": RED, "fontSize": "0.7rem", "marginLeft": "0.4rem"},
    )


def evidence_note(text: str) -> html.Div:
    """Render a deterministic evidence-note, clearly labeled as a hypothesis."""
    return html.Div(
        [
            html.Span("HYPOTHESIS  ",
                      style={"fontWeight": "700", "color": "#1565c0",
                             "fontSize": "0.7rem"}),
            html.Span(text, style={"fontSize": "0.85rem"}),
        ],
        style={"padding": "0.4rem 0.6rem", "background": "#e3f2fd",
               "borderRadius": "6px", "margin": "0.3rem 0"},
    )
```

- [ ] **Step 2: Smoke-test the import**

Run: `python -c "from app_workbench.components import kpi_tile, fail_color, assumed_badge, evidence_note; print(fail_color(0.7), fail_color(0.5), fail_color(0.1))"`
Expected: prints `#c62828 #f9a825 #2e7d32`.

- [ ] **Step 3: Commit**

```bash
git add app_workbench/components.py
git commit -m "feat(workbench): shared render helpers (kpi tile, evidence-note, assumed badge)"
```

---

### Task 3: Surface ① — corpus selector + KPI tiles

**Files:**
- Modify: `app_workbench/pages/explore.py`

- [ ] **Step 1: Replace the explore stub with corpus selector + KPI row**

`app_workbench/pages/explore.py`:
```python
"""Surface 1 — Explore / Eval Workbench."""
from __future__ import annotations

from pathlib import Path

import dash
from dash import Input, Output, callback, dcc, html

from app_workbench.components import kpi_tile
from core.workbench_data import list_trace_sets, load_merged

dash.register_page(__name__, path="/", name="Explore")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"
ANNOTATIONS_PATH = TRACES_DIR / "traces_annotations.jsonl"


def _trace_set_options():
    return [{"label": s.name, "value": s.name} for s in list_trace_sets(TRACES_DIR)]


def _load(active_name: str):
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    ts = sets.get(active_name) or next(iter(sets.values()))
    return load_merged(ts, ANNOTATIONS_PATH)


layout = html.Div(
    [
        html.Div(
            [
                html.Label("Active trace set:"),
                dcc.Dropdown(
                    id="corpus-selector",
                    options=_trace_set_options(),
                    value="live",
                    clearable=False,
                    style={"width": "240px"},
                ),
            ],
            style={"display": "flex", "gap": "0.6rem", "alignItems": "center"},
        ),
        html.H3("How bad is it?"),
        html.Div(id="kpi-row", style={"display": "flex", "gap": "0.8rem", "flexWrap": "wrap"}),
    ]
)


@callback(Output("kpi-row", "children"), Input("corpus-selector", "value"))
def _render_kpis(active_name: str):
    df = _load(active_name)
    ph = df[df["phosita_verdict"].isin(["PASS", "FAIL"])]
    ct = df[df["citation_verdict"].isin(["PASS", "FAIL"])]
    both = df[df["phosita_verdict"].isin(["PASS", "FAIL"])
              & df["citation_verdict"].isin(["PASS", "FAIL"])]

    ph_rate = (ph["phosita_verdict"] == "FAIL").mean() if not ph.empty else 0.0
    ct_rate = (ct["citation_verdict"] == "FAIL").mean() if not ct.empty else 0.0
    either = (((both["phosita_verdict"] == "FAIL") | (both["citation_verdict"] == "FAIL")).mean()
              if not both.empty else 0.0)
    clean = (((both["phosita_verdict"] == "PASS") & (both["citation_verdict"] == "PASS")).mean()
             if not both.empty else 0.0)

    return [
        kpi_tile("PHOSITA Reasoning FAIL", f"{ph_rate:.0%}", f"n={len(ph)}"),
        kpi_tile("Citation Text FAIL", f"{ct_rate:.0%}", f"n={len(ct)}"),
        kpi_tile("Either fails", f"{either:.0%}", f"n={len(both)}"),
        kpi_tile("Fully clean", f"{clean:.0%}", f"n={len(both)}"),
    ]
```

- [ ] **Step 2: Boot and verify KPIs render**

Run: `python -m app_workbench.app`
Expected: Explore page shows the corpus dropdown (with "live" and any exp sets) and four KPI tiles with non-zero percentages matching the Streamlit Summary tab. Stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add app_workbench/pages/explore.py
git commit -m "feat(workbench): explore corpus selector + KPI tiles"
```

---

### Task 4: Surface ① — configurable drag-drop pivot heatmap

**Files:**
- Modify: `app_workbench/pages/explore.py`

- [ ] **Step 1: Add a pivot section using dash-pivottable**

In `app_workbench/pages/explore.py`, add the import at the top (with the other imports):
```python
import dash_pivottable
```

Append to the `layout` children list (after the `kpi-row` Div), i.e. add these two elements inside the outer `html.Div([...])`:
```python
        html.H3("Where does it fail? (drag dimensions onto Rows / Cols / Filters)"),
        dcc.RadioItems(
            id="pivot-eval",
            options=[
                {"label": "PHOSITA", "value": "phosita"},
                {"label": "Citation", "value": "citation"},
                {"label": "Either", "value": "either"},
            ],
            value="phosita",
            inline=True,
        ),
        html.Div(id="pivot-container"),
```

- [ ] **Step 2: Add the pivot-building callback**

Append to `app_workbench/pages/explore.py`:
```python
def _fail_frame(df, eval_name: str):
    """Long frame with one 'fail' label column per scored trace, for the pivot."""
    work = df.copy()
    if eval_name == "phosita":
        scored = work[work["phosita_verdict"].isin(["PASS", "FAIL"])].copy()
        scored["result"] = scored["phosita_verdict"]
    elif eval_name == "citation":
        scored = work[work["citation_verdict"].isin(["PASS", "FAIL"])].copy()
        scored["result"] = scored["citation_verdict"]
    else:
        mask = (work["phosita_verdict"].isin(["PASS", "FAIL"])
                | work["citation_verdict"].isin(["PASS", "FAIL"]))
        scored = work[mask].copy()
        scored["result"] = (
            ((scored["phosita_verdict"] == "FAIL")
             | (scored["citation_verdict"] == "FAIL"))
            .map({True: "FAIL", False: "PASS"})
        )
    return scored[["claim_type", "claim_length", "relationship", "result"]]


@callback(
    Output("pivot-container", "children"),
    Input("corpus-selector", "value"),
    Input("pivot-eval", "value"),
)
def _render_pivot(active_name: str, eval_name: str):
    df = _load(active_name)
    scored = _fail_frame(df, eval_name)
    scored = scored[(scored["claim_type"] != "Unknown")
                    & (scored["relationship"] != "Unknown")]
    data = [scored.columns.tolist()] + scored.values.tolist()
    return dash_pivottable.PivotTable(
        id="pivot-table",
        data=data,
        rows=["claim_type", "claim_length"],
        cols=["relationship"],
        vals=["result"],
        aggregatorName="Count as Fraction of Rows",
        rendererName="Heatmap",
    )
```

> **Note:** `dash-pivottable` natively supports dragging any field between Rows/Cols/Filters and a "Count as Fraction of Rows" aggregator over the PASS/FAIL `result` column — this *is* the configurable FAIL-rate heatmap. The `rows`/`cols`/`vals` args only seed the default arrangement.

- [ ] **Step 3: Boot and verify the pivot**

Run: `python -m app_workbench.app`
Expected: a pivot table renders with claim_type/claim_length on rows, relationship on columns, heatmap shading. Dragging `relationship` to Filters and switching the eval radio both update the grid. Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add app_workbench/pages/explore.py
git commit -m "feat(workbench): configurable drag-drop pivot heatmap"
```

> **Phase 1 complete:** the app now reproduces the dashboard's how-bad + where, fully PM-configurable.

---

# Phase 2 — Diagnostics & Decision

### Task 5: `core/diagnostics.py` — dispersion, gradient, evidence-note

**Files:**
- Create: `core/diagnostics.py`
- Test: `tests/test_diagnostics.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_diagnostics.py`:
```python
import pandas as pd

from core.diagnostics import (
    cell_fail_rates,
    dispersion_pp,
    relationship_gradient,
    evidence_note,
)


def _df(rows):
    return pd.DataFrame(rows)


def test_cell_fail_rates_excludes_low_n_from_dispersion():
    df = _df([
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
    ])
    rates = cell_fail_rates(df, "phosita")
    assert rates[("Method", "Anticipation")] == (0.0, 3)
    assert rates[("System", "Novel")] == (1.0, 3)


def test_dispersion_pp_is_max_minus_min_over_reliable_cells():
    df = _df([
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
        {"claim_type": "System", "relationship": "Novel", "phosita_verdict": "FAIL"},
    ])
    assert dispersion_pp(df, "phosita") == 100.0  # 0% vs 100%


def test_relationship_gradient_detects_monotonic_increase():
    rows = []
    # Anticipation 0/4, Implicit 2/4, Novel 4/4
    for v in ["PASS", "PASS", "PASS", "PASS"]:
        rows.append({"claim_type": "Method", "relationship": "Anticipation", "phosita_verdict": v})
    for v in ["PASS", "PASS", "FAIL", "FAIL"]:
        rows.append({"claim_type": "Method", "relationship": "Implicit", "phosita_verdict": v})
    for v in ["FAIL", "FAIL", "FAIL", "FAIL"]:
        rows.append({"claim_type": "Method", "relationship": "Novel", "phosita_verdict": v})
    g = relationship_gradient(_df(rows), "phosita")
    assert g.monotonic_increasing is True
    assert g.worst_relationship == "Novel"
    assert g.rates["Anticipation"] == 0.0
    assert g.rates["Novel"] == 1.0


def test_evidence_note_uniform_says_layer1():
    note = evidence_note(dispersion=10.0, gradient=None)
    assert "uniform" in note.lower()
    assert "layer-1" in note.lower() or "layer 1" in note.lower()


def test_evidence_note_gradient_says_reasoning_correlated():
    from core.diagnostics import RelationshipGradient
    g = RelationshipGradient(
        rates={"Anticipation": 0.17, "Implicit": 0.5, "Novel": 0.68},
        monotonic_increasing=True,
        worst_relationship="Novel",
    )
    note = evidence_note(dispersion=51.0, gradient=g)
    assert "reasoning" in note.lower()
    assert "novel" in note.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_diagnostics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.diagnostics'`.

- [ ] **Step 3: Implement the module**

`core/diagnostics.py`:
```python
"""Deterministic 'shape read' diagnostics for the Eval Workbench.

These functions describe the SHAPE of the failure distribution (how spread out,
whether it rises with reasoning difficulty) and emit a TEMPLATED hypothesis
string. They never return a verdict — the PM assigns the architecture layer.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MIN_RELIABLE_N = 3
REL_ORDER = ["Anticipation", "Implicit", "Novel"]
UNIFORM_THRESHOLD_PP = 25.0  # spread below this reads as "uniform"


def _verdict_col(eval_name: str) -> str:
    return "phosita_verdict" if eval_name == "phosita" else "citation_verdict"


def cell_fail_rates(df: pd.DataFrame, eval_name: str) -> dict[tuple[str, str], tuple[float, int]]:
    """FAIL rate + n per (claim_type, relationship) cell, scored traces only."""
    col = _verdict_col(eval_name)
    scored = df[df[col].isin(["PASS", "FAIL"])].copy()
    scored = scored[(scored["claim_type"] != "Unknown")
                    & (scored["relationship"] != "Unknown")]
    scored["fail"] = scored[col] == "FAIL"
    out: dict[tuple[str, str], tuple[float, int]] = {}
    grouped = scored.groupby(["claim_type", "relationship"])["fail"]
    for key, series in grouped:
        out[key] = (float(series.mean()), int(series.count()))
    return out


def dispersion_pp(df: pd.DataFrame, eval_name: str) -> float:
    """Spread (max - min, in percentage points) of FAIL rate across reliable cells."""
    rates = [r for r, n in cell_fail_rates(df, eval_name).values() if n >= MIN_RELIABLE_N]
    if len(rates) < 2:
        return 0.0
    return round((max(rates) - min(rates)) * 100, 1)


@dataclass
class RelationshipGradient:
    rates: dict[str, float]
    monotonic_increasing: bool
    worst_relationship: str | None


def relationship_gradient(df: pd.DataFrame, eval_name: str) -> RelationshipGradient:
    """FAIL rate along Anticipation -> Implicit -> Novel, and whether it rises monotonically."""
    col = _verdict_col(eval_name)
    scored = df[df[col].isin(["PASS", "FAIL"])].copy()
    scored["fail"] = scored[col] == "FAIL"
    rates: dict[str, float] = {}
    for rel in REL_ORDER:
        sub = scored[scored["relationship"] == rel]["fail"]
        if not sub.empty:
            rates[rel] = float(sub.mean())
    ordered = [rates[r] for r in REL_ORDER if r in rates]
    monotonic = len(ordered) >= 2 and all(b >= a for a, b in zip(ordered, ordered[1:]))
    worst = max(rates, key=rates.get) if rates else None
    return RelationshipGradient(rates=rates, monotonic_increasing=monotonic, worst_relationship=worst)


def evidence_note(dispersion: float, gradient: RelationshipGradient | None) -> str:
    """Templated hypothesis string. NOT a verdict."""
    if dispersion <= UNIFORM_THRESHOLD_PP:
        return (f"FAIL% spread across cells = {dispersion:.0f}pp (low) → uniform → "
                f"Layer-1 (instruction) hypothesis.")
    parts = [f"FAIL% spread across cells = {dispersion:.0f}pp (high) → clustered."]
    if gradient and gradient.monotonic_increasing and gradient.rates:
        chain = " → ".join(f"{r} {gradient.rates[r]:.0%}"
                           for r in REL_ORDER if r in gradient.rates)
        parts.append(f"Rises monotonically with reasoning difficulty ({chain}) → "
                     f"reasoning-correlated → Layer-2/3 signal; "
                     f"worst cluster: {gradient.worst_relationship}.")
    else:
        parts.append("No clean reasoning gradient → inspect which cells drive the cluster.")
    return " ".join(parts)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_diagnostics.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add core/diagnostics.py tests/test_diagnostics.py
git commit -m "feat(workbench): shape-read diagnostics (dispersion, gradient, evidence-note)"
```

---

### Task 6: Surface ① — shape-read widget

**Files:**
- Modify: `app_workbench/pages/explore.py`

- [ ] **Step 1: Add the shape-read section to the layout**

In `app_workbench/pages/explore.py`, update the imports to add diagnostics and the evidence-note helper:
```python
from app_workbench.components import kpi_tile, evidence_note
from core.diagnostics import dispersion_pp, relationship_gradient, evidence_note as build_note
```

Append to the outer `layout` `html.Div([...])` children (after `pivot-container`):
```python
        html.H3("Shape read (hypothesis only — you assign the layer)"),
        html.Div(id="shape-read"),
```

- [ ] **Step 2: Add the shape-read callback**

Append to `app_workbench/pages/explore.py`:
```python
@callback(
    Output("shape-read", "children"),
    Input("corpus-selector", "value"),
    Input("pivot-eval", "value"),
)
def _render_shape_read(active_name: str, eval_name: str):
    if eval_name == "either":
        return html.Div("Select PHOSITA or Citation to read the failure shape.",
                        style={"color": "#888"})
    df = _load(active_name)
    disp = dispersion_pp(df, eval_name)
    grad = relationship_gradient(df, eval_name)
    return html.Div([
        evidence_note(build_note(disp, grad)),
        html.Div(
            f"Dispersion {disp:.0f}pp · gradient "
            + " → ".join(f"{r} {grad.rates[r]:.0%}" for r in grad.rates),
            style={"fontSize": "0.8rem", "color": "#555"},
        ),
    ])
```

- [ ] **Step 3: Boot and verify the shape read**

Run: `python -m app_workbench.app`
Expected: under the heatmap, a blue "HYPOTHESIS" block appears, e.g. for PHOSITA "...reasoning-correlated → Layer-2/3 signal; worst cluster: Novel." Switching eval to Citation shows the uniform/Layer-1 note. Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add app_workbench/pages/explore.py
git commit -m "feat(workbench): shape-read widget (hypothesis-only layer signal)"
```

---

### Task 7: `core/priority.py` — Frequency × Impact × Exposure scoring

**Files:**
- Create: `core/priority.py`
- Test: `tests/test_priority.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_priority.py`:
```python
import pandas as pd

from core.priority import frequency_tier, priority_table


def test_frequency_tier_boundaries():
    assert frequency_tier(0.83) == 3   # >=0.67
    assert frequency_tier(0.50) == 2   # 0.34-0.66
    assert frequency_tier(0.20) == 1   # <=0.33


def test_priority_table_scores_and_sorts():
    df = pd.DataFrame([
        # System x Novel: 2/2 FAIL on phosita -> tier 3
        {"claim_type": "System", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        {"claim_type": "System", "relationship": "Novel",
         "phosita_verdict": "FAIL", "citation_verdict": "PASS"},
        # Method x Anticipation: 0/3 FAIL on phosita -> tier 1
        {"claim_type": "Method", "relationship": "Anticipation",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
        {"claim_type": "Method", "relationship": "Anticipation",
         "phosita_verdict": "PASS", "citation_verdict": "PASS"},
    ])
    impact = {"Absent PHOSITA": "High", "Citation Text": "Low"}
    exposure = {("System", "Novel"): "Med", ("Method", "Anticipation"): "Med"}

    table = priority_table(df, impact_tiers=impact, exposure_tiers=exposure)

    top = table.iloc[0]
    assert top["failure_mode"] == "Absent PHOSITA"
    assert top["cell"] == "System × Novel"
    assert top["frequency_tier"] == 3
    assert top["impact_tier"] == 3       # High
    assert top["exposure_tier"] == 2     # Med
    assert top["score"] == 18            # 3*3*2
    # sorted descending: System×Novel (18) before Method×Anticipation (low)
    assert table["score"].is_monotonic_decreasing
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_priority.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.priority'`.

- [ ] **Step 3: Implement the module**

`core/priority.py`:
```python
"""Frequency × Impact × Exposure priority scoring (Notion Steps 1 / 1b).

Frequency is computed from the eval data. Impact and Exposure are PM-supplied
domain judgments (High/Med/Low) — the dashboard never invents them.
"""
from __future__ import annotations

import pandas as pd

TIER = {"High": 3, "Med": 2, "Low": 1}
MODE_VERDICT = {"Absent PHOSITA": "phosita_verdict", "Citation Text": "citation_verdict"}


def frequency_tier(fail_rate: float) -> int:
    """Heatmap tiering: >=67% -> 3, 34-66% -> 2, <=33% -> 1."""
    if fail_rate >= 0.67:
        return 3
    if fail_rate >= 0.34:
        return 2
    return 1


def priority_table(
    df: pd.DataFrame,
    impact_tiers: dict[str, str],
    exposure_tiers: dict[tuple[str, str], str],
) -> pd.DataFrame:
    """One row per (failure mode × claim_type × relationship) cell, scored & sorted.

    Columns: failure_mode, cell, claim_type, relationship, fail_rate, n,
    frequency_tier, impact_tier, exposure_tier, score.
    """
    rows = []
    for mode, col in MODE_VERDICT.items():
        scored = df[df[col].isin(["PASS", "FAIL"])].copy()
        scored = scored[(scored["claim_type"] != "Unknown")
                        & (scored["relationship"] != "Unknown")]
        scored["fail"] = scored[col] == "FAIL"
        for (ctype, rel), series in scored.groupby(["claim_type", "relationship"])["fail"]:
            fail_rate = float(series.mean())
            n = int(series.count())
            f_tier = frequency_tier(fail_rate)
            i_tier = TIER.get(impact_tiers.get(mode, "Med"), 2)
            e_tier = TIER.get(exposure_tiers.get((ctype, rel), "Med"), 2)
            rows.append({
                "failure_mode": mode,
                "cell": f"{ctype} × {rel}",
                "claim_type": ctype,
                "relationship": rel,
                "fail_rate": fail_rate,
                "n": n,
                "frequency_tier": f_tier,
                "impact_tier": i_tier,
                "exposure_tier": e_tier,
                "score": f_tier * i_tier * e_tier,
            })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.sort_values("score", ascending=False, ignore_index=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_priority.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add core/priority.py tests/test_priority.py
git commit -m "feat(workbench): Frequency x Impact x Exposure priority scoring"
```

---

### Task 8: Surface ② — Decision page (inputs + live priority table)

**Files:**
- Modify: `app_workbench/pages/decision.py`

- [ ] **Step 1: Build the Decision page with interactive inputs and a live table**

`app_workbench/pages/decision.py`:
```python
"""Surface 2 — Decision (Steps 1 + 1b + the decision)."""
from __future__ import annotations

from pathlib import Path

import dash
from dash import Input, Output, callback, dash_table, dcc, html

from app_workbench.components import assumed_badge
from core.priority import priority_table
from core.workbench_data import list_trace_sets, load_merged

dash.register_page(__name__, path="/decision", name="Decision")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"
ANNOTATIONS_PATH = TRACES_DIR / "traces_annotations.jsonl"
TIERS = [{"label": t, "value": t} for t in ("High", "Med", "Low")]


def _load(active_name: str):
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    ts = sets.get(active_name) or next(iter(sets.values()))
    return load_merged(ts, ANNOTATIONS_PATH)


CELLS = [(ct, rel) for ct in ("Method", "System")
         for rel in ("Anticipation", "Implicit", "Novel")]


def _impact_control(mode: str, default: str):
    return html.Div(
        [html.Label([f"Impact — {mode} ", assumed_badge()]),
         dcc.Dropdown(id={"type": "impact", "mode": mode}, options=TIERS,
                      value=default, clearable=False, style={"width": "160px"})],
    )


def _exposure_control(ctype: str, rel: str):
    return html.Div(
        [html.Label([f"{ctype} × {rel} ", assumed_badge()],
                    style={"fontSize": "0.75rem"}),
         dcc.Dropdown(id={"type": "exposure", "cell": f"{ctype} × {rel}"},
                      options=TIERS, value="Med", clearable=False,
                      style={"width": "140px"})],
    )


layout = html.Div(
    [
        html.Div(
            [html.Label("Active trace set:"),
             dcc.Dropdown(id="decision-corpus", value="live", clearable=False,
                          options=[{"label": s.name, "value": s.name}
                                   for s in list_trace_sets(TRACES_DIR)],
                          style={"width": "240px"})],
            style={"display": "flex", "gap": "0.6rem", "alignItems": "center"},
        ),
        html.H3("Step 1 — Impact per failure mode (domain judgment)"),
        html.Div(
            [_impact_control("Absent PHOSITA", "High"),
             _impact_control("Citation Text", "Low")],
            style={"display": "flex", "gap": "1.2rem"},
        ),
        html.H3(["Step 1b — Priority = Frequency × Impact × Exposure ", assumed_badge()]),
        html.P("Set Exposure per cell (production query mix) — every value is a "
               "placeholder until the live query distribution is instrumented.",
               style={"fontSize": "0.8rem", "color": "#555"}),
        html.Div([_exposure_control(ct, rel) for ct, rel in CELLS],
                 style={"display": "flex", "gap": "0.8rem", "flexWrap": "wrap"}),
        dash_table.DataTable(
            id="priority-table",
            columns=[
                {"name": "Failure mode", "id": "failure_mode"},
                {"name": "Cell", "id": "cell"},
                {"name": "FAIL%", "id": "fail_pct"},
                {"name": "n", "id": "n"},
                {"name": "Freq", "id": "frequency_tier"},
                {"name": "Impact", "id": "impact_tier"},
                {"name": "Exposure", "id": "exposure_tier"},
                {"name": "Score", "id": "score"},
            ],
            sort_action="native",
            style_data_conditional=[
                {"if": {"filter_query": "{score} >= 12"},
                 "backgroundColor": "#ffebee"},
            ],
        ),
    ]
)


@callback(
    Output("priority-table", "data"),
    Input("decision-corpus", "value"),
    Input({"type": "impact", "mode": dash.ALL}, "value"),
    Input({"type": "impact", "mode": dash.ALL}, "id"),
    Input({"type": "exposure", "cell": dash.ALL}, "value"),
    Input({"type": "exposure", "cell": dash.ALL}, "id"),
)
def _render_priority(active_name, impact_values, impact_ids, exp_values, exp_ids):
    df = _load(active_name)
    impact = {i["mode"]: v for i, v in zip(impact_ids, impact_values)}
    exposure: dict[tuple[str, str], str] = {}
    for i, v in zip(exp_ids, exp_values):
        ct, rel = i["cell"].split(" × ")
        exposure[(ct, rel)] = v
    table = priority_table(df, impact_tiers=impact, exposure_tiers=exposure)
    if table.empty:
        return []
    table["fail_pct"] = (table["fail_rate"] * 100).round(0).astype(int)
    return table[["failure_mode", "cell", "fail_pct", "n", "frequency_tier",
                  "impact_tier", "exposure_tier", "score"]].to_dict("records")
```

- [ ] **Step 2: Boot and verify the Decision page**

Run: `python -m app_workbench.app`
Expected: the Decision page shows two Impact dropdowns (each with a ⚠ assumed badge), and a priority table sorted by Score. Changing "Absent PHOSITA" Impact from High→Low drops its rows' scores and re-sorts; editing an Exposure cell recomputes that row's Score. High-score rows shade pink. Stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add app_workbench/pages/decision.py
git commit -m "feat(workbench): Decision page — interactive Freq x Impact x Exposure table"
```

---

### Task 9: Surface ② — layer assignment + decision rationale

**Files:**
- Modify: `app_workbench/pages/decision.py`

- [ ] **Step 1: Add per-mode layer pick + decision rationale to the layout**

In `app_workbench/pages/decision.py`, append to the `layout` children (after the `priority-table` DataTable):
```python
        html.H3("Step 2 — Assign the architecture layer (you decide)"),
        html.Div(
            [
                html.Div([
                    html.Label(f"{mode} → layer"),
                    dcc.RadioItems(
                        id={"type": "layer", "mode": mode},
                        options=[{"label": l, "value": l}
                                 for l in ("L1", "L2", "L3")],
                        inline=True,
                    ),
                ]) for mode in ("Absent PHOSITA", "Citation Text")
            ],
            style={"display": "flex", "gap": "2rem"},
        ),
        html.H3("Decision — why we fix in this order (your rationale)"),
        dcc.Textarea(
            id="decision-rationale",
            placeholder="e.g. Citation is uniform → L1 verbatim instruction, "
                        "nearly free, do first; PHOSITA Novel cluster likely L3, "
                        "gate behind the prompt fix and re-measure.",
            style={"width": "100%", "height": "120px"},
        ),
        html.Div(id="decision-saved-flag", style={"color": "#2e7d32"}),
```

> **Note:** persistence of these inputs is wired in Task 12 (`workbench_state`). For now they render and hold value within a session.

- [ ] **Step 2: Boot and verify**

Run: `python -m app_workbench.app`
Expected: layer radios for both modes and a rationale textarea render below the priority table; values are editable. Stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add app_workbench/pages/decision.py
git commit -m "feat(workbench): Decision page — PM layer assignment + rationale capture"
```

> **Phase 2 complete:** the full how-bad → where → why → what-to-fix arc is computed and PM-driven.

---

# Phase 3 — Interactivity & persistence

### Task 10: `core/workbench_state.py` — JSON persistence

**Files:**
- Create: `core/workbench_state.py`
- Test: `tests/test_workbench_state.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_workbench_state.py`:
```python
from pathlib import Path

from core.workbench_state import load_state, save_state


def test_load_state_missing_returns_default(tmp_path: Path):
    assert load_state(tmp_path, "priority_inputs") == {}


def test_save_then_load_round_trips(tmp_path: Path):
    data = {"impact": {"Absent PHOSITA": "High"}, "layers": {"Citation Text": "L1"}}
    save_state(tmp_path, "priority_inputs", data)
    assert load_state(tmp_path, "priority_inputs") == data


def test_save_creates_dir_if_absent(tmp_path: Path):
    target = tmp_path / "nested" / "state"
    save_state(target, "layout", {"a": 1})
    assert (target / "layout.json").exists()
    assert load_state(target, "layout") == {"a": 1}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_workbench_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.workbench_state'`.

- [ ] **Step 3: Implement the module**

`core/workbench_state.py`:
```python
"""File-based JSON persistence for the Eval Workbench (single-user).

State files live under a state dir: layout.json, annotations.json,
priority_inputs.json. Each holds one JSON object; missing files read as {}.
"""
from __future__ import annotations

import json
from pathlib import Path

VALID_NAMES = {"layout", "annotations", "priority_inputs"}


def _path(state_dir: Path, name: str) -> Path:
    if name not in VALID_NAMES:
        raise ValueError(f"unknown state name: {name!r} (expected one of {VALID_NAMES})")
    return Path(state_dir) / f"{name}.json"


def load_state(state_dir: Path, name: str) -> dict:
    path = _path(state_dir, name)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state_dir: Path, name: str, data: dict) -> None:
    path = _path(state_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_workbench_state.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add core/workbench_state.py tests/test_workbench_state.py
git commit -m "feat(workbench): file-based JSON persistence (core.workbench_state)"
```

---

### Task 11: Persist Decision inputs (impact, exposure, layers, rationale)

**Files:**
- Modify: `app_workbench/pages/decision.py`

- [ ] **Step 1: Add the state dir constant and a save callback**

In `app_workbench/pages/decision.py`, add to the imports:
```python
from core.workbench_state import load_state, save_state
```

Add near the other module constants:
```python
STATE_DIR = TRACES_DIR / "workbench_state"
```

Append this callback at the end of the file:
```python
@callback(
    Output("decision-saved-flag", "children"),
    Input({"type": "impact", "mode": dash.ALL}, "value"),
    Input({"type": "impact", "mode": dash.ALL}, "id"),
    Input({"type": "exposure", "cell": dash.ALL}, "value"),
    Input({"type": "exposure", "cell": dash.ALL}, "id"),
    Input({"type": "layer", "mode": dash.ALL}, "value"),
    Input({"type": "layer", "mode": dash.ALL}, "id"),
    Input("decision-rationale", "value"),
    prevent_initial_call=True,
)
def _save_decision(impact_values, impact_ids, exp_values, exp_ids,
                   layer_values, layer_ids, rationale):
    data = {
        "impact": {i["mode"]: v for i, v in zip(impact_ids, impact_values)},
        "exposure": {i["cell"]: v for i, v in zip(exp_ids, exp_values)},
        "layers": {i["mode"]: v for i, v in zip(layer_ids, layer_values)},
        "rationale": rationale or "",
    }
    save_state(STATE_DIR, "priority_inputs", data)
    return "Saved ✓"
```

- [ ] **Step 2: Hydrate saved values on page load**

In `app_workbench/pages/decision.py`, replace the `_impact_control` default and the layer radios' initial values by reading saved state. Update `_impact_control` to:
```python
def _impact_control(mode: str, default: str):
    saved = load_state(STATE_DIR, "priority_inputs").get("impact", {})
    return html.Div(
        [html.Label([f"Impact — {mode} ", assumed_badge()]),
         dcc.Dropdown(id={"type": "impact", "mode": mode}, options=TIERS,
                      value=saved.get(mode, default), clearable=False,
                      style={"width": "160px"})],
    )
```

Also hydrate the per-cell exposure controls — update `_exposure_control`:
```python
def _exposure_control(ctype: str, rel: str):
    saved = load_state(STATE_DIR, "priority_inputs").get("exposure", {})
    return html.Div(
        [html.Label([f"{ctype} × {rel} ", assumed_badge()],
                    style={"fontSize": "0.75rem"}),
         dcc.Dropdown(id={"type": "exposure", "cell": f"{ctype} × {rel}"},
                      options=TIERS, value=saved.get(f"{ctype} × {rel}", "Med"),
                      clearable=False, style={"width": "140px"})],
    )
```

And in the layer `dcc.RadioItems`, set the initial value from saved state by changing that list comprehension block to:
```python
                html.Div([
                    html.Label(f"{mode} → layer"),
                    dcc.RadioItems(
                        id={"type": "layer", "mode": mode},
                        options=[{"label": l, "value": l} for l in ("L1", "L2", "L3")],
                        value=load_state(STATE_DIR, "priority_inputs")
                              .get("layers", {}).get(mode),
                        inline=True,
                    ),
                ]) for mode in ("Absent PHOSITA", "Citation Text")
```

Also set the rationale textarea initial value: change the `dcc.Textarea(...)` to include
```python
            value=load_state(STATE_DIR, "priority_inputs").get("rationale", ""),
```

- [ ] **Step 3: Boot and verify persistence**

Run: `python -m app_workbench.app`
Set Impact, a layer, and type a rationale; confirm "Saved ✓" appears. Stop the app, restart it, reopen Decision.
Expected: the impact tier, layer pick, and rationale text are restored. A `traces/workbench_state/priority_inputs.json` file exists.

- [ ] **Step 4: Ignore the state dir in git**

Append to `.gitignore`:
```
traces/workbench_state/
.dash_cache/
```

- [ ] **Step 5: Commit**

```bash
git add app_workbench/pages/decision.py .gitignore
git commit -m "feat(workbench): persist Decision inputs (impact, exposure, layer, rationale)"
```

---

### Task 12: Draggable/resizable layout on the Explore page

**Files:**
- Modify: `app_workbench/pages/explore.py`

- [ ] **Step 1: Wrap the Explore widgets in a dash-draggable grid**

In `app_workbench/pages/explore.py`, add the import:
```python
import dash_draggable
```

Replace the `layout = html.Div([...])` assignment so the four widget blocks (KPI section, pivot section, shape-read section) are children of a `ResponsiveGridLayout`. Keep the corpus selector outside the grid (it is global). Concretely, set:
```python
layout = html.Div([
    html.Div(
        [
            html.Label("Active trace set:"),
            dcc.Dropdown(id="corpus-selector", options=_trace_set_options(),
                         value="live", clearable=False, style={"width": "240px"}),
        ],
        style={"display": "flex", "gap": "0.6rem", "alignItems": "center"},
    ),
    dash_draggable.ResponsiveGridLayout(
        id="explore-grid",
        children=[
            html.Div([html.H3("How bad is it?"),
                      html.Div(id="kpi-row",
                               style={"display": "flex", "gap": "0.8rem",
                                      "flexWrap": "wrap"})],
                     id="w-kpis"),
            html.Div([html.H3("Where does it fail? (drag dims onto Rows/Cols/Filters)"),
                      dcc.RadioItems(id="pivot-eval",
                                     options=[{"label": "PHOSITA", "value": "phosita"},
                                              {"label": "Citation", "value": "citation"},
                                              {"label": "Either", "value": "either"}],
                                     value="phosita", inline=True),
                      html.Div(id="pivot-container")],
                     id="w-pivot"),
            html.Div([html.H3("Shape read (hypothesis only — you assign the layer)"),
                      html.Div(id="shape-read")],
                     id="w-shape"),
        ],
    ),
])
```

> **Note:** `dash_draggable.ResponsiveGridLayout` makes each top-level child draggable and resizable by default. The existing `kpi-row`, `pivot-container`, and `shape-read` callbacks are unchanged — only their wrappers moved into the grid.

- [ ] **Step 2: Persist the grid layout**

Append to `app_workbench/pages/explore.py`:
```python
from core.workbench_state import load_state, save_state

STATE_DIR = TRACES_DIR / "workbench_state"


@callback(
    Output("explore-grid", "layouts"),
    Input("corpus-selector", "value"),  # fires on initial load
)
def _restore_layout(_):
    saved = load_state(STATE_DIR, "layout")
    return saved or dash.no_update


@callback(
    Output("w-kpis", "id"),  # dummy output; we only need the side effect
    Input("explore-grid", "layouts"),
    prevent_initial_call=True,
)
def _save_layout(layouts):
    if layouts:
        save_state(STATE_DIR, "layout", layouts)
    return "w-kpis"
```

- [ ] **Step 3: Boot and verify drag + persistence**

Run: `python -m app_workbench.app`
Drag the "Where does it fail?" widget above the KPIs and resize it. Restart the app.
Expected: widgets are draggable/resizable; the rearranged layout is restored after restart (a `traces/workbench_state/layout.json` exists). Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add app_workbench/pages/explore.py
git commit -m "feat(workbench): draggable/resizable Explore grid with persisted layout"
```

---

### Task 13: `core/eval_runner.py` — run evals as a subprocess

**Files:**
- Create: `core/eval_runner.py`
- Test: `tests/test_eval_runner.py`

- [ ] **Step 1: Write the failing test (command construction only — no real LLM calls)**

`tests/test_eval_runner.py`:
```python
from pathlib import Path

from core.eval_runner import build_eval_commands
from core.workbench_data import TraceSet


def test_build_eval_commands_targets_the_selected_set():
    ts = TraceSet(
        name="exp1",
        traces_path=Path("traces/traces.exp1.jsonl"),
        phosita_path=Path("traces/phosita_eval_full.exp1.jsonl"),
        citation_path=Path("traces/citation_text_eval_full.exp1.jsonl"),
    )
    cmds = build_eval_commands(ts)

    assert len(cmds) == 2
    citation_cmd, phosita_cmd = cmds[0], cmds[1]
    assert "run_citation_eval.py" in " ".join(citation_cmd)
    assert "run_phosita_eval.py" in " ".join(phosita_cmd)
    # each command points --traces / --out at the selected set's files
    assert str(ts.traces_path) in citation_cmd
    assert str(ts.citation_path) in citation_cmd
    assert str(ts.phosita_path) in phosita_cmd
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_eval_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.eval_runner'`.

- [ ] **Step 3: Implement the module**

`core/eval_runner.py`:
```python
"""Run the existing eval scripts on a selected trace set, as a subprocess.

This does NOT modify the evals (the ruler). It only invokes the same CLI an
operator would run by hand, pointing --traces/--out at the chosen set. Intended
to be called from a Dash background callback.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.workbench_data import TraceSet

REPO_ROOT = Path(__file__).resolve().parents[1]
CITATION_SCRIPT = REPO_ROOT / "scripts" / "run_citation_eval.py"
PHOSITA_SCRIPT = REPO_ROOT / "scripts" / "run_phosita_eval.py"


def build_eval_commands(trace_set: TraceSet) -> list[list[str]]:
    """Return [citation_cmd, phosita_cmd] for the selected set (citation first — cheaper)."""
    py = sys.executable
    return [
        [py, str(CITATION_SCRIPT),
         "--traces", str(trace_set.traces_path),
         "--out", str(trace_set.citation_path)],
        [py, str(PHOSITA_SCRIPT),
         "--traces", str(trace_set.traces_path),
         "--out", str(trace_set.phosita_path)],
    ]


def run_evals(trace_set: TraceSet, set_status=None) -> str:
    """Run both evals sequentially; stream a short status via set_status(str).

    Returns a final summary string. Re-running is safe — the scripts are
    idempotent-cached. Raises CalledProcessError if a script exits non-zero.
    """
    log_lines: list[str] = []
    for label, cmd in zip(("Citation", "PHOSITA"), build_eval_commands(trace_set)):
        if set_status:
            set_status(f"Running {label} eval on '{trace_set.name}'…")
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                              text=True, check=True)
        tail = (proc.stdout or "").strip().splitlines()[-3:]
        log_lines.append(f"[{label}] " + " | ".join(tail))
    return "\n".join(log_lines)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_eval_runner.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add core/eval_runner.py tests/test_eval_runner.py
git commit -m "feat(workbench): eval_runner — invoke eval scripts on a selected set"
```

---

### Task 14: Wire the "Run eval" background callback into Explore

**Files:**
- Modify: `app_workbench/pages/explore.py`

- [ ] **Step 1: Add the Run-eval button + status output to the corpus bar**

In `app_workbench/pages/explore.py`, inside the corpus-selector `html.Div([...])` (the global one outside the grid), add after the dropdown:
```python
            html.Button("Run eval", id="run-eval-btn", n_clicks=0),
            html.Span(id="run-eval-status", style={"fontSize": "0.8rem", "color": "#555"}),
```

- [ ] **Step 2: Add the background callback**

Append to `app_workbench/pages/explore.py`:
```python
from core.eval_runner import run_evals


@callback(
    Output("run-eval-status", "children"),
    Input("run-eval-btn", "n_clicks"),
    dash.State("corpus-selector", "value"),
    background=True,
    running=[(Output("run-eval-btn", "disabled"), True, False)],
    prevent_initial_call=True,
)
def _run_eval(_n, active_name):
    sets = {s.name: s for s in list_trace_sets(TRACES_DIR)}
    ts = sets.get(active_name)
    if ts is None:
        return "No such trace set."
    try:
        summary = run_evals(ts)
    except Exception as exc:  # surface failures to the PM, don't crash the app
        return f"Eval failed: {exc}"
    return f"Done. {summary}"
```

> **Note:** `background=True` uses the DiskCache manager configured in `app.py`, so a multi-minute eval run does not block the UI; `running=[...]` disables the button while a job is in flight (prevents double-runs).

- [ ] **Step 3: Boot and verify (use a tiny/cached set to keep it fast)**

Run: `python -m app_workbench.app`
Select the `live` set, click "Run eval".
Expected: the button disables, the status shows "Running …", and on completion shows "Done. [Citation] … | [PHOSITA] …". Because the scripts are idempotent-cached, a re-run on an unchanged set returns quickly. The KPIs reflect the (re)written eval files after switching the corpus dropdown away and back. Stop with Ctrl+C.

> **If `GROQ_API_KEY` is absent**, the PHOSITA run will error; the status shows "Eval failed: …" rather than crashing — that is the expected guarded behavior.

- [ ] **Step 4: Commit**

```bash
git add app_workbench/pages/explore.py
git commit -m "feat(workbench): Run-eval background job button with status + lockout"
```

---

### Task 15: Run docs + full test sweep

**Files:**
- Create: `app_workbench/README.md`

- [ ] **Step 1: Write the run instructions**

`app_workbench/README.md`:
```markdown
# Eval Workbench (Dash)

Interactive eval workbench: how-bad → where → why-layer → what-to-fix-first.

## Run

    pip install -r requirements.txt
    python -m app_workbench.app

Open http://127.0.0.1:8050.

## Surfaces
- **Explore** — corpus selector, Run-eval, KPI tiles, drag-drop pivot heatmap, shape-read hypothesis. Widgets are draggable/resizable; layout persists.
- **Decision** — Impact (per mode) + Exposure (per cell) inputs → live Frequency × Impact × Exposure priority table; PM assigns the architecture layer and records the decision rationale.

## Principle
The app guides; the PM decides. Every derived insight shows a templated
HYPOTHESIS plus the number behind it. Final layer / priority / decision are PM
inputs, persisted under `traces/workbench_state/` (git-ignored).

## Notes
- Reads existing eval sets only; does not generate traces.
- "Run eval" re-runs the existing scripts on the selected set (needs `GROQ_API_KEY` for PHOSITA).
- The eval/judge logic (the measurement ruler) is never modified by this app.
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/test_workbench_data.py tests/test_diagnostics.py tests/test_priority.py tests/test_workbench_state.py tests/test_eval_runner.py -v`
Expected: all tests pass (3 + 5 + 2 + 3 + 1 = 14 passed).

- [ ] **Step 3: Commit**

```bash
git add app_workbench/README.md
git commit -m "docs(workbench): run instructions + full test sweep green"
```

---

## Self-review notes

- **Spec coverage:** Architecture (Tasks 0,1,10,13) · Surface ① corpus/KPI/pivot/shape (Tasks 3,4,6) · Surface ② inputs/priority/layer/rationale (Tasks 8,9) · guides-not-decides evidence-notes (Tasks 2,5,6) · persistence (Tasks 10,11,12) · run-eval (Tasks 13,14) · out-of-scope respected (no ingest/generate; ruler untouched). Every spec section maps to a task.
- **Ruler integrity:** No task edits `core/phosita_eval.py`, `core/citation_eval.py`, or any judge prompt. `eval_runner` only invokes existing scripts.
- **Type consistency:** `TraceSet(name, traces_path, phosita_path, citation_path)` used identically in Tasks 1/13/14. `load_merged(trace_set, annotations_path)` signature consistent across pages. `priority_table(df, impact_tiers, exposure_tiers)` columns (`failure_mode`, `cell`, `score`, `frequency_tier`, `impact_tier`, `exposure_tier`) consistent between Task 7 and Task 8. `evidence_note(dispersion, gradient)` / `RelationshipGradient(rates, monotonic_increasing, worst_relationship)` consistent between Tasks 5 and 6. `load_state/save_state(state_dir, name, [data])` consistent across Tasks 10/11/12.
- **Phasing:** each phase ends in a runnable app; Phase 1 alone reaches read-only parity, Phase 2 adds the decision arc, Phase 3 adds interactivity/persistence/run.
- **TDD:** all five `core/` modules are test-first; Dash page wiring is verified by explicit boot-and-observe steps (UI callbacks aren't unit-tested, consistent with the repo's existing Streamlit approach).
```
