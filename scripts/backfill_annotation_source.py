#!/usr/bin/env python
"""One-off backfill: set source="human" or source="coded" on every row in
traces/traces_annotations.jsonl that is missing the field.

Rules:
- If `comment` starts with "[code]"  -> source="coded"
- Otherwise                          -> source="human"

Idempotent: rows that already have a `source` value are left alone, so re-running
this script is safe and a no-op after the first run.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = REPO_ROOT / "traces" / "traces_annotations.jsonl"


def main() -> int:
    if not ANNOTATIONS_PATH.exists():
        print(f"Annotations file not found: {ANNOTATIONS_PATH}", file=sys.stderr)
        return 1

    with open(ANNOTATIONS_PATH, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    set_count = 0
    preserved_count = 0
    for row in rows:
        if "source" in row and row["source"] in ("human", "coded"):
            preserved_count += 1
            continue
        comment = row.get("comment") or ""
        row["source"] = "coded" if comment.startswith("[code]") else "human"
        set_count += 1

    if set_count == 0:
        print("No rows needed backfill — every row already has a valid source.")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = ANNOTATIONS_PATH.with_suffix(f".jsonl.backup.backfill.{ts}")
    shutil.copy2(ANNOTATIONS_PATH, backup_path)
    print(f"Backup written: {backup_path.relative_to(REPO_ROOT)}")

    with open(ANNOTATIONS_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"Backfilled source on {set_count} row(s); preserved on {preserved_count}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
