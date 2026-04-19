from core.truncation import extract_keywords


def test_extract_keywords_removes_stop_words():
    claim = "A system comprising at least one computer processor"
    keywords = extract_keywords(claim)
    assert "comprising" not in keywords
    assert "least" not in keywords
    assert "system" in keywords
    assert "computer" in keywords
    assert "processor" in keywords


def test_extract_keywords_filters_short_words():
    claim = "A method for processing data using an algorithm"
    keywords = extract_keywords(claim)
    assert "for" not in keywords
    assert "an" not in keywords
    assert "method" in keywords
    assert "processing" in keywords
    assert "data" in keywords
    assert "algorithm" in keywords


def test_extract_keywords_is_case_insensitive():
    claim = "A System comprising a Processor and Memory"
    keywords = extract_keywords(claim)
    assert "system" in keywords
    assert "processor" in keywords
    assert "memory" in keywords
    for kw in keywords:
        assert kw == kw.lower()


def test_extract_keywords_returns_unique():
    claim = "processor and processor and processor"
    keywords = extract_keywords(claim)
    assert isinstance(keywords, set)
    assert len([k for k in keywords if k == "processor"]) == 1


def test_extract_keywords_empty_claim():
    keywords = extract_keywords("")
    assert keywords == set()
