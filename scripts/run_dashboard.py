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
from core.phosita_eval import PROMPT_VERSION as PHOSITA_PROMPT_VERSION

TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
PHOSITA_PATH = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"
CITATION_PATH = REPO_ROOT / "traces" / "citation_text_eval_full.jsonl"
ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"

st.set_page_config(page_title="PatentDiff — Error Rate Dashboard", layout="wide")
st.title("PatentDiff — Error Rate Dashboard")


def _iter_jsonl(path: Path):
    """Yield parsed JSON objects from a JSONL file, skipping blank/corrupt lines.

    Returns nothing if the file does not exist.
    """
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


@st.cache_data
def _load_data() -> pd.DataFrame:
    """Load and merge all eval sources into one DataFrame.

    One row per trace that has at least one eval result. Dimensions are
    inferred from trace data; human-annotated dimensions override where present.
    """
    # 1. Load traces and infer dimensions for all
    traces: dict[str, dict] = {}
    for t in _iter_jsonl(TRACES_PATH):
        if "run_id" in t:
            traces[t["run_id"]] = t

    if not traces:
        st.error(f"No traces found. Expected data at: {TRACES_PATH}")
        st.stop()

    dims: dict[str, dict] = {rid: tag_trace(t) for rid, t in traces.items()}

    # 2. Override with human-verified dimensions where available
    for ann in _iter_jsonl(ANNOTATIONS_PATH):
        if ann.get("phase") == 3 and ann.get("dimensions"):
            rid = ann.get("run_id")
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
    for r in _iter_jsonl(PHOSITA_PATH):
        if (r.get("config") or {}).get("prompt_version") == PHOSITA_PROMPT_VERSION:
            rid = r.get("run_id")
            if rid and r.get("verdict"):
                phosita[rid] = r["verdict"]

    # 4. Load citation verdicts
    citation: dict[str, str] = {}
    for r in _iter_jsonl(CITATION_PATH):
        rid = r.get("run_id")
        if rid and r.get("verdict"):
            citation[rid] = r["verdict"]

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
    if not REL_ORDER:
        st.warning("No recognised prior-art relationships in the data.")
        return
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

    n_total = len(df)
    n_human = int((df["dim_source"] == "human").sum())
    st.caption(
        f"{n_human} of {n_total} traces use human-verified dimensions · "
        "Remaining use inferred dimensions "
        "(claim_type: 100% accurate, claim_length: 89%, relationship: ~61%) · "
        "Cells with n<3 flagged with ⚠"
    )


def render_implications() -> None:
    """Tab 3: PM-facing priority matrix and action narrative (static content)."""
    st.subheader("What to Do — Priority × Fix Type")

    st.markdown("""
| Issue | Priority | Fix Type | Effort |
|---|---|---|---|
| **PHOSITA failures on Implicit prior art (73% FAIL)** | 🔴 P0 | Prompt iteration | 1–2 sprints |
| **Citation text paraphrasing (45% FAIL)** | 🟠 P1 | Prompt fix *(v2 deployed — verify)* | Done |
| **System claims fail harder than Method (60% vs 43%)** | 🔴 P1 | Architecture: claim-type routing | 2–4 sprints |
| **Overall quality below production threshold (~25% clean)** | 🟣 P2 | Fine-tuning | 4–8 sprints |
    """)

    st.caption(
        "Failure rates above are product judgement anchored on the 28 "
        "human-annotated traces (the ground-truth subset). The live full-corpus "
        "rates in the Summary and Heatmap tabs differ — see those tabs for "
        "current automated numbers."
    )

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


# ── Entry point ───────────────────────────────────────────────────────────────
df = _load_data()
tab1, tab2, tab3 = st.tabs(["📊 Summary", "🔥 Error Heatmap", "📋 PM Implications"])
with tab1:
    render_summary(df)
with tab2:
    render_heatmap(df)
with tab3:
    render_implications()
