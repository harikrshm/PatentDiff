#!/usr/bin/env python
"""Merge citation_text coded-eval results into traces_annotations.jsonl
so the annotation tool can display them alongside human annotations.

- Backs up the current annotations file before writing.
- Only inserts coded-eval rows for run_ids that have NO existing annotation
  (human annotations are never overwritten).
- Each coded-eval row is marked with a `[code]` prefix in the comment and
  saved with reviewed=False so it shows as unreviewed in the tool.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.annotation import load_annotations, save_annotations, AnnotationRecord

ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"
EVAL_PATH = REPO_ROOT / "traces" / "citation_text_eval.jsonl"


def make_comment(eval_row: dict) -> str:
    verdict = eval_row["verdict"]
    n = eval_row["num_elements_scored"]
    q = eval_row["num_quoted"]
    s = eval_row["num_summarised"]
    cfg = eval_row.get("config", {})
    base = (
        f"[code] citation_text eval: verdict={verdict}, "
        f"scored={n} quoted={q} summarised={s}, "
        f"threshold={cfg.get('threshold')}, ngram_n={cfg.get('ngram_n')}"
    )
    if verdict == "NO_CITATIONS":
        base += " (no non-empty corresponding_text fields to evaluate)"
    return base


def eval_to_annotation(eval_row: dict) -> AnnotationRecord:
    verdict = eval_row["verdict"]
    # NO_CITATIONS maps to PASS for the annotation tool — the citation_text
    # failure mode cannot apply when there are no citations to check.
    if verdict == "FAIL":
        record_verdict = "FAIL"
        failure_modes = ["citation_text"]
    else:
        record_verdict = "PASS"
        failure_modes = []

    return AnnotationRecord(
        run_id=eval_row["run_id"],
        phase=3,
        failure_modes=failure_modes,
        verdict=record_verdict,
        comment=make_comment(eval_row),
        reviewed=False,
        timestamp=datetime.now(timezone.utc).isoformat(),
        dimensions=None,
        source="coded",
    )


def main() -> int:
    if not EVAL_PATH.exists():
        print(f"Eval file not found: {EVAL_PATH}", file=sys.stderr)
        print("Run scripts/run_citation_eval.py first.", file=sys.stderr)
        return 1

    existing = load_annotations(ANNOTATIONS_PATH)
    print(f"Existing annotations: {len(existing)}")

    # Backup
    if ANNOTATIONS_PATH.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = ANNOTATIONS_PATH.with_suffix(f".jsonl.backup.{ts}")
        shutil.copy2(ANNOTATIONS_PATH, backup_path)
        print(f"Backup written: {backup_path.relative_to(REPO_ROOT)}")

    with open(EVAL_PATH, encoding="utf-8") as f:
        eval_rows = [json.loads(line) for line in f if line.strip()]
    print(f"Coded eval rows: {len(eval_rows)}")

    added = 0
    skipped_existing = 0
    by_verdict = {"PASS": 0, "FAIL": 0, "NO_CITATIONS": 0}
    for row in eval_rows:
        run_id = row["run_id"]
        if run_id in existing:
            skipped_existing += 1
            continue
        existing[run_id] = eval_to_annotation(row)
        added += 1
        by_verdict[row["verdict"]] += 1

    save_annotations(ANNOTATIONS_PATH, existing)

    print(f"\nAdded {added} coded-eval annotations")
    print(f"  PASS         : {by_verdict['PASS']}")
    print(f"  FAIL         : {by_verdict['FAIL']}")
    print(f"  NO_CITATIONS : {by_verdict['NO_CITATIONS']} (mapped to PASS)")
    print(f"Skipped (already annotated by human): {skipped_existing}")
    print(f"Total annotations now: {len(existing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
