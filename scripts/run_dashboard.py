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
