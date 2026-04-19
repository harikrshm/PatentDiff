# Token Optimisation — Design Specification

## Overview

PatentDiff hits Groq's 8,000 token per-minute limit when users paste multi-paragraph specification sections. This feature adds claim-aware smart truncation of specification text before the LLM call, silently keeping sentences that directly describe claim elements and trimming the rest to fit within the token budget.

## Goals

- Stay within the 8,000 token input limit on Groq's on-demand tier
- Preserve specification sentences that contain keywords from the claim text
- Log truncation events in JSONL traces for eval analysis
- No visible change to the user

## Non-Goals

- UI warnings or indicators of truncation
- Summarisation or paraphrasing of spec content
- Adding a second LLM call for relevance scoring
- Changing the single-call architecture

---

## Architecture

### New File

**`core/truncation.py`** — two public functions with clear, testable responsibilities

### Modified Files

- **`core/llm.py`** — `build_user_prompt()` calls truncation internally, return type changes to `tuple[str, list[str]]`
- **`app.py`** — unpacks the new tuple, passes `truncation_warnings` to `build_trace_record()`
- **`tracing/logger.py`** — adds `truncation_warnings: list[str]` field to trace record

---

## `core/truncation.py`

### `extract_keywords(claim_text: str) -> set[str]`

Extracts technical terms from the claim for use as matching keywords.

**Algorithm:**
1. Lowercase the claim text
2. Split into words
3. Remove stop words — common English words plus patent language: `{"a", "an", "the", "comprising", "wherein", "said", "least", "having", "each", "one", "at", "of", "to", "for", "with", "by", "or", "and", "is", "are", "that", "which", "this", "in", "on", "from", "be", "as", "its", "into", "based", "using", "at", "least", "more", "than"}`
4. Keep words with 4 or more characters
5. Return as a set of unique strings

### `smart_truncate_spec(spec_text: str, claim_text: str, token_budget: int) -> tuple[str, bool]`

Truncates spec text to fit within `token_budget` tokens, protecting sentences that contain claim keywords.

**Token estimation:** `len(text.split()) * 1.3` (word count × 1.3 to approximate subword tokenization, no external library)

**Algorithm:**
1. Extract keywords via `extract_keywords(claim_text)`
2. Split spec into sentences — split on `. ` (period + space), `\n\n` (paragraph break), keeping the delimiter attached to the preceding sentence
3. Classify each sentence: **protected** if it contains any keyword (case-insensitive), **unprotected** otherwise
4. If the full spec fits within `token_budget`, return `(spec_text, False)` — no truncation needed
5. Otherwise, greedily fill budget:
   - First pass: collect all protected sentences (preserving original document order) — these are always included if budget allows
   - Second pass: iterate all sentences in original document order; add each unprotected sentence if it fits within the remaining budget after protected sentences are accounted for
   - Result is reassembled in original document order (not protected-first)
6. Return `(truncated_text, True)`

---

## `core/llm.py` Changes

### Token Budget Calculation

Constants (at module level):
```python
GROQ_TOKEN_LIMIT = 8000
SYSTEM_PROMPT_TOKENS = 500   # conservative estimate for current system prompt
TEMPLATE_OVERHEAD_TOKENS = 150  # user prompt template markdown and labels
SAFETY_BUFFER_TOKENS = 300   # headroom to avoid off-by-one errors
```

### `build_user_prompt()` Signature Change

**Before:** `build_user_prompt(source: PatentInput, target: PatentInput) -> str`

**After:** `build_user_prompt(source: PatentInput, target: PatentInput) -> tuple[str, list[str]]`

**Logic added inside `build_user_prompt()`:**
1. Estimate token counts for both claims
2. Calculate `available = GROQ_TOKEN_LIMIT - SYSTEM_PROMPT_TOKENS - TEMPLATE_OVERHEAD_TOKENS - SAFETY_BUFFER_TOKENS - claim_a_tokens - claim_b_tokens`
3. `per_spec_budget = max(available // 2, 500)` — floor at 500 to avoid zero budget edge case
4. Truncate `source.specification` and `target.specification` via `smart_truncate_spec()`
5. Build the prompt string using truncated specs
6. Return `(prompt_string, warnings)` where `warnings` is a list containing `"Patent A specification truncated"` and/or `"Patent B specification truncated"` for each spec that was trimmed

---

## `app.py` Changes

Unpack the new return value from `build_user_prompt()`:

```python
user_prompt, truncation_warnings = build_user_prompt(source, target)
```

Pass `truncation_warnings` to `build_trace_record()`. No user-facing display.

---

## `tracing/logger.py` Changes

Add `truncation_warnings` field to the trace record dict:

```python
"truncation_warnings": truncation_warnings,  # list[str], empty if no truncation
```

---

## Constraints & Assumptions

- Token estimation uses `len(text.split()) * 1.3` — approximate, not exact. The 300-token safety buffer absorbs estimation error.
- The sentence splitter is simple (`. `, `\n\n`) — does not handle all edge cases (e.g., abbreviations like "U.S." mid-sentence). Acceptable for patent text which uses standard technical prose.
- If protected sentences alone exceed the budget, only protected sentences are returned (truncation still occurs, unprotected sentences are all dropped).
- `per_spec_budget` is floored at 500 tokens to ensure at minimum a meaningful amount of spec text is included even for extremely long claims.
