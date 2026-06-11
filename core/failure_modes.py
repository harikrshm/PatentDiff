# core/failure_modes.py
"""Failure-mode breakdown for the dashboard's Block 2.

Among a trace set's eval-FAIL traces, tally the human-annotated failure modes
(taxonomy) and surface an 'Unverified / untagged' bucket for FAILs with no FAIL
annotation. Reuses the frozen eval verdicts (core.eval_delta) + the human
annotations (core.annotation); computes no new scores.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.annotation import load_annotations, load_taxonomy
from core.eval_delta import load_verdict_map
from core.workbench_data import list_trace_sets

REPO_ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"
TAXONOMY_PATH = REPO_ROOT / "failure_taxonomy.json"
UNTAGGED_LABEL = "Unverified / untagged"


def _mode_labels(taxonomy_path: Path) -> dict:
    tax = load_taxonomy(taxonomy_path)
    return {c["id"]: c["name"] for c in tax.get("failure_categories", [])}


def failure_mode_breakdown(traces_dir: Path, trace_set: str,
                           annotations_path: Path = ANNOTATIONS_PATH,
                           taxonomy_path: Path = TAXONOMY_PATH
                           ) -> list[tuple[str, int]]:
    """Return [(label, count), ...] — failure modes among the set's FAILs, sorted
    desc, with the untagged bucket last. Empty list if the set has no eval FAILs.
    """
    sets = {s.name: s for s in list_trace_sets(Path(traces_dir))}
    ts = sets.get(trace_set)
    set_run_ids: set[str] = set()
    eval_fail: set[str] = set()
    if ts is not None:
        for p in (ts.phosita_path, ts.citation_path):
            for rid, verdict in load_verdict_map(p).items():
                set_run_ids.add(rid)
                if verdict == "FAIL":
                    eval_fail.add(rid)

    anns = load_annotations(annotations_path)
    labels = _mode_labels(taxonomy_path)
    counts: Counter = Counter()
    tagged: set[str] = set()
    for rid in set_run_ids:
        rec = anns.get(rid)
        if rec is None or rec.verdict != "FAIL":
            continue
        modes = (rec.failure_modes or rec.open_coded_failure_modes) or []
        if not modes:
            continue
        tagged.add(rid)
        for m in modes:
            counts[labels.get(m, m)] += 1

    out = counts.most_common()
    untagged = len(eval_fail - tagged)
    if untagged:
        out.append((UNTAGGED_LABEL, untagged))
    return out
