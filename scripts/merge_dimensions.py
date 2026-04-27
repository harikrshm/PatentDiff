#!/usr/bin/env python3
"""
Merge trace dimensions from traces.xlsx into traces.jsonl
Reads columns M (claim_type), N (claim_length), O (relationship)
and adds them to matching run_id records in traces.jsonl
"""

import json
import pandas as pd
import os
import sys
from pathlib import Path

def main():
    # File paths
    excel_file = Path('traces/traces.xlsx')
    jsonl_input = Path('traces/traces.jsonl')
    jsonl_backup = Path('traces/traces.jsonl.backup')
    jsonl_output = Path('traces/traces.jsonl.temp')

    # Verify input files exist
    if not excel_file.exists():
        print(f"Error: {excel_file} not found")
        sys.exit(1)
    if not jsonl_input.exists():
        print(f"Error: {jsonl_input} not found")
        sys.exit(1)

    print(f"Reading dimensions from {excel_file}...")

    # Read Excel file - use 'runs' sheet
    df = pd.read_excel(excel_file, sheet_name='runs')

    # Build dimensions lookup by run_id
    dimensions_map = {}
    for idx, row in df.iterrows():
        run_id = row['run_id'] if pd.notna(row['run_id']) else None
        if not run_id:
            continue

        claim_type = str(row['Claim type ']) if pd.notna(row['Claim type ']) else None
        claim_length = str(row['Claim length']) if pd.notna(row['Claim length']) else None
        relationship = str(row['Disclosure relationship']) if pd.notna(row['Disclosure relationship']) else None

        dimensions_map[run_id] = {
            "claim_type": claim_type,
            "claim_length": claim_length,
            "relationship": relationship
        }

    print(f"Found {len(dimensions_map)} dimension records from Excel")

    # Merge into JSONL
    print(f"Merging into {jsonl_input}...")
    merged_count = 0
    skipped_count = 0

    with open(jsonl_input, 'r') as f_in, open(jsonl_output, 'w') as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue

            try:
                trace = json.loads(line)
                run_id = trace.get('run_id')

                if run_id in dimensions_map:
                    trace['dimensions'] = dimensions_map[run_id]
                    merged_count += 1
                else:
                    skipped_count += 1

                json.dump(trace, f_out)
                f_out.write('\n')
            except json.JSONDecodeError as e:
                print(f"Warning: Skipped malformed JSON line: {e}")
                skipped_count += 1

    # Backup original and replace
    if jsonl_backup.exists():
        jsonl_backup.unlink()
    jsonl_input.rename(jsonl_backup)
    jsonl_output.rename(jsonl_input)

    print(f"\nMerge complete:")
    print(f"  [OK] {merged_count} traces updated with dimensions")
    print(f"  [-] {skipped_count} traces skipped (no match or malformed)")
    print(f"  [OK] Original backed up to {jsonl_backup}")
    print(f"  [OK] Updated file: {jsonl_input}")

if __name__ == '__main__':
    main()
