# Absent PHOSITA Reasoning - Coded Eval vs Human Eval

**Sample:** 30 human-annotated traces (`source="human"`, comment does not start with "Test", matching coded eval entry exists)
**Positive class:** human tagged `absent_phosita_reasoning`
**Coded mapping:** FAIL -> positive; PASS -> negative
**Judge model:** qwen/qwen3-32b
**Prompt version:** v1

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** |              3 |              5 |
| **Coded negative** |              6 |             16 |

## Metrics

- **TPR (sensitivity)** = TP / (TP + FN) = 3 / 9 = 33.3%
- **TNR (specificity)** = TN / (TN + FP) = 16 / 21 = 76.2%

## Disagreement run_ids (for spot-check)

**False positives (coded FAIL, human did not tag phosita):**
- a6c76d48-82cf-4629-a298-1773424f96ad
- ada673e2-f15c-4fc5-8803-8c9bbb63a875
- 66177649-19b1-4a4c-9164-f3d46b34f281
- 44fb3f46-a43c-4866-99c8-6fc01661159f
- 7acff2e7-df49-4ae0-90a3-8e7218973c15

**False negatives (human tagged phosita, coded PASS):**
- 5b329590-338e-4794-b854-48b34854423f
- adb8892f-9b5b-414e-852a-dec4e1e2bf64
- 19ae3684-d65b-4624-9e4b-a5b2eaac04ba
- 8d9bc974-af50-4d86-8535-e7cfc83bec5a
- 68c46c9b-5079-4e4e-80a6-82686fae5a3d
- ad420124-d80c-442c-9868-aa0a7496ea9f
