"""Seed traces/eval_history.jsonl from existing eval files. Idempotent."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.eval_history import backfill_from_eval_files  # noqa: E402

if __name__ == "__main__":
    added = backfill_from_eval_files(REPO_ROOT / "traces")
    print(f"Backfilled {added} eval-history record(s).")
