#!/usr/bin/env python3
"""Phase 2: Axial Coding - Generate Failure Taxonomy from Phase 1 Open Codes"""

import json
from collections import Counter, defaultdict

# Load annotations
annotations = []
with open('traces/traces_annotations.jsonl', 'r') as f:
    for line in f:
        if line.strip():
            annotations.append(json.loads(line))

print(f"Total annotations: {len(annotations)}\n")

# Filter out token_limit errors
filtered_annotations = []
for ann in annotations:
    modes = ann.get('open_coded_failure_modes', [])
    # Remove token_limit/toke_limit
    cleaned_modes = [m for m in modes if 'token_limit' not in m.lower() and m.lower() != 'toke_limit']
    ann['open_coded_failure_modes'] = cleaned_modes
    # Keep if has other modes or PASS
    if cleaned_modes or ann.get('verdict') == 'PASS':
        filtered_annotations.append(ann)
    elif not modes:
        filtered_annotations.append(ann)

print(f"Annotations after filtering token_limit: {len(filtered_annotations)}")

# Verdict distribution
pass_count = sum(1 for a in filtered_annotations if a.get('verdict') == 'PASS')
fail_count = sum(1 for a in filtered_annotations if a.get('verdict') == 'FAIL')

print(f"PASS: {pass_count}, FAIL: {fail_count}\n")

# Define failure taxonomy
failure_taxonomy = {
    "STAGE_1_INPUT_UNDERSTANDING": {
        "name": "Input Understanding & Decomposition",
        "description": "Failures in understanding input patents, decomposing claims, and identifying preprocessing steps",
        "categories": {
            "Claim Decomposition & Structure": {
                "consolidated_codes": [
                    "claim_decomposition",
                    "claim element decomposition",
                    "big_claim"
                ],
                "description": "Large claims not properly broken down into elements; elements analyzed without context of full claim",
                "impact": "HIGH - Incomplete element-by-element analysis"
            },
            "Preprocessing & Input Step Recognition": {
                "consolidated_codes": [
                    "pre_processing_mapping",
                    "pre_processing  step",
                    "pre+post_processing_steps"
                ],
                "description": "Failure to correctly classify preprocessing/postprocessing steps; treating them as novel when they are foundational",
                "impact": "HIGH - Incorrect novelty/inventive step assessment"
            },
            "Patent Document Coverage": {
                "consolidated_codes": [
                    "preamble_missed"
                ],
                "description": "Failure to analyze all sections of patent (preamble, claims, specification)",
                "impact": "MEDIUM - Incomplete analysis"
            }
        }
    },
    "STAGE_2_CLAIM_ANALYSIS": {
        "name": "Claim Language & Term Analysis",
        "description": "Failures in interpreting claim language, identifying corresponding text between patents",
        "categories": {
            "Term Interpretation & Consistency": {
                "consolidated_codes": [
                    "term_consistent",
                    "verbatim_term"
                ],
                "description": "Treating claim terms verbatim instead of using specification context; inconsistent interpretation",
                "impact": "HIGH - Misinterpretation of claim scope"
            },
            "Corresponding Text Identification": {
                "consolidated_codes": [
                    "correspond_text"
                ],
                "description": "Verdict summarizes/paraphrases rather than quoting actual corresponding text from patent",
                "impact": "MEDIUM - Traceability and verification issues"
            }
        }
    },
    "STAGE_3_NOVELTY_ASSESSMENT": {
        "name": "Novelty Assessment",
        "description": "Failures in understanding novelty concept and assessing against prior art",
        "categories": {
            "Novelty vs. Inventive Step Distinction": {
                "consolidated_codes": [
                    "diff_nov_and_invent",
                    "diff_in_tech"
                ],
                "description": "Confusion between novelty and inventive step; missing explanation of technical differences",
                "impact": "HIGH - Fundamental conceptual error"
            },
            "Person Skilled in Art Consideration": {
                "consolidated_codes": [
                    "person_skilled"
                ],
                "description": "Failure to consider assessment from perspective of person skilled in the art",
                "impact": "HIGH - Fundamental patent law requirement"
            }
        }
    },
    "STAGE_4_INVENTIVE_STEP_ASSESSMENT": {
        "name": "Inventive Step Assessment",
        "description": "All errors related to assessing whether differences from prior art constitute inventive step",
        "categories": {
            "Inventive Step Reasoning & Judgment": {
                "consolidated_codes": [
                    "hallucination_inventive_step",
                    "narrow_inventive_step",
                    "mark_inventive_step",
                    "inventive_why?"
                ],
                "description": "Incorrect marking of inventive step; hallucinated reasoning; threshold issues; missing justification",
                "impact": "CRITICAL - Direct impact on final verdict"
            }
        }
    }
}

# Build reverse mapping and count
stage_counts = defaultdict(int)
code_to_category = {}

for stage_key, stage_data in failure_taxonomy.items():
    for cat_name, cat_data in stage_data['categories'].items():
        for open_code in cat_data['consolidated_codes']:
            code_to_category[open_code.lower().strip()] = {
                'stage': stage_key,
                'stage_name': stage_data['name'],
                'category': cat_name,
                'impact': cat_data['impact']
            }

# Count failures by stage
for ann in filtered_annotations:
    modes = ann.get('open_coded_failure_modes', [])
    for mode in modes:
        normalized = mode.strip().lower()
        if normalized in code_to_category:
            mapping = code_to_category[normalized]
            stage = mapping['stage_name']
            stage_counts[stage] += 1

# Create taxonomy output
taxonomy_output = {
    "phase": 2,
    "date_generated": "2026-04-25",
    "methodology": "Axial Coding - Workflow Stage Based",
    "statistics": {
        "total_traces_analyzed": len(filtered_annotations),
        "pass_traces": pass_count,
        "fail_traces": fail_count,
        "total_failures_identified": sum(stage_counts.values()),
        "unique_consolidated_categories": 9
    },
    "exclusions": {
        "technical_errors": ["token_limit", "toke_limit"],
        "reason": "Treated as system/environmental constraint, not methodology error"
    },
    "failure_taxonomy": failure_taxonomy,
    "stage_summary": {
        stage: {
            "count": stage_counts[stage],
            "percentage": f"{100*stage_counts[stage]/sum(stage_counts.values()):.1f}%"
        }
        for stage in sorted(stage_counts.keys())
    }
}

# Save taxonomy
with open('failure_taxonomy.json', 'w') as f:
    json.dump(taxonomy_output, f, indent=2)

print("[SUCCESS] Failure taxonomy generated and saved to: failure_taxonomy.json\n")

print("="*80)
print("PHASE 2 AXIAL CODING SUMMARY")
print("="*80)
print(json.dumps(taxonomy_output['statistics'], indent=2))

print("\n\nFAILURE COUNTS BY STAGE:")
print("="*80)
total_failures = sum(stage_counts.values())
for stage in sorted(stage_counts.keys()):
    count = stage_counts[stage]
    pct = 100 * count / total_failures if total_failures > 0 else 0
    print(f"{stage:45} : {count:3d} ({pct:5.1f}%)")

print("\n[COMPLETE] Ready for Phase 3: Re-annotation with Standardized Categories")
