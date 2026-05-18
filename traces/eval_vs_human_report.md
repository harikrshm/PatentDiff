# Citation Text - Coded Eval vs Human Eval

**Sample:** 30 human-annotated traces (`source="human"`, real `run_id`, comment does not start with "Test")
**Positive class:** human tagged `citation_text`
**Coded mapping:** FAIL -> positive; PASS and NO_CITATIONS -> negative
**Config:** ngram_n=5, threshold=0.75

## Confusion matrix

|                    | Human positive | Human negative |
|--------------------|---------------:|---------------:|
| **Coded positive** |              2 |             10 |
| **Coded negative** |              0 |             18 |

## Metrics

- **TPR (sensitivity)** = TP / (TP + FN) = 2 / 2 = 100.0%
- **TNR (specificity)** = TN / (TN + FP) = 18 / 28 = 64.3%
