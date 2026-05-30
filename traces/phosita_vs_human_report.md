# Absent PHOSITA Reasoning - Coded Eval vs Human Eval

**Sample:** 30 human-annotated traces (`source="human"`, comment does not start with "Test", matching coded eval entry exists)
**Positive class:** human tagged `absent_phosita_reasoning`
**Coded mapping:** FAIL -> positive; PASS -> negative
**Judge model:** qwen/qwen3-32b
**Prompt version:** v2

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** |              1 |              5 |
| **Coded negative** |              8 |             16 |

## Metrics

- **TPR (sensitivity)** = TP / (TP + FN) = 1 / 9 = 11.1%
- **TNR (specificity)** = TN / (TN + FP) = 16 / 21 = 76.2%

## Disagreement run_ids (for spot-check)

**False positives (coded FAIL, human did not tag phosita):**
- 25278e8f-8de3-4ca9-abfb-df23094b1afc
- 66177649-19b1-4a4c-9164-f3d46b34f281
- cd5f5b1d-ace6-4c38-9161-bf8ba84661d6
- 161f8d2c-522a-416d-a29d-42a2ba891747
- 7acff2e7-df49-4ae0-90a3-8e7218973c15

**False negatives (human tagged phosita, coded PASS):**
- 5b329590-338e-4794-b854-48b34854423f
- adb8892f-9b5b-414e-852a-dec4e1e2bf64
- 19ae3684-d65b-4624-9e4b-a5b2eaac04ba
- 4b409ef1-290f-4bfb-b921-9a07ac4b8659
- 3dd2fbfe-0fe4-4bdd-a8ac-caf54956c680
- 8d9bc974-af50-4d86-8535-e7cfc83bec5a
- 68c46c9b-5079-4e4e-80a6-82686fae5a3d
- ad420124-d80c-442c-9868-aa0a7496ea9f
