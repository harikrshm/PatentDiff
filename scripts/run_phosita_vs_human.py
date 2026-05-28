#!/usr/bin/env python
"""Compare the absent_phosita_reasoning coded eval against human annotations.

Loads phosita_eval_full.jsonl (produced by scripts/run_phosita_eval.py) and
the human annotations from traces/traces_annotations.jsonl. Joins on run_id,
computes the confusion matrix, TPR, and TNR for the
`absent_phosita_reasoning` failure mode, and writes a markdown report.

Test rows (annotation comment starts with "Test") are excluded from the
sample, matching the convention in scripts/run_eval_vs_human.py.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.eval_vs_human import classify_coded, classify_human, confusion, tpr, tnr
from core.phosita_eval import JUDGE_MODEL, PROMPT_VERSION

DEFAULT_EVAL_PATH = REPO_ROOT / "traces" / "phosita_eval_full.jsonl"
DEFAULT_ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"
DEFAULT_REPORT_PATH = REPO_ROOT / "traces" / "phosita_vs_human_report.md"

FAILURE_MODE_KEY = "absent_phosita_reasoning"


def load_human_annotations(path: Path) -> dict:
    annotations = {}
    with open(path, encoding="utf-8") as f:
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


def load_coded_eval(path: Path) -> dict:
    coded = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # Keep only rows for the current prompt_version.
            ver = (row.get("config") or {}).get("prompt_version")
            if ver != PROMPT_VERSION:
                continue
            coded[row["run_id"]] = row
    return coded


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
    return f"""# Absent PHOSITA Reasoning - Coded Eval vs Human Eval

**Sample:** {sample_size} human-annotated traces (`source="human"`, comment does not start with "Test", matching coded eval entry exists)
**Positive class:** human tagged `{FAILURE_MODE_KEY}`
**Coded mapping:** FAIL -> positive; PASS -> negative
**Judge model:** {JUDGE_MODEL}
**Prompt version:** {PROMPT_VERSION}

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** | {c['tp']:>14} | {c['fp']:>14} |
| **Coded negative** | {c['fn']:>14} | {c['tn']:>14} |

## Metrics

{tpr_line}
{tnr_line}
"""


def run(eval_path: Path, annotations_path: Path, report_path: Path) -> int:
    annotations = load_human_annotations(annotations_path)
    coded = load_coded_eval(eval_path)

    pairs = []
    fp_run_ids = []
    fn_run_ids = []
    missing_coded = []
    for run_id, ann in annotations.items():
        if run_id not in coded:
            missing_coded.append(run_id)
            continue
        human_label = classify_human(ann.get("failure_modes"), FAILURE_MODE_KEY)
        coded_label = classify_coded(coded[run_id]["verdict"])
        pairs.append((human_label, coded_label))
        if human_label == 0 and coded_label == 1:
            fp_run_ids.append(run_id)
        elif human_label == 1 and coded_label == 0:
            fn_run_ids.append(run_id)

    c = confusion(pairs)
    t_pr = tpr(c["tp"], c["fn"])
    t_nr = tnr(c["tn"], c["fp"])

    report = render_report(c, t_pr, t_nr, sample_size=len(pairs))
    if fp_run_ids or fn_run_ids:
        report += "\n## Disagreement run_ids (for spot-check)\n\n"
        if fp_run_ids:
            report += "**False positives (coded FAIL, human did not tag phosita):**\n"
            for rid in fp_run_ids:
                report += f"- {rid}\n"
            report += "\n"
        if fn_run_ids:
            report += "**False negatives (human tagged phosita, coded PASS):**\n"
            for rid in fn_run_ids:
                report += f"- {rid}\n"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    if missing_coded:
        print(
            f"WARNING: {len(missing_coded)} human-annotated run_ids have no coded eval entry "
            f"and were excluded from the sample.",
            file=sys.stderr,
        )
    try:
        rel = report_path.relative_to(REPO_ROOT)
    except ValueError:
        rel = report_path
    print(f"Wrote {rel}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    return run(args.eval, args.annotations, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
