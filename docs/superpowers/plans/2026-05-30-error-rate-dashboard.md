# Error Rate Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Streamlit dashboard (`scripts/run_dashboard.py`) that shows PHOSITA and citation eval FAIL rates broken down by patent dimensions, plus a PM-facing implications section.

**Architecture:** A `core/dimension_tagger.py` module infers claim_type / claim_length / relationship from trace data (human annotations override where available). `scripts/run_dashboard.py` loads all four JSONL sources into a single pandas DataFrame at startup (cached via `@st.cache_data`) and renders three tabs: Summary KPIs, Error Heatmap, PM Implications.

**Tech Stack:** Python 3.13, Streamlit 1.45, pandas 2.x, pytest. No plotly — heatmap uses pandas Styler `background_gradient`.

---

## File Map

| File | Change |
|---|---|
| `core/dimension_tagger.py` | **Create** — inference functions + `tag_trace` |
| `tests/test_dimension_tagger.py` | **Create** — unit tests (TDD) |
| `scripts/run_dashboard.py` | **Create** — Streamlit 3-tab dashboard |

No existing files are modified.

---

## Task 1: Dimension Tagger — tests first, then implementation

**Files:**
- Create: `tests/test_dimension_tagger.py`
- Create: `core/dimension_tagger.py`

- [ ] **Step 1: Write `tests/test_dimension_tagger.py`**

```python
"""Tests for core/dimension_tagger.py."""
import pytest

from core.dimension_tagger import (
    infer_claim_length,
    infer_claim_type,
    infer_relationship,
    tag_trace,
)


def _trace_with_claim(claim: str) -> dict:
    return {"inputs": {"source_patent": {"independent_claim": claim}}}


def _trace_with_elements(novelty_list: list[str]) -> dict:
    return {
        "parsed_output": {
            "element_mappings": [
                {"element_number": i + 1, "novelty": n}
                for i, n in enumerate(novelty_list)
            ]
        }
    }


# --- infer_claim_type ---


def test_infer_claim_type_method_simple():
    assert infer_claim_type(_trace_with_claim("A method comprising:\nreceiving data")) == "Method"


def test_infer_claim_type_method_computer_implemented():
    assert (
        infer_claim_type(_trace_with_claim("A computer-implemented method, comprising:\nprocessing"))
        == "Method"
    )


def test_infer_claim_type_method_with_leading_number():
    assert (
        infer_claim_type(_trace_with_claim("1. A method for processing, the method comprising:"))
        == "Method"
    )


def test_infer_claim_type_method_performed_by():
    assert (
        infer_claim_type(_trace_with_claim("A method performed by one or more computers, comprising:"))
        == "Method"
    )


def test_infer_claim_type_system():
    assert infer_claim_type(_trace_with_claim("A system comprising:\nat least one processor")) == "System"


def test_infer_claim_type_apparatus():
    assert (
        infer_claim_type(_trace_with_claim("An apparatus for encoding audio, comprising:\none or more processors"))
        == "System"
    )


def test_infer_claim_type_article():
    assert (
        infer_claim_type(_trace_with_claim("An abrasive article comprising:\na backing"))
        == "System"
    )


def test_infer_claim_type_unknown_empty():
    assert infer_claim_type(_trace_with_claim("")) == "Unknown"


def test_infer_claim_type_unknown_no_inputs():
    assert infer_claim_type({}) == "Unknown"


# --- infer_claim_length ---


def test_infer_claim_length_short_four_elements():
    assert infer_claim_length(_trace_with_elements(["Y", "N", "Y", "N"])) == "Short"


def test_infer_claim_length_short_five_elements():
    # Spec: Short = ≤5 elements
    assert infer_claim_length(_trace_with_elements(["Y"] * 5)) == "Short"


def test_infer_claim_length_long_six_elements():
    assert infer_claim_length(_trace_with_elements(["Y"] * 6)) == "Long"


def test_infer_claim_length_long_ten_elements():
    assert infer_claim_length(_trace_with_elements(["N"] * 10)) == "Long"


def test_infer_claim_length_short_no_parsed_output():
    # Zero elements → Short
    assert infer_claim_length({}) == "Short"


# --- infer_relationship ---


def test_infer_relationship_anticipation_all_y():
    # 100% Y → Anticipation
    assert infer_relationship(_trace_with_elements(["Y", "Y", "Y", "Y"])) == "Anticipation"


def test_infer_relationship_anticipation_mostly_y():
    # 75% Y (≥0.60) → Anticipation
    assert infer_relationship(_trace_with_elements(["Y", "Y", "Y", "N"])) == "Anticipation"


def test_infer_relationship_novel_all_n():
    # 0% Y → Novel
    assert infer_relationship(_trace_with_elements(["N", "N", "N", "N"])) == "Novel"


def test_infer_relationship_novel_mostly_n():
    # 25% Y (≤0.25) → Novel
    assert infer_relationship(_trace_with_elements(["Y", "N", "N", "N"])) == "Novel"


def test_infer_relationship_implicit_mixed():
    # 40% Y → Implicit
    assert infer_relationship(_trace_with_elements(["Y", "Y", "N", "N", "N"])) == "Implicit"


def test_infer_relationship_implicit_half():
    # 50% Y → Implicit
    assert infer_relationship(_trace_with_elements(["Y", "Y", "N", "N"])) == "Implicit"


def test_infer_relationship_unknown_no_elements():
    assert infer_relationship({}) == "Unknown"
    assert infer_relationship({"parsed_output": {"element_mappings": []}}) == "Unknown"


# --- tag_trace ---


def test_tag_trace_returns_all_dimensions_and_source():
    trace = {
        "inputs": {"source_patent": {"independent_claim": "A method comprising:\nreceiving data"}},
        "parsed_output": {
            "element_mappings": [
                {"element_number": 1, "novelty": "Y"},
                {"element_number": 2, "novelty": "N"},
            ]
        },
    }
    result = tag_trace(trace)
    assert result["claim_type"] == "Method"
    assert result["claim_length"] == "Short"   # 2 elements ≤ 5
    assert result["relationship"] == "Implicit"  # 50% Y
    assert result["source"] == "inferred"


def test_tag_trace_empty_trace():
    result = tag_trace({})
    assert result["claim_type"] == "Unknown"
    assert result["claim_length"] == "Short"
    assert result["relationship"] == "Unknown"
    assert result["source"] == "inferred"
```

- [ ] **Step 2: Run tests — confirm they all fail**

```
python -m pytest tests/test_dimension_tagger.py -v
```

Expected: `ImportError: No module named 'core.dimension_tagger'`

- [ ] **Step 3: Write `core/dimension_tagger.py`**

```python
"""Infers claim dimensions from trace data for the error rate dashboard.

Functions take the full trace dict and return a string label.
Human-annotated dimensions in traces_annotations.jsonl override these
inferences in the dashboard — these are fallbacks for un-annotated traces.
"""
from __future__ import annotations

import re


def infer_claim_type(trace: dict) -> str:
    """Return 'Method', 'System', or 'Unknown' from the source independent claim."""
    raw = (
        ((trace.get("inputs") or {}).get("source_patent") or {})
        .get("independent_claim", "")
    )
    # Strip leading numbers and dots (e.g. "1. A method")
    claim = re.sub(r"^[\d\s.]+", "", raw).strip().lower()
    if not claim:
        return "Unknown"
    if re.search(r"\ba\s+(computer-implemented\s+)?method\b", claim[:80]):
        return "Method"
    if re.search(r"\bmethod\s+(for|comprising|performed|implemented)\b", claim[:80]):
        return "Method"
    if re.search(r"\b(system|apparatus|device|article|encoder|circuit)\b", claim[:60]):
        return "System"
    if re.search(r"comprising:\s*(one or more\s+)?(processors?|memory|means)", claim[:120]):
        return "System"
    return "Unknown"


def infer_claim_length(trace: dict) -> str:
    """Return 'Short' (≤5 elements) or 'Long' (>5 elements)."""
    mappings = ((trace.get("parsed_output") or {}).get("element_mappings") or [])
    return "Long" if len(mappings) > 5 else "Short"


def infer_relationship(trace: dict) -> str:
    """Return 'Anticipation', 'Implicit', 'Novel', or 'Unknown'.

    Based on fraction of elements with novelty='Y' (found in prior art):
    - frac_Y >= 0.60 → Anticipation
    - frac_Y <= 0.25 → Novel
    - otherwise     → Implicit
    """
    mappings = ((trace.get("parsed_output") or {}).get("element_mappings") or [])
    if not mappings:
        return "Unknown"
    n_y = sum(1 for e in mappings if e.get("novelty") == "Y")
    frac_y = n_y / len(mappings)
    if frac_y >= 0.60:
        return "Anticipation"
    if frac_y <= 0.25:
        return "Novel"
    return "Implicit"


def tag_trace(trace: dict) -> dict:
    """Return inferred dimensions for a single trace.

    Returns:
        {
            "claim_type": "Method" | "System" | "Unknown",
            "claim_length": "Short" | "Long",
            "relationship": "Anticipation" | "Implicit" | "Novel" | "Unknown",
            "source": "inferred",
        }
    """
    return {
        "claim_type": infer_claim_type(trace),
        "claim_length": infer_claim_length(trace),
        "relationship": infer_relationship(trace),
        "source": "inferred",
    }
```

- [ ] **Step 4: Run tests — confirm all pass**

```
python -m pytest tests/test_dimension_tagger.py -v
```

Expected: `19 passed`

- [ ] **Step 5: Commit**

```
git add core/dimension_tagger.py tests/test_dimension_tagger.py
git commit -m "feat(dimension_tagger): infer claim_type / claim_length / relationship from trace data"
```

---

## Task 2: Dashboard — data loader

**Files:**
- Create: `scripts/run_dashboard.py`

The dashboard is a single Streamlit file. Build it function by function, verifying visually after each tab. Start with the data loader — the foundation all three tabs share.

- [ ] **Step 1: Write `scripts/run_dashboard.py` with `_load_data` only**

```python
#!/usr/bin/env python
"""Error Rate Dashboard for PatentDiff evals.

Run with:
    streamlit run scripts/run_dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.dimension_tagger import tag_trace

PHOSITA_PROMPT_VERSION = "v3"
TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
PHOSITA_PATH = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"
CITATION_PATH = REPO_ROOT / "traces" / "citation_text_eval_full.jsonl"
ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"

st.set_page_config(page_title="PatentDiff — Error Rate Dashboard", layout="wide")
st.title("PatentDiff — Error Rate Dashboard")


@st.cache_data
def _load_data() -> pd.DataFrame:
    """Load and merge all eval sources into one DataFrame.

    One row per trace that has at least one eval result. Dimensions are
    inferred from trace data; human-annotated dimensions override where present.
    """
    # 1. Load traces and infer dimensions for all
    traces: dict[str, dict] = {}
    with open(TRACES_PATH, encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            traces[t["run_id"]] = t
    dims: dict[str, dict] = {rid: tag_trace(t) for rid, t in traces.items()}

    # 2. Override with human-verified dimensions where available
    with open(ANNOTATIONS_PATH, encoding="utf-8") as f:
        for line in f:
            ann = json.loads(line)
            if ann.get("phase") == 3 and ann.get("dimensions"):
                rid = ann["run_id"]
                if rid in dims:
                    human_dims = ann["dimensions"]
                    dims[rid] = {
                        "claim_type": human_dims.get("claim_type", dims[rid]["claim_type"]),
                        "claim_length": human_dims.get("claim_length", dims[rid]["claim_length"]),
                        "relationship": human_dims.get("relationship", dims[rid]["relationship"]),
                        "source": "human",
                    }

    # 3. Load PHOSITA verdicts (v3 only)
    phosita: dict[str, str] = {}
    with open(PHOSITA_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if (r.get("config") or {}).get("prompt_version") == PHOSITA_PROMPT_VERSION:
                phosita[r["run_id"]] = r["verdict"]

    # 4. Load citation verdicts
    citation: dict[str, str] = {}
    with open(CITATION_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            citation[r["run_id"]] = r["verdict"]

    # 5. Build DataFrame — one row per trace with ≥1 eval result
    rows = []
    for rid in set(phosita) | set(citation):
        dim = dims.get(rid, {
            "claim_type": "Unknown",
            "claim_length": "Unknown",
            "relationship": "Unknown",
            "source": "inferred",
        })
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


# Minimal render to verify loader works
df = _load_data()
st.write(f"Loaded {len(df)} traces. Columns: {list(df.columns)}")
st.dataframe(df.head(10))
```

- [ ] **Step 2: Run and verify the loader**

```
streamlit run scripts/run_dashboard.py
```

Open http://localhost:8501. Expected: page shows "Loaded 87 traces" and a 10-row preview with columns `run_id, claim_type, claim_length, relationship, dim_source, phosita_verdict, citation_verdict`.

- [ ] **Step 3: Commit**

```
git add scripts/run_dashboard.py
git commit -m "feat(dashboard): scaffold Streamlit app with data loader"
```

---

## Task 3: Dashboard — Summary tab

**Files:**
- Modify: `scripts/run_dashboard.py`

Replace the temporary `st.write` / `st.dataframe` at the bottom with the full three-tab layout, starting with the Summary tab. The other two tabs will show a placeholder for now.

- [ ] **Step 1: Replace the bottom of `scripts/run_dashboard.py` with the full tab layout and `render_summary`**

Remove the two temporary lines at the bottom (`st.write(...)` and `st.dataframe(...)`) and replace with everything below. Add `render_summary`, `render_heatmap` (stub), and `render_implications` (stub), then wire the tabs.

```python
# ── Replace from "# Minimal render..." to end of file with: ──────────────────


def render_summary(df: pd.DataFrame) -> None:
    """Tab 1: KPI metrics, co-occurrence table, highest-risk dimension preview."""
    # KPIs
    ph = df[df["phosita_verdict"].isin(["PASS", "FAIL"])]
    ct = df[df["citation_verdict"].isin(["PASS", "FAIL"])]
    both = df[
        df["phosita_verdict"].isin(["PASS", "FAIL"]) &
        df["citation_verdict"].isin(["PASS", "FAIL"])
    ]

    ph_rate = (ph["phosita_verdict"] == "FAIL").mean() if not ph.empty else 0.0
    ct_rate = (ct["citation_verdict"] == "FAIL").mean() if not ct.empty else 0.0
    either_rate = (
        ((both["phosita_verdict"] == "FAIL") | (both["citation_verdict"] == "FAIL")).mean()
        if not both.empty else 0.0
    )
    clean_rate = (
        ((both["phosita_verdict"] == "PASS") & (both["citation_verdict"] == "PASS")).mean()
        if not both.empty else 0.0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PHOSITA Reasoning Failures", f"{ph_rate:.0%}", f"n={len(ph)}")
    c2.metric("Citation Text Failures", f"{ct_rate:.0%}", f"n={len(ct)}")
    c3.metric("Either Failure Mode", f"{either_rate:.0%}", f"n={len(both)}")
    c4.metric("Fully Clean (both pass)", f"{clean_rate:.0%}", f"n={len(both)}")

    st.divider()

    # Co-occurrence table
    st.subheader("Failure Co-occurrence")
    if both.empty:
        st.info("No traces have both eval results.")
    else:
        ph_fail = both["phosita_verdict"] == "FAIL"
        ct_fail = both["citation_verdict"] == "FAIL"
        co = pd.DataFrame(
            {
                "PHOSITA PASS": [
                    int((~ph_fail & ~ct_fail).sum()),
                    int((~ph_fail & ct_fail).sum()),
                ],
                "PHOSITA FAIL": [
                    int((ph_fail & ~ct_fail).sum()),
                    int((ph_fail & ct_fail).sum()),
                ],
            },
            index=["Citation PASS", "Citation FAIL"],
        )
        st.dataframe(co, use_container_width=False)
        st.caption("Traces with both PHOSITA and citation eval results.")

    st.divider()

    # Highest/lowest risk relationship
    st.subheader("Highest Risk Dimension (PHOSITA)")
    rel_ph = ph[ph["relationship"] != "Unknown"]
    if not rel_ph.empty:
        rates = rel_ph.groupby("relationship")["phosita_verdict"].apply(
            lambda s: (s == "FAIL").mean()
        ).sort_values(ascending=False)
        ca, cb = st.columns(2)
        ca.metric(f"Worst: {rates.index[0]}", f"{rates.iloc[0]:.0%} FAIL rate")
        cb.metric(f"Best: {rates.index[-1]}", f"{rates.iloc[-1]:.0%} FAIL rate")


def render_heatmap(df: pd.DataFrame) -> None:
    st.info("Heatmap coming in next step.")


def render_implications() -> None:
    st.info("PM Implications coming in next step.")


# ── Entry point ───────────────────────────────────────────────────────────────
df = _load_data()
tab1, tab2, tab3 = st.tabs(["📊 Summary", "🔥 Error Heatmap", "📋 PM Implications"])
with tab1:
    render_summary(df)
with tab2:
    render_heatmap(df)
with tab3:
    render_implications()
```

- [ ] **Step 2: Run and verify Summary tab**

```
streamlit run scripts/run_dashboard.py
```

Open http://localhost:8501, click **📊 Summary**. Expected:
- 4 metric tiles with real percentages and n= counts
- A co-occurrence table with 2×2 integer cells
- Two metric tiles showing worst/best relationship FAIL rate

- [ ] **Step 3: Commit**

```
git add scripts/run_dashboard.py
git commit -m "feat(dashboard): add Summary tab — KPIs, co-occurrence, dimension preview"
```

---

## Task 4: Dashboard — Error Heatmap tab

**Files:**
- Modify: `scripts/run_dashboard.py`

Replace the `render_heatmap` stub with the real implementation.

- [ ] **Step 1: Replace `render_heatmap` in `scripts/run_dashboard.py`**

Find the line `def render_heatmap(df: pd.DataFrame) -> None:` and replace the entire function body with:

```python
def render_heatmap(df: pd.DataFrame) -> None:
    """Tab 2: Colour-coded FAIL rate heatmap, relationship × claim profile."""
    eval_choice = st.radio(
        "Show eval:",
        ["PHOSITA Reasoning", "Citation Text", "Both (either fails)"],
        horizontal=True,
    )

    # Build a working copy with the profile label and a 'fail' boolean
    work = df.copy()
    work["profile"] = work["claim_type"] + " · " + work["claim_length"]

    if eval_choice == "PHOSITA Reasoning":
        scored = work[work["phosita_verdict"].isin(["PASS", "FAIL"])].copy()
        scored["fail"] = scored["phosita_verdict"] == "FAIL"
        label = "PHOSITA FAIL %"
    elif eval_choice == "Citation Text":
        scored = work[work["citation_verdict"].isin(["PASS", "FAIL"])].copy()
        scored["fail"] = scored["citation_verdict"] == "FAIL"
        label = "Citation FAIL %"
    else:
        mask = work["phosita_verdict"].isin(["PASS", "FAIL"]) | work["citation_verdict"].isin(["PASS", "FAIL"])
        scored = work[mask].copy()
        scored["fail"] = (scored["phosita_verdict"] == "FAIL") | (scored["citation_verdict"] == "FAIL")
        label = "Either FAIL %"

    # Exclude Unknown dimensions from heatmap
    scored = scored[
        (scored["relationship"] != "Unknown") & (scored["claim_type"] != "Unknown")
    ]

    if scored.empty:
        st.warning("No data available for the selected eval and known dimensions.")
        return

    # Build pivot: rows = claim profile, columns = relationship
    agg = scored.groupby(["profile", "relationship"])["fail"].agg(["mean", "count"])
    agg["display"] = agg.apply(
        lambda r: f"{r['mean']:.0%}  (n={int(r['count'])})"
        if r["count"] >= 3
        else f"n={int(r['count'])} ⚠",
        axis=1,
    )

    REL_ORDER = [c for c in ["Anticipation", "Implicit", "Novel"] if c in agg.index.get_level_values("relationship")]
    PROFILE_ORDER = ["Method · Short", "Method · Long", "System · Short", "System · Long"]
    profile_order = [p for p in PROFILE_ORDER if p in agg.index.get_level_values("profile")]

    pct_pivot = (
        agg["mean"]
        .unstack("relationship")
        .reindex(index=profile_order, columns=REL_ORDER)
    )
    display_pivot = (
        agg["display"]
        .unstack("relationship")
        .reindex(index=profile_order, columns=REL_ORDER)
        .fillna("—")
    )

    st.subheader(f"Heatmap: {label} by Dimension")
    styled = display_pivot.style.background_gradient(
        gmap=pct_pivot,
        cmap="RdYlGn_r",
        vmin=0.0,
        vmax=1.0,
        axis=None,
    )
    st.dataframe(styled, use_container_width=True)

    # Column averages as metric tiles
    st.subheader("Average FAIL Rate by Prior Art Relationship")
    cols = st.columns(len(REL_ORDER))
    for col, rel in zip(cols, REL_ORDER):
        rel_data = scored[scored["relationship"] == rel]
        rate = rel_data["fail"].mean() if not rel_data.empty else 0.0
        col.metric(rel, f"{rate:.0%}", f"n={len(rel_data)}")

    st.caption(
        "28 of 87 traces use human-verified dimensions · "
        "Remaining 59 use inferred dimensions "
        "(claim_type: 100% accurate, claim_length: 89%, relationship: ~61%) · "
        "Cells with n<3 flagged with ⚠"
    )
```

- [ ] **Step 2: Run and verify Heatmap tab**

```
streamlit run scripts/run_dashboard.py
```

Click **🔥 Error Heatmap**. Expected:
- Radio buttons for PHOSITA / Citation / Both
- A colour-coded table (green → red) with cells like "73%  (n=11)"
- Three metric tiles below showing average FAIL rate per relationship type
- Caption with dimension accuracy note

Toggle between the three eval options — counts and colours should change.

- [ ] **Step 3: Commit**

```
git add scripts/run_dashboard.py
git commit -m "feat(dashboard): add Error Heatmap tab — pandas Styler with eval toggle"
```

---

## Task 5: Dashboard — PM Implications tab

**Files:**
- Modify: `scripts/run_dashboard.py`

Replace the `render_implications` stub with the full static content.

- [ ] **Step 1: Replace `render_implications` in `scripts/run_dashboard.py`**

Find `def render_implications() -> None:` and replace the body with:

```python
def render_implications() -> None:
    """Tab 3: PM-facing priority matrix and action narrative (static content)."""
    st.subheader("What to Do — Priority × Fix Type")

    st.markdown("""
| Issue | Priority | Fix Type | Effort |
|---|---|---|---|
| **PHOSITA failures on Implicit prior art (73% FAIL)** | 🔴 P0 | Prompt iteration | 1–2 sprints |
| **Citation text paraphrasing (45% FAIL)** | 🟠 P1 | Prompt fix *(v2 deployed — verify)* | Done |
| **System claims fail harder than Method (60% vs 43%)** | 🔴 P1 | Architecture: claim-type routing | 2–4 sprints |
| **Overall quality below production threshold (~38% clean)** | 🟣 P2 | Fine-tuning | 4–8 sprints |
    """)

    with st.expander("What each fix type means"):
        st.markdown("""
**Prompt fix** — change the system prompt or output schema instruction.
Reversible, fast, cheap. No model retraining. Results measurable within
days by re-running the eval scripts.

**Architecture change** — separate prompt paths or agents for different
input types (e.g. Method vs System claims). Requires engineering work
but no training data.

**Fine-tuning** — train the model on high-quality labelled examples.
Highest quality ceiling, highest cost and lead time. Do this after
prompt fixes plateau.
        """)

    st.divider()

    col_act, col_wait = st.columns(2)

    with col_act:
        st.subheader("Act now")
        st.markdown("""
1. **Monitor Implicit prior art cases** — consider adding a confidence
   flag in the PatentDiff UI for outputs where prior art relationship
   is Implicit. These have a 73% PHOSITA failure rate.

2. **Verify the citation fix landed** — re-run `python scripts/run_citation_eval.py`
   and `python scripts/run_eval_vs_human.py` after the v2 prompt is
   deployed to production. The fix should lift citation TNR above 64%.

3. **Spec a claim-type router** — route System claims through a separate
   prompt that handles apparatus-style elements differently from method steps.
   This alone could drop System claim FAIL rate from 60% toward the Method
   baseline of 43%.
        """)

    with col_wait:
        st.subheader("Wait on")
        st.markdown("""
- **Anticipation cases are performing well** (0–17% FAIL rate). Don't
  change the prompt for these — over-engineering what works tends to
  introduce regressions in other categories.

- **Fine-tuning** — wait until prompt and architecture fixes have been
  applied and have plateaued. Collect high-quality labelled examples in
  parallel using the annotation tool so the dataset is ready when needed.
        """)
```

- [ ] **Step 2: Run and verify PM Implications tab**

```
streamlit run scripts/run_dashboard.py
```

Click **📋 PM Implications**. Expected:
- Priority matrix table with four rows, colour-coded priority badges
- Collapsible "What each fix type means" section
- Two-column layout: "Act now" (3 numbered actions) and "Wait on" (2 bullets)

- [ ] **Step 3: Commit**

```
git add scripts/run_dashboard.py
git commit -m "feat(dashboard): add PM Implications tab — priority matrix and action narrative"
```

---

## Task 6: Smoke test — full run verification

**Files:**
- Read: `scripts/run_dashboard.py`

- [ ] **Step 1: Run the full test suite to confirm dimension_tagger tests still pass**

```
python -m pytest tests/test_dimension_tagger.py -v
```

Expected: `19 passed`

- [ ] **Step 2: Verify the dashboard loads cleanly on all three tabs**

```
streamlit run scripts/run_dashboard.py
```

Open http://localhost:8501. Walk through all three tabs:

| Tab | What to check |
|---|---|
| 📊 Summary | 4 KPI metrics show real % values; co-occurrence table has non-zero cells |
| 🔥 Error Heatmap | Heatmap renders with colours; "Implicit" column is darkest red; toggle changes values |
| 📋 PM Implications | Priority table renders with emoji badges; both columns of actions visible |

- [ ] **Step 3: Confirm KPIs match existing reports**

Run:
```
python scripts/run_phosita_vs_human.py
python scripts/run_eval_vs_human.py
```

The PHOSITA FAIL % on the dashboard (43%) should match the overall FAIL rate in
`traces/phosita_eval_full.jsonl` (v3 entries). The citation FAIL % should match
`traces/eval_vs_human_report.md`.

- [ ] **Step 4: Final commit**

```
git add .
git commit -m "feat(dashboard): complete error rate dashboard — dimension tagger + 3-tab Streamlit app"
```
