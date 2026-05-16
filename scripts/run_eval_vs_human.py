#!/usr/bin/env python
"""Compare the citation_text coded eval against human annotations.

Loads `source="human"` rows from traces/traces_annotations.jsonl (excluding the
3 development-only test rows whose comments start with "Test"), runs the coded
eval on each corresponding trace, computes the confusion matrix, TPR, and TNR,
and writes a markdown report to traces/eval_vs_human_report.md.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.citation_eval import evaluate_trace, NGRAM_N, THRESHOLD
from core.eval_vs_human import classify_coded, classify_human, confusion, tpr, tnr

TRACES_PATH = REPO_ROOT / "traces" / "traces.jsonl"
ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"
REPORT_PATH = REPO_ROOT / "traces" / "eval_vs_human_report.md"

EXPECTED_HUMAN_SAMPLE_SIZE = 30


def load_human_annotations() -> dict:
    annotations = {}
    with open(ANNOTATIONS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("source", "human") != "human":
                continue
            comment = row.get("comment") or ""
            if comment.startswith("Test"):
                continue
            annotations[row["run_id"]] = row
    return annotations


def load_traces() -> dict:
    traces = {}
    with open(TRACES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            trace = json.loads(line)
            traces[trace["run_id"]] = trace
    return traces


def format_percent(value):
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def render_report(c: dict, t_pr, t_nr, sample_size: int) -> str:
    tpr_denom = c["tp"] + c["fn"]
    tnr_denom = c["tn"] + c["fp"]
    tpr_line = (
        f"- **TPR (sensitivity)** = TP / (TP + FN) = {c['tp']} / {tpr_denom} = "
        f"{format_percent(t_pr) if t_pr is not None else 'N/A (no positives in sample)'}"
    )
    tnr_line = (
        f"- **TNR (specificity)** = TN / (TN + FP) = {c['tn']} / {tnr_denom} = "
        f"{format_percent(t_nr) if t_nr is not None else 'N/A (no negatives in sample)'}"
    )
    return f"""# Citation Text - Coded Eval vs Human Eval

**Sample:** {sample_size} human-annotated traces (`source="human"`, real `run_id`, comment does not start with "Test")
**Positive class:** human tagged `citation_text`
**Coded mapping:** FAIL -> positive; PASS and NO_CITATIONS -> negative
**Config:** ngram_n={NGRAM_N}, threshold={THRESHOLD}

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** | {c['tp']:>14} | {c['fp']:>14} |
| **Coded negative** | {c['fn']:>14} | {c['tn']:>14} |

## Metrics

{tpr_line}
{tnr_line}
"""


def main() -> int:
    annotations = load_human_annotations()
    traces = load_traces()

    pairs = []
    skipped = []
    for run_id, ann in annotations.items():
        if run_id not in traces:
            skipped.append(run_id)
            continue
        trace = traces[run_id]
        coded = evaluate_trace(trace)
        human_label = classify_human(ann.get("failure_modes"))
        coded_label = classify_coded(coded["verdict"])
        pairs.append((human_label, coded_label, run_id))

    if len(pairs) != EXPECTED_HUMAN_SAMPLE_SIZE:
        print(
            f"ERROR: expected {EXPECTED_HUMAN_SAMPLE_SIZE} human-annotated traces, "
            f"got {len(pairs)}. Skipped {len(skipped)} run_ids missing from traces.jsonl.",
            file=sys.stderr,
        )
        return 1

    c = confusion(pairs)
    t_pr = tpr(c["tp"], c["fn"])
    t_nr = tnr(c["tn"], c["fp"])

    report = render_report(c, t_pr, t_nr, sample_size=len(pairs))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"Wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
