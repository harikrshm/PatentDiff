#!/usr/bin/env python3
"""
Auto-map Phase 1 open-coded failure modes to Phase 3 taxonomy categories
using the mapping table provided by user.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Mapping table (old mode -> new category ID)
MAPPING_TABLE = {
    "big_claim": "failed_claim_construction",
    "claim_decomposition": "failed_claim_construction",
    "claim element decomposition": "failed_claim_construction",
    "correspond text": "citation_text",
    "diff in tech": "absent_phosita_reasoning",
    "diff nov and invent": "absent_phosita_reasoning",
    "hallucination_inventive step": "absent_phosita_reasoning",
    "inventive_why?": "absent_phosita_reasoning",
    "mark_inventive step": "absent_phosita_reasoning",
    "narrow inventive step": "absent_phosita_reasoning",
    "person_skilled": "absent_phosita_reasoning",
    "pre+post processing steps": "unnecessary_evaluation",
    "pre_processing  step": "unnecessary_evaluation",
    "pre_processing mapping": "unnecessary_evaluation",
    "preamble_missed": "unnecessary_evaluation",
    "term_consistent": "failed_claim_construction",
    "toke_limit": None,  # Skip
    "token_limit": None,  # Skip
    "verbatim_term": "failed_claim_construction",
}

def main():
    jsonl_file = Path('traces/traces_annotations.jsonl')

    if not jsonl_file.exists():
        print(f"Error: {jsonl_file} not found")
        sys.exit(1)

    print("Reading Phase 1 annotations and creating Phase 3 mappings...")

    phase3_records = []
    mapped_count = 0
    skipped_token_limit = 0

    with open(jsonl_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)

                # Only process Phase 1 records
                if record.get('phase') != 1:
                    continue

                # Skip token_limit traces
                old_modes = record.get('open_coded_failure_modes', [])
                if 'token_limit' in old_modes or 'toke_limit' in old_modes:
                    skipped_token_limit += 1
                    continue

                # Map old modes to new category IDs
                new_modes = set()
                for old_mode in old_modes:
                    if old_mode in MAPPING_TABLE:
                        new_cat = MAPPING_TABLE[old_mode]
                        if new_cat:  # Skip None entries
                            new_modes.add(new_cat)

                # Create Phase 3 record
                phase3_record = {
                    'run_id': record['run_id'],
                    'phase': 3,
                    'dimensions': record.get('dimensions'),
                    'verdict': record['verdict'],
                    'failure_modes': list(new_modes),
                    'open_coded_failure_modes': old_modes,  # Preserve for traceability
                    'comment': record.get('comment', ''),
                    'reviewed': False,  # Needs manual review
                    'timestamp': datetime.now().isoformat()
                }

                phase3_records.append(phase3_record)
                mapped_count += 1

            except json.JSONDecodeError as e:
                print(f"Warning: Skipped malformed JSON: {e}")

    # Append Phase 3 records to file
    print(f"Appending {mapped_count} Phase 3 records to {jsonl_file}...")

    with open(jsonl_file, 'a') as f:
        for record in phase3_records:
            json.dump(record, f)
            f.write('\n')

    print(f"\nAuto-mapping complete:")
    print(f"  - {mapped_count} Phase 3 records created")
    print(f"  - {skipped_token_limit} token_limit traces skipped")
    print(f"  - All records appended to {jsonl_file}")
    print(f"\nNext: Review Phase 3 records in annotation tool and mark reviewed")

if __name__ == '__main__':
    main()
