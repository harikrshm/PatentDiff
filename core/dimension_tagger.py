"""Infers claim dimensions from trace data for the error rate dashboard.

Functions take the full trace dict and return a string label.
Human-annotated dimensions in traces_annotations.jsonl override these
inferences in the dashboard — these are fallbacks for un-annotated traces.
"""
from __future__ import annotations

import re


def infer_claim_type(trace: dict) -> str:
    """Return 'Method', 'System', or 'Unknown' from the source independent claim.

    Note: process-style method claims (e.g. "A process for...") are not
    recognized and may be misclassified as 'Unknown'.
    """
    raw = (
        ((trace.get("inputs") or {}).get("source_patent") or {})
        .get("independent_claim", "")
    )
    # Strip leading numbers and dots (e.g. "1. A method")
    claim = re.sub(r"^[\d\s.]+", "", raw).strip().lower()
    if not claim:
        return "Unknown"
    # Only scan the claim preamble — keyword matches deeper in the body are unreliable.
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
    n_y = sum(1 for e in mappings if (e or {}).get("novelty") == "Y")
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
