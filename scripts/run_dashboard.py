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


# Minimal render to verify loader works
df = _load_data()
st.write(f"Loaded {len(df)} traces. Columns: {list(df.columns)}")
st.dataframe(df.head(10))
