# LLM Prompt — Verbatim Corresponding-Text Requirement

**Date:** 2026-05-18
**File affected:** `core/llm.py` (`build_system_prompt`)
**Related:** [[2026-05-18-citation-eval-tnr-design]] (eval-side fix, already shipped in commit `fe1bb56`)
**Target metric:** PASS rate of `citation_text` coded eval on `traces/traces.jsonl`

## Goal

Make the patentdiff system prompt force the model to emit `corresponding_text` as either (a) exact verbatim text from the target patent, or (b) the empty string `""`. Nothing else. This is a prompt-only change motivated by genuine quoting (the coded eval is a proxy for whether the user can verify validity claims).

## Motivation

The current `core/llm.py` system prompt mentions `corresponding_text` only inside the JSON schema example: `"the corresponding text found in the target patent's claim or specification, or empty string if not found"`. This is too weak — the model freely paraphrases, narrates, and appends inline source tags.

Analysis of the 39 FAIL traces from `traces/citation_text_eval_full.jsonl` (93 summarised elements) shows three dominant failure patterns:

| Pattern | Share | Example |
|---|---:|---|
| **Meta-narration** (`"the specification describes…"`, trailing `(Specification)`, `"Patent B describes…"`) | 22% | `"the diffusion model may be a text‑guided diffusion model, and the diffusion model takes a text prompt as an input (Specification)"` |
| **Loose paraphrase** (rephrased without explicit meta-phrase) | 37% | `"encoding the text description information, obtaining a text code of a CLIP model"` |
| **Long paraphrase with inline parenthetical quote** | 41% | `"The cancellation channel is weighted (e.g., –3 dB) and combined with base channels; scaling of channels is described in the specification (e.g., \"scaled to the desired target level\")"` |

The 22% meta-narration bucket is the lowest-hanging fruit (model just needs to drop the wrapping). The 41% long-paraphrase bucket is interesting: the verbatim text is *already there*, just wrapped in narration — fixing the prompt should let many of these flip to PASS without changing model behavior much.

Baseline (pre-change) coded eval on all 87 traces with parsed_output:
- PASS: 32 (36.8%)
- FAIL: 39 (44.8%)
- NO_CITATIONS: 16 (18.4%)
- PASS rate among scored (PASS+FAIL, n=71): **45.1%**

## Scope

**In scope:**
- Add a new section `## Citation Text — Verbatim Quoting Requirements` to `build_system_prompt` in `core/llm.py`.
- Tighten the inline schema description for `corresponding_text` (line 49).

**Out of scope:**
- No changes to `core/citation_eval.py` (eval already credits `...`/`;`-joined verbatim fragments — see [[2026-05-18-citation-eval-tnr-design]]).
- No changes to `core/models.py` (`ElementMapping.corresponding_text` stays `str`, no `Optional`).
- No changes to `build_user_prompt` or any consumer.
- No few-shot examples beyond the inline CORRECT/INCORRECT pairs in the new section.
- No re-annotation of human labels.

## Design decisions (recorded)

1. **Empty value representation: `""`, not `null`.** Pydantic model is `corresponding_text: str` (non-optional). Allowing `null` would require a model change and consumer audit. Eval treats `""` and `None` identically. Decision: keep `""`.
2. **Success metric: genuine verbatim quoting.** Eval score is a proxy. We do not game the eval; we tighten the prompt and let the score follow.
3. **Aggressive but not full-rewrite.** Insert the new section + extend with rules and examples for the parenthetical/narration patterns. Do not rewrite the whole system prompt.

## Change 1 — New section in `build_system_prompt`

**Insertion point:** between the `## Output Format` heading (currently `core/llm.py:40`) and the JSON schema block. The new section MUST sit adjacent to the schema, because it modifies the semantics of the `corresponding_text` field.

**Block to insert** (verbatim, fenced inside the Python triple-quoted system prompt):

```
## Citation Text — Verbatim Quoting Requirements

For every element, `corresponding_text` MUST be either (a) exact verbatim
text copied from the target patent's independent_claim or specification,
or (b) the empty string "". Nothing else is acceptable.

RULES
- Copy verbatim. Character-for-character. Same words, same order, same
  punctuation as the target patent.
- Do NOT paraphrase, summarize, rephrase, or explain.
- Do NOT add meta-narration: no "the patent describes…", "the reference
  teaches…", "the target claim recites…", "Patent B discloses…".
- Do NOT add inline source tags: no trailing "(Specification)",
  "(independent claim)", "(see para 0618)", "(col. 5 lines 10-15)",
  "(see Fig. 3)". The user already knows where you looked.
- Do NOT wrap a quote in narration. If you want to cite something,
  cite ONLY the quote.
- If the element is clearly disclosed: quote the exact sentence(s).
- If the element is NOT disclosed: set corresponding_text to "".
- If you need to cite multiple non-adjacent passages from the same
  patent, join them with " ... " (three dots) or "; " between the
  verbatim fragments. Each fragment must independently be verbatim.

EXAMPLES

CORRECT (single verbatim sentence):
  "a processor configured to receive search query input and store
   said query in a persistent state database for subsequent retrieval"

CORRECT (two non-adjacent verbatim fragments joined with ...):
  "the cancellation channel is weighted ... scaled to the desired
   target level"

CORRECT (element not disclosed):
  ""

INCORRECT — paraphrase:
  "The patent describes a system that stores queries for later use"

INCORRECT — verbatim quote wrapped in narration:
  "scaling of channels is described in the specification
   (e.g., \"scaled to the desired target level\")"
  → Should be just: "scaled to the desired target level"

INCORRECT — trailing source tag:
  "the diffusion model may be a text-guided diffusion model (Specification)"
  → Should be: "the diffusion model may be a text-guided diffusion model"

INCORRECT — meta-narration with embedded paragraph reference:
  "The specification describes low-light mode being activated when
   ambient light is low (see §0618)."
  → Should be the actual quoted sentence from §0618, or "" if no
   sentence cleanly maps.
```

Three deliberate differences from the user's original draft:

1. `"leave corresponding_text as null"` → `set corresponding_text to ""` (matches Pydantic schema).
2. Explicit ban on inline source tags `(Specification)`, `(see para X)`, `(col. X)` — these alone account for ~22% of FAILs.
3. New "joined fragments" rule + two new INCORRECT examples for the narration-wrapping-a-quote pattern. Directly attacks the 41% long-paraphrase bucket, and is consistent with the eval's existing `...`/`;` splitter (so good model behavior gets credited by the score).

## Change 2 — Schema-line tightening

Current `core/llm.py:49`:

```
"corresponding_text": "the corresponding text found in the target patent's claim or specification, or empty string if not found",
```

Replace with:

```
"corresponding_text": "the EXACT verbatim text quoted from the target patent's independent_claim or specification — no paraphrase, no narration, no parenthetical citations — or \"\" if not disclosed",
```

Rationale: schema must agree with the new section, or the model can rationalize disobeying the section by pointing at the looser schema description.

## Verification

1. **Pre-change baseline frozen.** `traces/citation_text_eval_full.jsonl` from the 09:17 run (2026-05-18) is the baseline — PASS 36.8%, FAIL 44.8%, NO_CITATIONS 18.4%, scored-PASS 45.1%.
2. **Regenerate traces.** Re-run the model against the same 91 inputs from `traces/traces.jsonl`. Use a small script that:
   - Iterates each line of `traces/traces.jsonl`.
   - Reconstructs `PatentInput` from `trace["inputs"]["source_patent"]` and `trace["inputs"]["target_patent"]`.
   - Calls `build_system_prompt()` + `build_user_prompt(...)` + `call_groq(...)`.
   - Writes a new file `traces/traces.post-prompt-v2.jsonl` with the same per-line schema (`run_id`, `inputs`, `prompt`, `llm_response`, `parsed_output`, `status`, `error`). Reuse the existing `run_id` so per-trace comparison is trivial.
   - Do NOT overwrite `traces/traces.jsonl` — keep both for direct diff.
3. **Re-run coded eval.** Add a `--traces PATH` CLI arg to `scripts/run_citation_eval.py` (default keeps current `traces/traces.jsonl`) and a paired `--out PATH` arg. Run with `--traces traces/traces.post-prompt-v2.jsonl --out traces/citation_text_eval_full.post-prompt-v2.jsonl`.
4. **Compute delta.** Small script:
   - Per-trace verdict change matrix (rows = pre, cols = post, cells = count).
   - Aggregate counts and PASS rate among scored.
   - List the run_ids in each transition bucket for spot-checking.
5. **Spot-check 5 newly-PASS traces** (eval-is-proxy check from the goal). For each: read `parsed_output.element_mappings` and confirm every non-empty `corresponding_text` is genuinely verbatim against the input target patent text — not just gaming.
6. **Spot-check 3 still-FAIL traces.** Confirm remaining failures are legitimate hard cases (true paraphrase that couldn't be quoted), not new failure modes introduced by the prompt.

## Success criteria

- **PASS rate among scored** (PASS+FAIL) rises from **45.1% baseline → ≥ 65%**. Justification: 22% meta-narration is almost-certainly fixable + reasonable share of the 41% long-paraphrase bucket should flip.
- **NO_CITATIONS rate stays within ±5 pp of baseline (18.4%).** Guards against the model dodging the verbatim rule by emitting `""` everywhere.
- **Spot-check confirms 5/5 newly-PASS traces have genuine verbatim quotes** (not adversarial gaming of the n-gram score).
- **No new failure modes introduced** in spot-checked still-FAIL traces.

## Failure modes / risks

- **Risk: model truncates quotes to keep them "clean."** Dropping trailing or middle words to avoid imperfection could lower `_contiguous_ratio` and push borderline cases into FAIL. Caught by spot-check step 6.
- **Risk: model defaults to `""` too aggressively** if it can't find an exact quote. Caught by the NO_CITATIONS ±5 pp guard.
- **Risk: model still meta-narrates despite the rule** because the few-shot is inline rather than in a separate few-shot block. If post-change FAILs still show meta-narration in spot-check, consider escalating to explicit few-shot examples in a follow-up.
- **Risk: prompt growth invalidates `SYSTEM_PROMPT_TOKENS = 500` budget** in `core/llm.py:11`. The new block is ~350 words ≈ 460 tokens. Combined with existing system prompt (~370 tokens), new total ≈ 830 tokens. **Action: bump `SYSTEM_PROMPT_TOKENS` to 1000** to leave headroom and confirm `available` budget in `build_user_prompt` (line 72) still leaves a usable per-spec budget. With `GROQ_TOKEN_LIMIT = 8000` and typical claim sizes ~500 tokens, per-spec budget drops by ~250 tokens — still well above the `max(..., 500)` floor.

## Rollback

Single-file revert of `core/llm.py`. No data migration. The regenerated traces file (`traces/traces.post-prompt-v2.jsonl`) is independent — leave it in place or delete it.

## Reproducibility

- Same model (`PATENTDIFF_MODEL` env var, default `openai/gpt-oss-120b`).
- Same `temperature=0.2` and `max_tokens=4096` from `call_groq`.
- Same 91 inputs from `traces/traces.jsonl`.
- Outputs written to dedicated `*.post-prompt-v2.jsonl` files so baseline is preserved.
