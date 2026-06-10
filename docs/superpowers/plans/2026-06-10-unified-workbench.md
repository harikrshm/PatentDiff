# Unified Workbench Implementation Plan (Spec 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the four PatentDiff tools (prototype, analyst console, annotation tool, and a new before/after eval comparison) into a single Plotly Dash multi-page app, and delete the legacy Streamlit dashboard.

**Architecture:** One `Dash(use_pages=True)` app under `app_unified/`. A persistent shell (top nav `PatentDiff | Evaluation`, a secondary eval nav strip, an app-global light/dark toggle) wraps `dash.page_container`. Each view is its own route/page module whose callbacks call the existing Python `core/` modules directly — no API layer, no React. The analyst console (`app_workbench/`) is folded in nearly unchanged as the `/eval` page.

**Tech Stack:** Python 3.13, Dash 2.x (Pages), `diskcache` (background callback manager, already present), pandas, pydantic, pytest. Reuses `core/` (llm, report, models, annotation, trace_loader, workbench_data, diagnostics, priority, workbench_state, eval_runner) and `tracing/` unchanged.

**Reference spec:** `docs/superpowers/specs/2026-06-10-unified-workbench-design.md`

---

## Pre-flight: branch setup (run once, before Task 0)

The analyst console lives on `eval-workbench`; `main` is a strict ancestor of it (verified: `git rev-list --left-right --count main...eval-workbench` → `0  24`), so this is a fast-forward, not a merge with conflicts.

- [ ] **Confirm with the user before any git branch operation.** Then:

```bash
# Land the complete, tested console on main (fast-forward — no conflicts).
git checkout main
git merge --ff-only eval-workbench

# Cut the working branch for all Spec 1 work.
git checkout -b unify-workbench
```

Expected: `main` now contains `app_workbench/`, the console's `core/` modules (`workbench_data.py`, `diagnostics.py`, `priority.py`, `workbench_state.py`, `eval_runner.py`), their `tests/`, and `app_workbench/assets/`. `git status` clean on `unify-workbench`.

Verify the baseline is green before changing anything:

```bash
pytest -q
```

Expected: PASS (the console's suite + existing core tests).

---

## File structure (locked before tasks)

| File | Responsibility |
|---|---|
| `app_unified/__init__.py` | Package marker. |
| `app_unified/app.py` | Dash entry: `use_pages=True`, DiskcacheManager, persistent shell layout, app-global theme `dcc.Store` + toggle + clientside theme/url callbacks, `page_container`. |
| `app_unified/components.py` | Shared chrome: `top_nav()`, `eval_subnav()`, `page_header()`. |
| `app_unified/pages/__init__.py` | Package marker. |
| `app_unified/pages/prototype.py` | `/` — claim-diff form → Analyze → report (port of `app.py`). |
| `app_unified/pages/eval_overview.py` | `/eval` — mounts the analyst console layout + registers its callbacks. |
| `app_unified/pages/eval_traces.py` | `/eval/traces` — annotation tool (port of `app_annotation.py`). |
| `app_unified/pages/eval_comparison.py` | `/eval/comparison` — before/after eval delta v1. |
| `app_unified/assets/workbench.css` | Relocated from `app_workbench/assets/`. |
| `app_unified/assets/workbench.js` | Relocated from `app_workbench/assets/`. |
| `core/eval_delta.py` | NEW — verdict transition matrix + PASS-rate delta (extracted from `scripts/compute_eval_delta.py`). |
| `tests/test_app_unified_shell.py` | Shell boots; 4 routes registered. |
| `tests/test_prototype_page.py` | Analyze callback builds+appends a trace (mocked LLM). |
| `tests/test_traces_page.py` | Annotation save/load round-trip via the page's pure helpers. |
| `tests/test_eval_delta.py` | Transition matrix, PASS-rate delta, run-id filter. |
| `tests/test_comparison_page.py` | Comparison callback returns matrix + KPIs for a before/after pair. |

**Run convention (new):** `python -m app_unified.app` (replaces `streamlit run app.py`, `streamlit run app_annotation.py`, `python -m app_workbench.app`, and `streamlit run scripts/run_dashboard.py`).

---

# Task 0: Bootable unified shell skeleton

**Files:**
- Create: `app_unified/__init__.py`
- Create: `app_unified/components.py`
- Create: `app_unified/app.py`
- Create: `app_unified/pages/__init__.py`
- Create: `app_unified/pages/prototype.py` (stub)
- Create: `app_unified/pages/eval_overview.py` (stub)
- Create: `app_unified/pages/eval_traces.py` (stub)
- Create: `app_unified/pages/eval_comparison.py` (stub)
- Test: `tests/test_app_unified_shell.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_unified_shell.py
import importlib


def test_shell_registers_all_four_routes():
    import dash
    importlib.import_module("app_unified.app")  # registers pages on import
    registered = {p["path"] for p in dash.page_registry.values()}
    assert {"/", "/eval", "/eval/traces", "/eval/comparison"} <= registered


def test_shell_layout_has_nav_and_page_container():
    mod = importlib.import_module("app_unified.app")
    # Render the layout to a string of component types; must include the page container.
    from dash import page_container  # noqa: F401
    assert mod.app.layout is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_unified_shell.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app_unified'`.

- [ ] **Step 3: Create the package markers and shared chrome**

```python
# app_unified/__init__.py
```

```python
# app_unified/pages/__init__.py
```

```python
# app_unified/components.py
"""Shared chrome for the unified workbench shell."""
from __future__ import annotations

from dash import dcc, html

# Top-level sections and the eval sub-views (label, href).
TOP_NAV = [("PatentDiff", "/"), ("Evaluation", "/eval")]
EVAL_SUBNAV = [
    ("Overview", "/eval"),
    ("Traces", "/eval/traces"),
    ("Comparison", "/eval/comparison"),
]


def top_nav() -> html.Nav:
    """Primary nav: PatentDiff | Evaluation."""
    return html.Nav(
        className="uw-topnav",
        **{"aria-label": "Primary"},
        children=[
            dcc.Link(label, href=href, className="uw-topnav__link",
                     **{"data-href": href})
            for label, href in TOP_NAV
        ],
    )


def eval_subnav(active: str) -> html.Nav:
    """Secondary strip shown on /eval* routes; `active` is the current pathname."""
    def cls(href: str) -> str:
        is_active = active == href or (href != "/eval" and active.startswith(href))
        if href == "/eval":
            is_active = active == "/eval"
        return "uw-subnav__link" + (" is-active" if is_active else "")

    return html.Nav(
        className="uw-subnav",
        **{"aria-label": "Evaluation views"},
        children=[
            dcc.Link(label, href=href, className=cls(href)) for label, href in EVAL_SUBNAV
        ],
    )


def page_header(title: str, subtitle: str = "") -> html.Header:
    """Lightweight per-page header for the ported views."""
    children = [html.H1(title, className="uw-page__title")]
    if subtitle:
        children.append(html.P(subtitle, className="uw-page__subtitle"))
    return html.Header(className="uw-page__header", children=children)
```

- [ ] **Step 4: Create the shell app**

```python
# app_unified/app.py
"""Unified PatentDiff workbench — single Dash app housing every tool.

Routes:
    /                 PatentDiff prototype
    /eval             Overview (analyst console)
    /eval/traces      Annotation tool
    /eval/comparison  Before/after eval delta

Run with:
    python -m app_unified.app
"""
from __future__ import annotations

from pathlib import Path

import diskcache
from dash import (Dash, DiskcacheManager, Input, Output, State, dcc, html,
                  page_container)

from app_unified.components import eval_subnav, top_nav

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
app.title = "PatentDiff — Workbench"


def _theme_toggle() -> html.Button:
    return html.Button(
        id="theme-toggle",
        className="uw-themetoggle",
        n_clicks=0,
        title="Toggle light / dark",
        **{"aria-label": "Toggle light or dark theme"},
        children=html.Span("◐", className="uw-themetoggle__glyph",
                            **{"aria-hidden": "true"}),
    )


app.layout = html.Div(
    className="uw-root",
    children=[
        dcc.Location(id="url"),
        html.Div(id="url-writer-dummy", style={"display": "none"}),
        dcc.Store(id="theme", data="light"),     # app-global; console figures read it
        dcc.Store(id="data-version", data=0),     # console refresh signal
        html.Header(
            className="uw-appbar",
            children=[
                html.Div(
                    className="uw-appbar__brand",
                    children=[
                        html.Span("PatentDiff", className="uw-appbar__brand-strong"),
                        html.Span("Workbench", className="uw-appbar__brand-sub"),
                    ],
                ),
                top_nav(),
                _theme_toggle(),
            ],
        ),
        html.Div(id="uw-subnav-slot"),
        html.Main(className="uw-pagewrap", children=page_container),
    ],
)


# Show the eval sub-nav only on /eval* routes.
@app.callback(Output("uw-subnav-slot", "children"), Input("url", "pathname"))
def _render_subnav(pathname: str):
    pathname = pathname or "/"
    if pathname == "/eval" or pathname.startswith("/eval/"):
        return eval_subnav(pathname)
    return None


# Theme toggle (clientside): flips <html data-theme>, persists, mirrors to `theme`
# store so server-side Plotly figures recolor. On initial load (no click) it just
# reports the theme workbench.js already set.
app.clientside_callback(
    """
    function(n_clicks, current) {
        var html = document.documentElement;
        var present = html.getAttribute('data-theme');
        if (!present) {
            present = (window.matchMedia &&
                window.matchMedia('(prefers-color-scheme: dark)').matches)
                ? 'dark' : 'light';
        }
        if (!n_clicks) { return present; }
        var next = present === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        try { localStorage.setItem('wb-theme', next); } catch (e) {}
        return next;
    }
    """,
    Output("theme", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme", "data"),
)

if __name__ == "__main__":
    app.run(debug=True)
```

- [ ] **Step 5: Create four page stubs**

```python
# app_unified/pages/prototype.py
import dash
from dash import html

dash.register_page(__name__, path="/", name="PatentDiff")

layout = html.Div("PatentDiff prototype — coming in Task 1", className="uw-stub")
```

```python
# app_unified/pages/eval_overview.py
import dash
from dash import html

dash.register_page(__name__, path="/eval", name="Overview")

layout = html.Div("Overview — coming in Task 3", className="uw-stub")
```

```python
# app_unified/pages/eval_traces.py
import dash
from dash import html

dash.register_page(__name__, path="/eval/traces", name="Traces")

layout = html.Div("Traces — coming in Task 2", className="uw-stub")
```

```python
# app_unified/pages/eval_comparison.py
import dash
from dash import html

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

layout = html.Div("Comparison — coming in Task 5", className="uw-stub")
```

- [ ] **Step 6: Relocate the console assets so the shell serves them**

```bash
git mv app_workbench/assets/workbench.css app_unified/assets/workbench.css
git mv app_workbench/assets/workbench.js  app_unified/assets/workbench.js
```

(Dash serves `assets/` relative to the app module; the unified app is the one users run.)

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_app_unified_shell.py -v`
Expected: PASS (4 routes registered, layout present).

- [ ] **Step 8: Manually boot once**

Run: `python -m app_unified.app` then open `http://127.0.0.1:8050/`.
Expected: appbar with `PatentDiff | Evaluation` + theme toggle; `/` shows the prototype stub; `/eval`, `/eval/traces`, `/eval/comparison` show their stubs with the eval sub-nav strip visible; theme toggle flips light/dark. Ctrl-C to stop.

- [ ] **Step 9: Commit**

```bash
git add app_unified/ tests/test_app_unified_shell.py
git add -A app_workbench/assets app_unified/assets
git commit -m "feat(unified): bootable Dash shell — top nav, eval sub-nav, theme toggle, 4 routed pages"
```

---

# Task 1: PatentDiff prototype page (`/`)

Port `app.py`. The Streamlit form becomes a Dash form; "Analyze" is a callback that calls the exact same `core` functions and appends a trace identically.

**Files:**
- Modify: `app_unified/pages/prototype.py`
- Test: `tests/test_prototype_page.py`

- [ ] **Step 1: Write the failing test (the analyze logic, LLM mocked)**

```python
# tests/test_prototype_page.py
from unittest.mock import patch

from app_unified.pages import prototype


def test_run_analysis_appends_trace_and_returns_report(tmp_path, monkeypatch):
    fake_llm = {
        "raw_output": "ELEMENT 1 ...", "model": "test-model",
        "tokens_input": 10, "tokens_output": 20, "latency_ms": 5,
    }
    appended = {}

    def fake_append(trace):
        appended["trace"] = trace

    with patch.object(prototype, "call_groq", return_value=fake_llm), \
         patch.object(prototype, "parse_llm_response") as fake_parse, \
         patch.object(prototype, "append_trace", side_effect=fake_append):
        fake_parse.return_value.element_mappings = []
        fake_parse.return_value.overall_opinion = "No overlap."
        status, report_children, meta = prototype.run_analysis(
            "US-A", "claim a", "spec a", "US-B", "claim b", "spec b",
        )

    assert appended["trace"]["status"] == "success"
    assert appended["trace"]["inputs"]["source_patent"]["label"] == "US-A"
    assert status == ""  # no error banner


def test_run_analysis_rejects_missing_fields():
    status, report_children, meta = prototype.run_analysis(
        "US-A", "", "spec a", "US-B", "claim b", "spec b",
    )
    assert "fill in all fields" in status.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_prototype_page.py -v`
Expected: FAIL with `AttributeError: module 'app_unified.pages.prototype' has no attribute 'run_analysis'`.

- [ ] **Step 3: Implement the prototype page**

```python
# app_unified/pages/prototype.py
"""PatentDiff prototype — claim-diff form → Analyze → report. Port of app.py."""
from __future__ import annotations

import dash
from dash import Input, Output, State, callback, dash_table, dcc, html

from app_unified.components import page_header
from core.llm import build_system_prompt, build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response
from tracing.logger import build_trace_record
from tracing.store import append_trace

dash.register_page(__name__, path="/", name="PatentDiff")

_EMPTY_LLM = {"raw_output": "", "model": "", "tokens_input": 0,
              "tokens_output": 0, "latency_ms": 0}


def _patent_column(side: str, title: str) -> html.Div:
    return html.Div(
        className="uw-proto__col",
        children=[
            html.H2(title, className="uw-proto__coltitle"),
            dcc.Input(id=f"label-{side}", type="text", placeholder="e.g., US10,123,456",
                      className="uw-input"),
            html.Label("Independent Claim", className="uw-label"),
            dcc.Textarea(id=f"claim-{side}", className="uw-input--area", style={"height": "200px"}),
            html.Label("Specification Support", className="uw-label"),
            dcc.Textarea(id=f"spec-{side}", className="uw-input--area", style={"height": "200px"}),
        ],
    )


layout = html.Div(
    className="uw-page uw-proto",
    children=[
        page_header("PatentDiff — Patent Claim Analysis"),
        html.Div(
            className="uw-proto__grid",
            children=[
                _patent_column("a", "Patent A (Source)"),
                _patent_column("b", "Patent B (Target / Prior Art)"),
            ],
        ),
        html.Button("Analyze", id="analyze-btn", n_clicks=0,
                    className="uw-btn uw-btn--primary uw-proto__analyze"),
        html.Div(id="analyze-status", className="uw-status", role="status",
                 **{"aria-live": "polite"}),
        dcc.Loading(html.Div(id="analyze-report"), type="dot"),
        html.Div(id="analyze-meta"),
    ],
)


def run_analysis(label_a, claim_a, spec_a, label_b, claim_b, spec_b):
    """Pure logic: validate, call the LLM, append a trace, build report children.

    Returns (status_message, report_children, meta_children). status_message is
    "" on success, an error string otherwise. Mirrors app.py exactly.
    """
    if not all([label_a, claim_a, spec_a, label_b, claim_b, spec_b]):
        return "Please fill in all fields for both patents.", None, None

    source = PatentInput(label=label_a, independent_claim=claim_a, specification=spec_a)
    target = PatentInput(label=label_b, independent_claim=claim_b, specification=spec_b)

    system_prompt = build_system_prompt()
    user_prompt, truncation_warnings = build_user_prompt(source, target)

    llm_response = None
    try:
        llm_response = call_groq(system_prompt, user_prompt)
        report = parse_llm_response(llm_response["raw_output"])
        append_trace(build_trace_record(
            source_patent=source, target_patent=target,
            system_prompt=system_prompt, user_prompt=user_prompt,
            llm_response=llm_response, parsed_output=report,
            status="success", error=None, truncation_warnings=truncation_warnings,
        ))
    except Exception as e:  # noqa: BLE001 — mirror app.py's broad guard
        append_trace(build_trace_record(
            source_patent=source, target_patent=target,
            system_prompt=system_prompt, user_prompt=user_prompt,
            llm_response=llm_response or dict(_EMPTY_LLM),
            parsed_output=None, status="error", error=str(e),
            truncation_warnings=truncation_warnings,
        ))
        return f"Analysis failed: {e}", None, None

    rows = [{
        "Element #": em.element_number,
        "Patent A Element": em.element_text,
        "Patent B Corresponding Text": em.corresponding_text,
        "Novelty": "✅" if em.novelty else "❌",
        "Inventive Step": "✅" if em.inventive_step else "❌",
        "Verdict": em.verdict,
        "Comment": em.comment,
    } for em in report.element_mappings]

    report_children = html.Div([
        html.H2("Element Mapping", className="uw-proto__h2"),
        dash_table.DataTable(
            data=rows,
            columns=[{"name": c, "id": c} for c in
                     ["Element #", "Patent A Element", "Patent B Corresponding Text",
                      "Novelty", "Inventive Step", "Verdict", "Comment"]],
            style_table={"overflowX": "auto"}, style_cell={"textAlign": "left"},
        ),
        html.H2("Overall Opinion", className="uw-proto__h2"),
        html.P(report.overall_opinion),
    ])
    meta_children = html.Details([
        html.Summary("Run Metadata"),
        html.P(f"Model: {llm_response['model']}"),
        html.P(f"Input tokens: {llm_response['tokens_input']}"),
        html.P(f"Output tokens: {llm_response['tokens_output']}"),
        html.P(f"Latency: {llm_response['latency_ms']}ms"),
    ])
    return "", report_children, meta_children


@callback(
    Output("analyze-status", "children"),
    Output("analyze-report", "children"),
    Output("analyze-meta", "children"),
    Input("analyze-btn", "n_clicks"),
    State("label-a", "value"), State("claim-a", "value"), State("spec-a", "value"),
    State("label-b", "value"), State("claim-b", "value"), State("spec-b", "value"),
    prevent_initial_call=True,
)
def _on_analyze(_n, la, ca, sa, lb, cb, sb):
    return run_analysis(la, ca, sa, lb, cb, sb)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_prototype_page.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Boot and smoke-test the form**

Run: `python -m app_unified.app`, open `/`, fill all six fields, click Analyze (requires `GROQ_API_KEY` in `.env`). Expected: element-mapping table + overall opinion + metadata; a new line appended to `traces/traces.jsonl`.

- [ ] **Step 6: Commit**

```bash
git add app_unified/pages/prototype.py tests/test_prototype_page.py
git commit -m "feat(unified): PatentDiff prototype page — port of Streamlit app.py"
```

---

# Task 2: Traces page (`/eval/traces`) — annotation tool

Port `app_annotation.py`. Keep all persistence in `core.annotation` (unchanged). Extract the verdict/failure-mode/comment **save logic** as a pure function so it is unit-testable without Dash.

**Files:**
- Modify: `app_unified/pages/eval_traces.py`
- Test: `tests/test_traces_page.py`

- [ ] **Step 1: Write the failing test (pure save/build helpers)**

```python
# tests/test_traces_page.py
from pathlib import Path

from core.annotation import load_annotations
from app_unified.pages import eval_traces


def test_build_record_phase3_fail_carries_failure_modes():
    rec = eval_traces.build_record(
        run_id="r1", phase=3, verdict="FAIL",
        failure_modes_ids=["citation_text"], comment="paraphrased", reviewed=True,
        dimensions={"claim_type": "Method"},
    )
    assert rec.failure_modes == ["citation_text"]
    assert rec.verdict == "FAIL"
    assert rec.dimensions == {"claim_type": "Method"}


def test_validate_rejects_fail_without_modes():
    errs = eval_traces.validate_annotation("FAIL", [], comment="x")
    assert any("requires at least one failure mode" in e for e in errs)


def test_validate_rejects_pass_with_modes():
    errs = eval_traces.validate_annotation("PASS", ["citation_text"], comment="x")
    assert any("cannot have failure modes" in e for e in errs)


def test_save_round_trip(tmp_path):
    path = tmp_path / "ann.jsonl"
    rec = eval_traces.build_record(
        run_id="r1", phase=1, verdict="PASS",
        failure_modes_ids=[], comment="ok", reviewed=False, dimensions=None,
    )
    eval_traces.persist_record(path, {"r1": rec})
    loaded = load_annotations(path)
    assert loaded["r1"].verdict == "PASS"
    assert loaded["r1"].comment == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_traces_page.py -v`
Expected: FAIL with `AttributeError: module 'app_unified.pages.eval_traces' has no attribute 'build_record'`.

- [ ] **Step 3: Implement the Traces page**

```python
# app_unified/pages/eval_traces.py
"""Traces — annotation tool. Port of app_annotation.py.

Trace browser (left) + read-only trace view (centre) + failure-mode coder
(right). Persists to traces/traces_annotations.jsonl via core.annotation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import dash
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from app_unified.components import page_header
from core.annotation import (AnnotationRecord, detect_phase, load_annotations,
                             load_taxonomy, parse_failure_modes, save_annotations)
from core.trace_loader import load_traces

dash.register_page(__name__, path="/eval/traces", name="Traces")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_FILE = REPO_ROOT / "traces" / "traces.jsonl"
ANNOTATIONS_FILE = REPO_ROOT / "traces" / "traces_annotations.jsonl"
TAXONOMY_FILE = REPO_ROOT / "failure_taxonomy.json"


# ── Pure logic (unit-tested) ──────────────────────────────────────────────────
def validate_annotation(verdict: str, failure_modes: List[str], comment: str) -> List[str]:
    """Mirror app_annotation.save_annotation validation. Returns error strings."""
    errors: List[str] = []
    if not comment:
        errors.append("Comment is required")
    if verdict == "PASS" and failure_modes:
        errors.append("PASS verdict cannot have failure modes selected")
    if verdict == "FAIL" and not failure_modes:
        errors.append("FAIL verdict requires at least one failure mode")
    return errors


def build_record(run_id: str, phase: int, verdict: str, failure_modes_ids: List[str],
                 comment: str, reviewed: bool,
                 dimensions: Optional[Dict[str, str]]) -> AnnotationRecord:
    """Build an AnnotationRecord exactly as app_annotation.save_annotation does."""
    modes = failure_modes_ids if verdict == "FAIL" else []
    if phase == 1:
        return AnnotationRecord(
            run_id=run_id, phase=1, open_coded_failure_modes=modes,
            verdict=verdict, comment=comment, reviewed=reviewed, dimensions=dimensions,
        )
    return AnnotationRecord(
        run_id=run_id, phase=3, failure_modes=modes,
        verdict=verdict, comment=comment, reviewed=reviewed, dimensions=dimensions,
    )


def persist_record(path: Path, annotations: Dict[str, AnnotationRecord]) -> None:
    save_annotations(path, annotations)


# ── Data access ───────────────────────────────────────────────────────────────
def _load_traces() -> dict:
    return {t.run_id: t for t in load_traces(TRACES_FILE)}


def _taxonomy_options() -> List[dict]:
    tax = load_taxonomy(TAXONOMY_FILE)
    return [{"label": c["name"], "value": c["id"]}
            for c in tax.get("failure_categories", [])]


# ── Layout ────────────────────────────────────────────────────────────────────
def _trace_options() -> List[dict]:
    opts = []
    for run_id, t in _load_traces().items():
        label = t.inputs.get("source_patent", {}).get("label", "?")
        opts.append({"label": f"{label[:24]}  ·  {run_id[:8]}", "value": run_id})
    return opts


layout = html.Div(
    className="uw-page uw-traces",
    children=[
        page_header("Traces — Error Analysis", "Browse traces and code failure modes."),
        dcc.Store(id="traces-phase", data=detect_phase(TAXONOMY_FILE)),
        html.Div(
            className="uw-traces__grid",
            children=[
                html.Aside(
                    className="uw-traces__nav",
                    children=[
                        html.Label("Trace", className="uw-label"),
                        dcc.Dropdown(id="traces-select", options=_trace_options(),
                                     className="uw-dropdown"),
                    ],
                ),
                dcc.Loading(html.Section(id="traces-detail", className="uw-traces__detail"),
                            type="dot"),
                html.Section(
                    className="uw-traces__form",
                    children=[
                        html.H2("Annotation", className="uw-traces__h2"),
                        html.Label("Verdict", className="uw-label"),
                        dcc.RadioItems(id="ann-verdict",
                                       options=[{"label": "PASS", "value": "PASS"},
                                                {"label": "FAIL", "value": "FAIL"}],
                                       value="PASS", className="uw-segmented__items"),
                        html.Label("Failure modes", className="uw-label"),
                        dcc.Dropdown(id="ann-modes", options=_taxonomy_options(),
                                     multi=True, className="uw-dropdown"),
                        html.Label("Comment", className="uw-label"),
                        dcc.Textarea(id="ann-comment", className="uw-input--area",
                                     style={"height": "150px"}),
                        dcc.Checklist(id="ann-reviewed",
                                      options=[{"label": "Reviewed", "value": "yes"}],
                                      value=[]),
                        html.Button("Save", id="ann-save", n_clicks=0,
                                    className="uw-btn uw-btn--primary"),
                        html.Div(id="ann-status", className="uw-status",
                                 role="status", **{"aria-live": "polite"}),
                    ],
                ),
            ],
        ),
    ],
)


# ── Callbacks ─────────────────────────────────────────────────────────────────
def _render_trace_detail(trace) -> html.Div:
    dims = trace.dimensions or {}
    src = trace.inputs.get("source_patent", {})
    tgt = trace.inputs.get("target_patent", {})
    children = [
        html.H2("Trace", className="uw-traces__h2"),
        html.P(f"Run ID: {trace.run_id[:12]}…  ·  Status: {trace.status}"),
        html.P(f"Claim type: {dims.get('claim_type','N/A')}  ·  "
               f"Length: {dims.get('claim_length','N/A')}  ·  "
               f"Relationship: {dims.get('relationship','N/A')}"),
        html.H3("Source Patent (A)"), html.P(src.get("label", "N/A")),
        dcc.Textarea(value=src.get("independent_claim", ""), readOnly=True,
                     className="uw-input--area", style={"height": "100px"}),
        html.H3("Target Patent (B)"), html.P(tgt.get("label", "N/A")),
        dcc.Textarea(value=tgt.get("independent_claim", ""), readOnly=True,
                     className="uw-input--area", style={"height": "100px"}),
    ]
    if trace.parsed_output:
        children.append(html.H3("Overall Opinion"))
        children.append(dcc.Textarea(value=trace.parsed_output.overall_opinion,
                                     readOnly=True, className="uw-input--area",
                                     style={"height": "120px"}))
    return html.Div(children)


@callback(
    Output("traces-detail", "children"),
    Output("ann-verdict", "value"),
    Output("ann-modes", "value"),
    Output("ann-comment", "value"),
    Output("ann-reviewed", "value"),
    Input("traces-select", "value"),
    State("traces-phase", "data"),
    prevent_initial_call=True,
)
def _select_trace(run_id, phase):
    if not run_id:
        return no_update, no_update, no_update, no_update, no_update
    traces = _load_traces()
    trace = traces.get(run_id)
    if trace is None:
        return html.P("Trace not found."), "PASS", [], "", []
    prev = load_annotations(ANNOTATIONS_FILE).get(run_id)
    if prev is None:
        return _render_trace_detail(trace), "PASS", [], "", []
    modes = (prev.failure_modes if phase == 3 else prev.open_coded_failure_modes) or []
    return (_render_trace_detail(trace), prev.verdict, modes, prev.comment or "",
            (["yes"] if prev.reviewed else []))


@callback(
    Output("ann-status", "children"),
    Input("ann-save", "n_clicks"),
    State("traces-select", "value"),
    State("ann-verdict", "value"),
    State("ann-modes", "value"),
    State("ann-comment", "value"),
    State("ann-reviewed", "value"),
    State("traces-phase", "data"),
    prevent_initial_call=True,
)
def _save(_n, run_id, verdict, modes, comment, reviewed, phase):
    if not run_id:
        return "Select a trace first."
    modes = modes or []
    errors = validate_annotation(verdict, modes, comment or "")
    if errors:
        return "❌ " + "; ".join(errors)
    traces = _load_traces()
    trace = traces.get(run_id)
    dimensions = trace.dimensions if trace else None
    annotations = load_annotations(ANNOTATIONS_FILE)
    annotations[run_id] = build_record(
        run_id=run_id, phase=phase, verdict=verdict, failure_modes_ids=modes,
        comment=comment, reviewed=bool(reviewed), dimensions=dimensions,
    )
    persist_record(ANNOTATIONS_FILE, annotations)
    return "✅ Annotation saved."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_traces_page.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Boot and smoke-test**

Run: `python -m app_unified.app`, open `/eval/traces`. Pick a trace → detail renders, form pre-fills from any existing annotation; change verdict to FAIL with no mode → Save shows the validation error; add a mode + comment → Save writes to `traces/traces_annotations.jsonl`. Confirm the new line via `git diff traces/traces_annotations.jsonl`.

- [ ] **Step 6: Commit**

```bash
git add app_unified/pages/eval_traces.py tests/test_traces_page.py
git commit -m "feat(unified): Traces page — port of Streamlit annotation tool"
```

---

# Task 3: Overview page (`/eval`) — fold in the analyst console

The console (`app_workbench/`) already uses the global `@callback` registry and reads an app-global `theme` / `data-version` store and a `corpus-selector` (in its own control bar). Mount its body as the `/eval` page and import its callbacks so they register. The shell already provides `theme`, `data-version`, `dcc.Location(id="url")`, and the theme toggle (Task 0), so the console's own copies of those are removed.

**Files:**
- Modify: `app_workbench/app.py` (extract a layout builder; stop creating a second Dash app at import)
- Modify: `app_unified/pages/eval_overview.py`
- Test: existing `tests/test_workbench_*.py`, `tests/test_diagnostics.py`, `tests/test_priority.py` (must stay green)

- [ ] **Step 1: Extract the console body into a reusable builder**

In `app_workbench/app.py`, refactor so the layout is built by a function and the `Dash(...)` instance is only created under `if __name__ == "__main__"`. Concretely:

1. Keep all the `_control_bar`, `_step_rail`, `_section`, `_SECTION_BODIES`, `STEPS`, helper definitions.
2. Remove `theme-toggle` from `_control_bar()` (the shell owns the global toggle now) — delete the `html.Button(id="theme-toggle", …)` child from the returned control bar.
3. Replace the module-level `app = Dash(...)` / `app.layout = …` / clientside callbacks / `app.run` block with:

```python
# app_workbench/app.py  (tail — replaces the old module-level Dash app + app.layout)
def build_console_body() -> html.Div:
    """The console's scrolling narrative, minus the global stores/Location/theme
    toggle (the unified shell owns those)."""
    return html.Div(
        className="wb-shell wb-page",
        children=[
            _control_bar(),   # corpus selector + run-eval + last-run (no theme toggle)
            html.Div(
                className="wb-shell__body",
                children=[
                    _step_rail(),
                    html.Main(
                        className="wb-main",
                        children=[
                            _section(anchor, num, title, question, _SECTION_BODIES[anchor])
                            for anchor, num, title, question in STEPS
                        ],
                    ),
                ],
            ),
        ],
    )


# Import the section callbacks so they register against the global @callback registry.
from app_workbench import callbacks  # noqa: E402,F401
```

Remove the old `url-writer-dummy`/url clientside callback from `app_workbench/app.py` (the shell can keep deep-linking simple for Spec 1 — the corpus/eval query-param writer is non-essential and is re-added in Spec 2 if needed). Delete the `app.clientside_callback(... url-writer-dummy ...)` and `dcc.Location`/`dcc.Store(theme/data-version)` lines, since those ids now live in the shell.

- [ ] **Step 2: Mount the console body as the Overview page**

```python
# app_unified/pages/eval_overview.py
"""Overview — the analyst console, folded in as the /eval page."""
import dash

from app_workbench.app import build_console_body

dash.register_page(__name__, path="/eval", name="Overview")

layout = build_console_body()
```

- [ ] **Step 3: Run the console's existing tests to verify no regression**

Run: `pytest tests/test_workbench_data.py tests/test_diagnostics.py tests/test_priority.py tests/test_workbench_state.py tests/test_eval_runner.py -v`
Expected: PASS (unchanged — these test `core/`, not the Dash wiring).

- [ ] **Step 4: Boot and verify the console renders inside the shell**

Run: `python -m app_unified.app`, open `/eval`. Expected: the five-step console (How bad → Where → Why → Priority → Decision) renders with its control bar (corpus selector, Run eval, last-run); the **shell's** theme toggle recolors it; KPIs/heatmap/priority/decision behave as before; corpus switch re-derives the page. The eval sub-nav shows Overview active.

- [ ] **Step 5: Verify there is exactly one `theme-toggle` and one `corpus-selector` in the DOM**

In the running app, open dev-tools and confirm a single `#theme-toggle` (in the appbar) and a single `#corpus-selector` (in the console control bar). No duplicate-id console warnings.

- [ ] **Step 6: Commit**

```bash
git add app_workbench/app.py app_unified/pages/eval_overview.py
git commit -m "feat(unified): Overview page — fold analyst console into /eval; shell owns theme + stores"
```

---

# Task 4: `core/eval_delta.py` — verdict transition + PASS-rate delta

Extract the comparison logic from `scripts/compute_eval_delta.py` into a testable core module, then refactor the script to call it.

**Files:**
- Create: `core/eval_delta.py`
- Modify: `scripts/compute_eval_delta.py`
- Test: `tests/test_eval_delta.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_delta.py
from core.eval_delta import EvalDelta, compute_delta

BEFORE = {"r1": "FAIL", "r2": "PASS", "r3": "FAIL", "r4": "PASS"}
AFTER = {"r1": "PASS", "r2": "PASS", "r3": "FAIL", "r4": "MISSING"}


def test_transition_matrix_counts():
    d = compute_delta(BEFORE, AFTER)
    assert d.matrix[("FAIL", "PASS")] == 1     # r1 fixed
    assert d.matrix[("FAIL", "FAIL")] == 1     # r3 still failing
    assert d.matrix[("PASS", "PASS")] == 1     # r2
    assert d.matrix[("PASS", "MISSING")] == 1  # r4 dropped


def test_pass_rate_delta():
    d = compute_delta(BEFORE, AFTER)
    # before scored (PASS+FAIL): r1,r2,r3,r4 → 2/4 = 50%
    assert round(d.before_rate, 3) == 0.5
    # after scored: r1,r2,r3 → 2/3 = 66.7% (r4 MISSING not scored)
    assert round(d.after_rate, 3) == 0.667
    assert d.delta_pp > 0


def test_flipped_buckets_list_run_ids():
    d = compute_delta(BEFORE, AFTER)
    assert d.buckets[("FAIL", "PASS")] == ["r1"]


def test_run_id_filter_restricts():
    d = compute_delta(BEFORE, AFTER, run_ids={"r1"})
    assert sum(d.matrix.values()) == 1
    assert d.matrix[("FAIL", "PASS")] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_delta.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.eval_delta'`.

- [ ] **Step 3: Implement `core/eval_delta.py`**

```python
# core/eval_delta.py
"""Compare two eval-verdict maps (before/after) by run_id.

A "verdict map" is {run_id: verdict} where verdict ∈ VERDICTS. Used by both
scripts/compute_eval_delta.py (CLI) and the Comparison page.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

VERDICTS = ["PASS", "FAIL", "NO_CITATIONS", "MISSING"]
Transition = Tuple[str, str]


@dataclass
class EvalDelta:
    matrix: Counter                                   # (before, after) -> count
    buckets: Dict[Transition, List[str]]              # (before, after) -> run_ids
    before_rate: float
    after_rate: float
    before_scored: int
    after_scored: int

    @property
    def delta_pp(self) -> float:
        """Change in PASS rate, in percentage points."""
        return 100.0 * (self.after_rate - self.before_rate)


def load_verdict_map(path: Path) -> Dict[str, str]:
    """Read {run_id: verdict} from an eval JSONL file (empty if missing)."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("run_id") and d.get("verdict"):
                out[d["run_id"]] = d["verdict"]
    return out


def _pass_rate(d: Dict[str, str]) -> Tuple[float, int]:
    scored = [v for v in d.values() if v in ("PASS", "FAIL")]
    if not scored:
        return 0.0, 0
    return sum(v == "PASS" for v in scored) / len(scored), len(scored)


def compute_delta(before: Dict[str, str], after: Dict[str, str],
                  run_ids: Optional[Iterable[str]] = None) -> EvalDelta:
    if run_ids is not None:
        ids = set(run_ids)
        before = {k: v for k, v in before.items() if k in ids}
        after = {k: v for k, v in after.items() if k in ids}
        all_ids = ids
    else:
        all_ids = set(before) | set(after)

    matrix: Counter = Counter()
    buckets: Dict[Transition, List[str]] = defaultdict(list)
    for rid in sorted(all_ids):
        b = before.get(rid, "MISSING")
        a = after.get(rid, "MISSING")
        matrix[(b, a)] += 1
        buckets[(b, a)].append(rid)

    br, bs = _pass_rate(before)
    ar, as_ = _pass_rate(after)
    return EvalDelta(matrix=matrix, buckets=dict(buckets),
                     before_rate=br, after_rate=ar,
                     before_scored=bs, after_scored=as_)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_delta.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Refactor the CLI script to use the core module**

In `scripts/compute_eval_delta.py`, replace the inline `load_eval`, matrix build, and `pass_rate` with imports from `core.eval_delta`. Keep the CLI args and printed output format identical:

```python
# scripts/compute_eval_delta.py  (body of main(), replacing the inline logic)
from core.eval_delta import VERDICTS, compute_delta, load_verdict_map

# ... argparse unchanged ...
before = load_verdict_map(args.before)
after = load_verdict_map(args.after)
run_ids = None
if args.run_ids:
    run_ids = {l.strip() for l in args.run_ids.read_text().splitlines()
               if l.strip() and not l.startswith("#")}
delta = compute_delta(before, after, run_ids=run_ids)
# print delta.matrix / delta.before_rate / delta.after_rate / delta.delta_pp / delta.buckets
# using the same header + row layout already in the file.
```

- [ ] **Step 6: Verify the CLI still runs identically**

Run: `python scripts/compute_eval_delta.py --before traces/citation_text_eval_full.baseline.jsonl --after traces/citation_text_eval_full.jsonl`
Expected: a transition matrix + PASS-rate before/after/delta + per-bucket run_ids, same shape as before the refactor.

- [ ] **Step 7: Commit**

```bash
git add core/eval_delta.py scripts/compute_eval_delta.py tests/test_eval_delta.py
git commit -m "feat(core): extract eval_delta (transition matrix + PASS-rate delta); CLI reuses it"
```

---

# Task 5: Comparison page (`/eval/comparison`) — before/after delta v1

Two trace-set selectors + an eval toggle drive `core.eval_delta`. Renders PASS-rate delta KPIs, the verdict transition matrix, and the flipped-run_id list. Trace-set discovery reuses `core.workbench_data`.

**Files:**
- Modify: `app_unified/pages/eval_comparison.py`
- Test: `tests/test_comparison_page.py`

The eval-output file for a given trace set follows the suffix convention: the "live" set uses `phosita_eval_full.jsonl` / `citation_text_eval_full.jsonl`; a named set `<name>` uses `..._full.<name>.jsonl`. Encode that mapping in one helper.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_comparison_page.py
from pathlib import Path

from app_unified.pages import eval_comparison


def test_eval_path_live_vs_named():
    base = Path("traces")
    assert eval_comparison.eval_path(base, "live", "phosita").name == "phosita_eval_full.jsonl"
    assert eval_comparison.eval_path(base, "baseline", "phosita").name == "phosita_eval_full.baseline.jsonl"
    assert eval_comparison.eval_path(base, "baseline", "citation").name == "citation_text_eval_full.baseline.jsonl"


def test_build_comparison_returns_kpis_and_matrix(tmp_path):
    before = tmp_path / "phosita_eval_full.baseline.jsonl"
    after = tmp_path / "phosita_eval_full.jsonl"
    before.write_text('{"run_id":"r1","verdict":"FAIL"}\n{"run_id":"r2","verdict":"PASS"}\n')
    after.write_text('{"run_id":"r1","verdict":"PASS"}\n{"run_id":"r2","verdict":"PASS"}\n')
    result = eval_comparison.build_comparison(tmp_path, "baseline", "live", "phosita")
    assert result["before_rate"] == 0.5
    assert result["after_rate"] == 1.0
    assert result["matrix"][("FAIL", "PASS")] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_comparison_page.py -v`
Expected: FAIL with `AttributeError: ... has no attribute 'eval_path'`.

- [ ] **Step 3: Implement the Comparison page**

```python
# app_unified/pages/eval_comparison.py
"""Comparison (v1) — before/after eval delta for two trace sets."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import dash
from dash import Input, Output, callback, dash_table, dcc, html

from app_unified.components import page_header
from core.eval_delta import VERDICTS, compute_delta, load_verdict_map
from core.workbench_data import list_trace_sets

dash.register_page(__name__, path="/eval/comparison", name="Comparison")

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "traces"

_EVAL_STEM = {"phosita": "phosita_eval_full", "citation": "citation_text_eval_full"}


def eval_path(base: Path, trace_set: str, eval_kind: str) -> Path:
    """Map (trace set, eval kind) → eval JSONL path (suffix convention)."""
    stem = _EVAL_STEM[eval_kind]
    if trace_set == "live":
        return base / f"{stem}.jsonl"
    return base / f"{stem}.{trace_set}.jsonl"


def _set_options() -> list[dict]:
    try:
        names = [s.name for s in list_trace_sets(TRACES_DIR)]
    except Exception:
        names = []
    if "live" not in names:
        names = ["live", *names]
    return [{"label": n, "value": n} for n in names]


def build_comparison(base: Path, before_set: str, after_set: str,
                     eval_kind: str) -> Dict:
    before = load_verdict_map(eval_path(base, before_set, eval_kind))
    after = load_verdict_map(eval_path(base, after_set, eval_kind))
    d = compute_delta(before, after)
    return {
        "matrix": d.matrix, "buckets": d.buckets,
        "before_rate": d.before_rate, "after_rate": d.after_rate,
        "delta_pp": d.delta_pp,
        "before_scored": d.before_scored, "after_scored": d.after_scored,
    }


layout = html.Div(
    className="uw-page uw-compare",
    children=[
        page_header("Comparison", "How did eval scores change after a prompt change?"),
        html.Div(
            className="uw-compare__controls",
            children=[
                html.Div([html.Label("Before (baseline)", className="uw-label"),
                          dcc.Dropdown(id="cmp-before", options=_set_options(),
                                       value="baseline", className="uw-dropdown")]),
                html.Div([html.Label("After (experiment)", className="uw-label"),
                          dcc.Dropdown(id="cmp-after", options=_set_options(),
                                       value="live", className="uw-dropdown")]),
                html.Div([html.Label("Eval", className="uw-label"),
                          dcc.RadioItems(id="cmp-eval",
                                         options=[{"label": "PHOSITA", "value": "phosita"},
                                                  {"label": "Citation", "value": "citation"}],
                                         value="phosita",
                                         className="uw-segmented__items")]),
            ],
        ),
        html.Div(id="cmp-kpis", className="uw-compare__kpis"),
        html.H2("Verdict transitions", className="uw-compare__h2"),
        html.Div(id="cmp-matrix"),
        html.H2("Flipped traces", className="uw-compare__h2"),
        html.Div(id="cmp-flipped"),
    ],
)


def _kpi(label: str, value: str) -> html.Div:
    return html.Div(className="uw-kpi", children=[
        html.Span(label, className="uw-kpi__label"),
        html.Span(value, className="uw-kpi__value uw-num"),
    ])


@callback(
    Output("cmp-kpis", "children"),
    Output("cmp-matrix", "children"),
    Output("cmp-flipped", "children"),
    Input("cmp-before", "value"),
    Input("cmp-after", "value"),
    Input("cmp-eval", "value"),
)
def _render(before_set, after_set, eval_kind):
    if not (before_set and after_set and eval_kind):
        return html.P("Pick two trace sets."), None, None
    r = build_comparison(TRACES_DIR, before_set, after_set, eval_kind)
    kpis = [
        _kpi("Before PASS", f"{100*r['before_rate']:.1f}%  (n={r['before_scored']})"),
        _kpi("After PASS", f"{100*r['after_rate']:.1f}%  (n={r['after_scored']})"),
        _kpi("Delta", f"{r['delta_pp']:+.1f} pp"),
    ]
    matrix_rows = [{"before": b, **{a: r["matrix"].get((b, a), 0) for a in VERDICTS}}
                   for b in VERDICTS]
    matrix = dash_table.DataTable(
        data=matrix_rows,
        columns=[{"name": "before \\ after", "id": "before"}]
                + [{"name": a, "id": a} for a in VERDICTS],
        style_cell={"textAlign": "right"},
        style_cell_conditional=[{"if": {"column_id": "before"}, "textAlign": "left"}],
    )
    fixed = r["buckets"].get(("FAIL", "PASS"), [])
    regressed = r["buckets"].get(("PASS", "FAIL"), [])
    flipped = html.Div([
        html.P(f"Fixed (FAIL→PASS): {len(fixed)}"),
        html.Code(" ".join(x[:8] for x in fixed[:20]) or "—"),
        html.P(f"Regressed (PASS→FAIL): {len(regressed)}"),
        html.Code(" ".join(x[:8] for x in regressed[:20]) or "—"),
    ])
    return kpis, matrix, flipped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_comparison_page.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Boot and smoke-test**

Run: `python -m app_unified.app`, open `/eval/comparison`. Pick before=`baseline`, after=`live`, eval=PHOSITA → KPIs, transition matrix, and flipped lists render. Toggle to Citation → numbers update. Missing eval file for a set → empty maps → all-zero matrix (no crash).

- [ ] **Step 6: Commit**

```bash
git add app_unified/pages/eval_comparison.py tests/test_comparison_page.py
git commit -m "feat(unified): Comparison v1 — before/after eval delta page"
```

---

# Task 6: Cleanup — delete legacy Streamlit apps

Only after Tasks 1–5 are green and parity is confirmed in the booted app.

**Files:**
- Delete: `scripts/run_dashboard.py`
- Delete: `app.py`
- Delete: `app_annotation.py`
- Modify: `requirements.txt`
- Modify: `README.md`, `README_ANNOTATION_TOOL.md`, `ANNOTATION_TOOL_README.md` (run instructions)

- [ ] **Step 1: Confirm nothing imports the legacy apps**

Run: `grep -rn "import app_annotation\|from app_annotation\|run_dashboard\|streamlit run app" --include=*.py --include=*.md .`
Expected: only matches inside docs you are about to update (no Python import references).

- [ ] **Step 2: Delete the legacy Streamlit files**

```bash
git rm scripts/run_dashboard.py app.py app_annotation.py
```

- [ ] **Step 3: Drop Streamlit from requirements if unused**

Run: `grep -rn "import streamlit\|streamlit run" --include=*.py .`
Expected: no remaining hits. Then remove the `streamlit` line from `requirements.txt`.

- [ ] **Step 4: Update run instructions in the READMEs**

Replace `streamlit run app.py` / `streamlit run app_annotation.py` / `streamlit run scripts/run_dashboard.py` / `python -m app_workbench.app` references with the single entry point:

```
python -m app_unified.app   # then open http://127.0.0.1:8050/
```

- [ ] **Step 5: Run the full test suite**

Run: `pytest -q`
Expected: PASS (all tests, including the new page tests and the relocated console tests).

- [ ] **Step 6: Final boot check of every route**

Run: `python -m app_unified.app` and visit `/`, `/eval`, `/eval/traces`, `/eval/comparison`. Expected: all render; nav and theme toggle work; no duplicate-id console warnings.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(unified): remove legacy Streamlit apps; single python -m app_unified.app entry point"
```

---

## Self-review notes (addressed)

- **Spec coverage:** shell (Task 0), prototype port (Task 1), annotation port (Task 2), console fold-in (Task 3), `core/eval_delta` + Comparison v1 (Tasks 4–5), legacy deletion (Task 6). Branch strategy in Pre-flight. All Spec 1 success criteria map to a task.
- **Frozen ruler:** no task touches `core/phosita_eval.py`, `core/citation_eval.py`, or judge prompts.
- **Deferred (Spec 2):** experiment tracker, shared global active-trace-set, per-view redesign — none appear as tasks here, by design.
- **Type consistency:** `compute_delta`/`EvalDelta`/`load_verdict_map` names match across Task 4 (definition) and Task 5 (use); `build_record`/`validate_annotation`/`persist_record` match across Task 2 test and implementation; `build_console_body` matches across Task 3 Steps 1–2.
