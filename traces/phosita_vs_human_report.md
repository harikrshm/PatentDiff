# Absent PHOSITA Reasoning - Coded Eval vs Human Eval

**Sample:** 29 human-annotated traces (`source="human"`, comment does not start with "Test", matching coded eval entry exists)
**Positive class:** human tagged `absent_phosita_reasoning`
**Coded mapping:** FAIL -> positive; PASS -> negative
**Judge model:** qwen/qwen3-32b
**Prompt version:** v3

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** |              7 |              8 |
| **Coded negative** |              2 |             12 |

## Metrics

- **TPR (sensitivity)** = TP / (TP + FN) = 7 / 9 = 77.8%
- **TNR (specificity)** = TN / (TN + FP) = 12 / 20 = 60.0%

## Disagreement run_ids (for spot-check)

**False positives (coded FAIL, human did not tag phosita):**
- 66177649-19b1-4a4c-9164-f3d46b34f281
- a0df6f16-08b2-4e90-b7bd-0e402154bb48
- cd5f5b1d-ace6-4c38-9161-bf8ba84661d6
- 62303a37-1e75-42a8-9f70-97776253e4ee
- 161f8d2c-522a-416d-a29d-42a2ba891747
- 1a7dd4d4-adb8-4b07-bc3c-0dfaab6516fe
- 7acff2e7-df49-4ae0-90a3-8e7218973c15
- 0f9448bd-048c-4761-9fce-4c5f7beef53a

**False negatives (human tagged phosita, coded PASS):**
- 3dd2fbfe-0fe4-4bdd-a8ac-caf54956c680
- 68c46c9b-5079-4e4e-80a6-82686fae5a3d
