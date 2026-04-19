import json
import os


def append_trace(record: dict, filepath: str = "traces/traces.jsonl") -> None:
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
