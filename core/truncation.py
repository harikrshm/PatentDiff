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


def _estimate_tokens(text: str) -> int:
    """Estimate token count as word count * 1.3."""
    return int(len(text.split()) * 1.3)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on '. ' and double newlines."""
    parts = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # Split on '. ' but reattach the period to the preceding sentence
        chunks = paragraph.split(". ")
        for i, chunk in enumerate(chunks):
            if i < len(chunks) - 1:
                parts.append(chunk + ".")
            else:
                parts.append(chunk)
    return [p for p in parts if p.strip()]


def smart_truncate_spec(
    spec_text: str,
    claim_text: str,
    token_budget: int,
) -> tuple[str, bool]:
    """Truncate spec_text to fit within token_budget, protecting sentences
    that contain keywords from claim_text.

    Returns (truncated_text, was_truncated).
    """
    if not spec_text.strip():
        return spec_text, False

    # No truncation needed
    if _estimate_tokens(spec_text) <= token_budget:
        return spec_text, False

    keywords = extract_keywords(claim_text)
    sentences = _split_sentences(spec_text)

    # Classify sentences
    protected = set()
    for i, sentence in enumerate(sentences):
        lower = sentence.lower()
        if any(kw in lower for kw in keywords):
            protected.add(i)

    # Calculate token budget used by protected sentences
    protected_tokens = sum(
        _estimate_tokens(sentences[i]) for i in protected
    )

    # Remaining budget for unprotected sentences
    remaining_budget = token_budget - protected_tokens

    # Select which unprotected sentences to include (in order)
    included = set(protected)
    if remaining_budget > 0:
        for i, sentence in enumerate(sentences):
            if i in protected:
                continue
            cost = _estimate_tokens(sentence)
            if cost <= remaining_budget:
                included.add(i)
                remaining_budget -= cost

    # Reassemble in original document order
    result = " ".join(sentences[i] for i in sorted(included))
    return result, True
