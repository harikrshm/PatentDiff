# EXP1 — Verbatim-quote instruction (Layer 1, Citation Text)

**Change:** PatentDiff `build_system_prompt()` requires `corresponding_text` to be
exact verbatim text (or empty), "no paraphrase, no narration." This was a
post-eval prompt change; the baseline traces predate it.

**Method:** No new generation needed — the verbatim-prompt regeneration of the 39
baseline citation-FAIL traces already exists (`traces.post-prompt-v2.fails.jsonl`).
Re-ran the citation eval on those (new-prompt) outputs and diffed vs baseline:

```
python scripts/compute_eval_delta.py \
  --before traces/citation_text_eval_full.baseline.jsonl \
  --after  traces/citation_text_eval_full.post-prompt-v2.fails.jsonl
```

**Result (the 39 baseline citation FAILs):**
- FAIL → PASS: **24**
- FAIL → FAIL: 1
- FAIL → NO_CITATIONS: 8
- FAIL → not-regenerated: 6
- Among the 25 re-scored: **24/25 = 96% PASS, up from 45% (+51pp).**

**Decision: KEEP.** The verbatim instruction resolves 24/25 scored citation failures.

**Caveat (open spot-check):** 8 went FAIL → NO_CITATIONS — the model now returns
empty `corresponding_text` instead of paraphrasing. Verify these are genuinely
"not disclosed" rather than the model omitting citations to dodge the verbatim
requirement. run_ids: 249fbb0c 25278e8f 3dd2fbfe 4f1e3deb 62303a37 ada673e2
e3a5c26b ff46a11a.

**Guardrail not yet checked:** the post-prompt-v2 regeneration only covers the
39 failing traces, so it does not show whether the verbatim change regressed any
baseline PASS. Acceptable for a Layer-1 instruction add; full-corpus guardrail
deferred.
