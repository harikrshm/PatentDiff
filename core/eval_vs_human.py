from typing import Iterable, Optional


def classify_coded(verdict: str) -> int:
    """1 if the coded verdict signals a citation_text failure, else 0."""
    return 1 if verdict == "FAIL" else 0


def classify_human(failure_modes: Optional[Iterable[str]]) -> int:
    """1 if the human tagged this trace with citation_text, else 0."""
    if not failure_modes:
        return 0
    return 1 if "citation_text" in failure_modes else 0


def confusion(pairs: Iterable[tuple]) -> dict:
    """Tally (human_label, coded_label) pairs into a 2x2 matrix."""
    tp = fp = fn = tn = 0
    for human, coded in (p[:2] for p in pairs):
        if human == 1 and coded == 1:
            tp += 1
        elif human == 0 and coded == 1:
            fp += 1
        elif human == 1 and coded == 0:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def tpr(tp: int, fn: int) -> Optional[float]:
    denom = tp + fn
    if denom == 0:
        return None
    return tp / denom


def tnr(tn: int, fp: int) -> Optional[float]:
    denom = tn + fp
    if denom == 0:
        return None
    return tn / denom
