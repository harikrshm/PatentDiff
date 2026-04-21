"""Convert traces/traces.jsonl to traces/traces.xlsx with two sheets:

  runs     — one row per analysis run (flattened metadata + overall opinion)
  elements — one row per claim element (one run produces N element rows)

Usage:
    python scripts/traces_to_xlsx.py
    python scripts/traces_to_xlsx.py --input traces/traces.jsonl --output traces/traces.xlsx
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def load_records(jsonl_path: Path) -> list[dict]:
    records = []
    with open(jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Warning: skipping line {i} — {e}", file=sys.stderr)
    return records


def build_runs_df(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        inp = r.get("inputs", {})
        src = inp.get("source_patent", {})
        tgt = inp.get("target_patent", {})
        llm = r.get("llm_response", {})
        parsed = r.get("parsed_output") or {}
        warnings = r.get("truncation_warnings", [])

        src_text = (
            f"Label: {src.get('label', '')}\n\n"
            f"Independent Claim:\n{src.get('independent_claim', '')}\n\n"
            f"Specification:\n{src.get('specification', '')}"
        )
        tgt_text = (
            f"Label: {tgt.get('label', '')}\n\n"
            f"Independent Claim:\n{tgt.get('independent_claim', '')}\n\n"
            f"Specification:\n{tgt.get('specification', '')}"
        )

        rows.append({
            "run_id":              r.get("run_id", ""),
            "timestamp":           r.get("timestamp", ""),
            "status":              r.get("status", ""),
            "error":               r.get("error", ""),
            "source_patent":       src_text,
            "target_patent":       tgt_text,
            "model":               llm.get("model", ""),
            "tokens_input":        llm.get("tokens_input", ""),
            "tokens_output":       llm.get("tokens_output", ""),
            "latency_ms":          llm.get("latency_ms", ""),
            "overall_opinion":     parsed.get("overall_opinion", ""),
            "truncation_warnings": "; ".join(warnings) if warnings else "",
        })
    return pd.DataFrame(rows)


def build_elements_df(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        run_id    = r.get("run_id", "")
        timestamp = r.get("timestamp", "")
        inp       = r.get("inputs", {})
        src_label = inp.get("source_patent", {}).get("label", "")
        tgt_label = inp.get("target_patent", {}).get("label", "")
        parsed    = r.get("parsed_output") or {}

        for em in parsed.get("element_mappings", []):
            rows.append({
                "run_id":             run_id,
                "timestamp":          timestamp,
                "source_label":       src_label,
                "target_label":       tgt_label,
                "element_number":     em.get("element_number", ""),
                "element_text":       em.get("element_text", ""),
                "corresponding_text": em.get("corresponding_text", ""),
                "novelty":            em.get("novelty", ""),
                "inventive_step":     em.get("inventive_step", ""),
                "verdict":            em.get("verdict", ""),
                "comment":            em.get("comment", ""),
            })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Convert traces.jsonl to traces.xlsx")
    parser.add_argument("--input",  default="traces/traces.jsonl", help="Path to JSONL file")
    parser.add_argument("--output", default="traces/traces.xlsx",  help="Path to output XLSX")
    args = parser.parse_args()

    input_path  = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {input_path} ...")
    records = load_records(input_path)
    print(f"  {len(records)} records loaded.")

    runs_df     = build_runs_df(records)
    elements_df = build_elements_df(records)

    print(f"Writing {output_path} ...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        runs_df.to_excel(writer, sheet_name="runs", index=False)
        elements_df.to_excel(writer, sheet_name="elements", index=False)

    print(f"Done.")
    print(f"  runs sheet:     {len(runs_df)} rows")
    print(f"  elements sheet: {len(elements_df)} rows")


if __name__ == "__main__":
    main()
