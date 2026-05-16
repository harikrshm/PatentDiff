import difflib
import re
import unicodedata

NGRAM_N = 5
NGRAM_FALLBACK_N = 3
THRESHOLD = 0.75


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _contiguous_ratio(ct_norm: str, target_norm: str) -> float:
    if not ct_norm:
        return 0.0
    matcher = difflib.SequenceMatcher(None, ct_norm, target_norm, autojunk=False)
    match = matcher.find_longest_match(0, len(ct_norm), 0, len(target_norm))
    return match.size / len(ct_norm)


def _ngram_ratio(ct_norm: str, target_norm: str) -> float:
    ct_tokens = ct_norm.split()
    if not ct_tokens:
        return 0.0
    target_tokens = target_norm.split()
    n = NGRAM_N if len(ct_tokens) >= NGRAM_N else NGRAM_FALLBACK_N
    if len(ct_tokens) < n:
        # Very short CT: pass if every token appears anywhere in target as substring.
        return 1.0 if all(t in target_norm for t in ct_tokens) else 0.0
    ct_grams = _ngrams(ct_tokens, n)
    target_grams = set(_ngrams(target_tokens, n))
    if not ct_grams:
        return 0.0
    matched = sum(1 for g in ct_grams if g in target_grams)
    return matched / len(ct_grams)


def evaluate_trace(trace: dict) -> dict:
    target_patent = trace.get("inputs", {}).get("target_patent", {}) or {}
    target_text = (target_patent.get("independent_claim") or "") + "\n" + (target_patent.get("specification") or "")

    parsed = trace.get("parsed_output") or {}
    mappings = parsed.get("element_mappings") or []

    per_element = []
    for em in mappings:
        ct = em.get("corresponding_text") or ""
        if not normalize(ct):
            continue
        score = score_corresponding(ct, target_text)
        per_element.append(
            {
                "element_number": em.get("element_number"),
                "contiguous_ratio": score["contiguous_ratio"],
                "ngram_ratio": score["ngram_ratio"],
                "quotation_score": score["quotation_score"],
                "verdict": score["verdict"],
            }
        )

    num_scored = len(per_element)
    num_quoted = sum(1 for e in per_element if e["verdict"] == "quoted")
    num_summarised = num_scored - num_quoted

    if num_scored == 0:
        verdict = "NO_CITATIONS"
    elif num_summarised == 0:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return {
        "run_id": trace.get("run_id"),
        "eval_name": "citation_text",
        "verdict": verdict,
        "num_elements_scored": num_scored,
        "num_quoted": num_quoted,
        "num_summarised": num_summarised,
        "per_element": per_element,
        "config": {"ngram_n": NGRAM_N, "threshold": THRESHOLD},
    }


def score_corresponding(ct: str, target_text: str) -> dict:
    ct_norm = normalize(ct)
    target_norm = normalize(target_text)
    if not target_norm or not ct_norm:
        return {
            "contiguous_ratio": 0.0,
            "ngram_ratio": 0.0,
            "quotation_score": 0.0,
            "verdict": "summarised",
        }
    contiguous = _contiguous_ratio(ct_norm, target_norm)
    ngram = _ngram_ratio(ct_norm, target_norm)
    score = max(contiguous, ngram)
    verdict = "quoted" if score >= THRESHOLD else "summarised"
    return {
        "contiguous_ratio": contiguous,
        "ngram_ratio": ngram,
        "quotation_score": score,
        "verdict": verdict,
    }
