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
    """Yield parsed JSON objects from a JSONL file; skip blank/corrupt lines; empty if missing."""
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
        # annotations for run_ids absent from traces are skipped (no inferred base to override)
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
    columns = ["run_id", "claim_type", "claim_length", "relationship",
               "dim_source", "phosita_verdict", "citation_verdict"]
    return pd.DataFrame(rows, columns=columns)
