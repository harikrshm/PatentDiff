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


from core.truncation import extract_keywords, smart_truncate_spec


def test_no_truncation_when_within_budget():
    spec = "The processor executes instructions. The memory stores data."
    claim = "A system comprising a processor and memory"
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=1000)
    assert was_truncated is False
    assert result == spec


def test_truncation_removes_unprotected_sentences():
    # Sentence 1: contains "processor" (keyword) — protected
    # Sentence 2: no keywords — unprotected, should be dropped
    spec = "The processor executes instructions stored in memory. The widget is used for filing purposes."
    claim = "A system comprising a processor"
    # Budget: only enough for ~10 tokens — forces truncation
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=10)
    assert was_truncated is True
    assert "processor" in result
    assert "widget" not in result


def test_protected_sentences_preserved_over_budget():
    spec = "The processor executes instructions. The memory stores processor data. Unrelated filler text here."
    claim = "A system comprising a processor"
    # Budget fits ~8 tokens — enough for one protected sentence
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=8)
    assert was_truncated is True
    assert "processor" in result


def test_result_preserves_original_sentence_order():
    spec = "First sentence about widget. Second sentence about processor. Third about memory. Fourth about widget again."
    claim = "A method using processor and memory"
    result, was_truncated = smart_truncate_spec(spec, claim, token_budget=1000)
    assert was_truncated is False
    proc_idx = result.index("processor")
    mem_idx = result.index("memory")
    assert proc_idx < mem_idx


def test_no_truncation_empty_spec():
    result, was_truncated = smart_truncate_spec("", "A system comprising a processor", token_budget=100)
    assert was_truncated is False
    assert result == ""
