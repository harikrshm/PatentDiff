import re

_STOP_WORDS = {
    "a", "an", "the", "comprising", "wherein", "said", "least", "having",
    "each", "one", "at", "of", "to", "for", "with", "by", "or", "and",
    "is", "are", "that", "which", "this", "in", "on", "from", "be", "as",
    "its", "into", "based", "using", "more", "than", "not", "such", "any",
    "also", "when", "then", "where", "how",
}


def extract_keywords(claim_text: str) -> set[str]:
    """Extract technical keywords from a patent claim.

    Strips stop words and short words, returns lowercase unique terms.
    """
    words = re.findall(r"[a-zA-Z]+", claim_text.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOP_WORDS}
