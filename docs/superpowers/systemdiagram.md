# PatentDiff — System Architecture Diagram

## Overview

PatentDiff is a local Streamlit application that assesses whether a source patent's independent claim is valid against a target patent as prior art. It makes a single LLM call per analysis and logs every run to a JSONL trace file for evaluation.

---

## Architecture Flowchart

```mermaid
flowchart TD
    %% ── INPUTS ──────────────────────────────────────────
    subgraph INPUTS["INPUTS (User via Browser UI)"]
        A1["Patent A — Label\n(e.g. US10,123,456)"]
        A2["Patent A — Independent Claim\n(plain text, numbered elements)"]
        A3["Patent A — Specification Support\n(relevant paragraphs)"]
        B1["Patent B — Label\n(prior art reference)"]
        B2["Patent B — Independent Claim"]
        B3["Patent B — Specification Support"]
    end

    %% ── UI LAYER ─────────────────────────────────────────
    subgraph UI["UI LAYER  ·  app.py  ·  Streamlit"]
        UI1["Two-column text inputs\n(label, claim, spec per patent)"]
        UI2["Analyze button"]
        UI3["Input validation\n(all 6 fields must be filled)"]
    end

    %% ── DATA MODELS ──────────────────────────────────────
    subgraph MODELS["DATA MODELS  ·  core/models.py  ·  Pydantic v2"]
        M1["PatentInput\n· label: str\n· independent_claim: str\n· specification: str"]
        M2["AnalysisReport\n· element_mappings: list[ElementMapping]\n· overall_opinion: str"]
        M3["ElementMapping\n· element_number: int\n· element_text: str\n· corresponding_text: str\n· novelty: Literal[Y/N]\n· inventive_step: Literal[Y/N]\n· verdict: Literal[Y/N]\n· comment: str"]
    end

    %% ── PROMPT BUILDING ──────────────────────────────────
    subgraph PROMPTS["PROMPT BUILDER  ·  core/llm.py"]
        P1["build_system_prompt()\n— Static patent analyst role\n— Element-by-element workflow\n— Novelty + inventive step criteria\n— JSON output schema"]
        P2["Token budget calculation\nLimit: 8,000 tokens\n− 500 system prompt\n− 150 template overhead\n− 300 safety buffer\n− claim_A tokens\n− claim_B tokens\n÷ 2 = per_spec_budget (min 500)"]
        P3["build_user_prompt()\n→ tuple[str, list[str]]\n(prompt, truncation_warnings)"]
    end

    %% ── TRUNCATION ───────────────────────────────────────
    subgraph TRUNC["SMART TRUNCATION  ·  core/truncation.py"]
        T1["extract_keywords(claim_text)\n— Lowercase & tokenise claim\n— Remove stop words + patent terms\n— Keep words ≥ 4 chars\n→ set[str]"]
        T2["smart_truncate_spec(spec, claim, budget)\n— Split spec into sentences\n— Classify: protected (has keyword) vs unprotected\n— Always include protected sentences\n— Greedily fill remaining budget\n  with unprotected sentences\n— Reassemble in original order\n→ (truncated_text, was_truncated: bool)"]
    end

    %% ── LLM CALL ─────────────────────────────────────────
    subgraph LLM["LLM CALL  ·  core/llm.py → Groq API"]
        L1["call_groq(system_prompt, user_prompt)\n— Model: openai/gpt-oss-120b\n— Temperature: 0.2\n— Max output tokens: 4,096\n— Auth: GROQ_API_KEY from .env"]
        L2["Groq API Response\n· raw_output: str (JSON)\n· model: str\n· tokens_input: int\n· tokens_output: int\n· latency_ms: int"]
    end

    %% ── RESPONSE PARSING ─────────────────────────────────
    subgraph PARSE["RESPONSE PARSER  ·  core/report.py"]
        R1["parse_llm_response(raw_output)\n— Strip markdown fences if present\n— json.loads() → dict\n— AnalysisReport.model_validate(dict)\n→ AnalysisReport  |  raises ValueError"]
    end

    %% ── TRACING ──────────────────────────────────────────
    subgraph TRACE["TRACING  ·  tracing/logger.py + tracing/store.py"]
        TR1["build_trace_record()\nFields:\n· run_id (UUID)\n· timestamp (UTC ISO)\n· inputs (both patents full text)\n· prompt (system + user)\n· llm_response (raw + metrics)\n· parsed_output (model_dump or null)\n· status: success | error\n· error: str | null\n· truncation_warnings: list[str]"]
        TR2["append_trace(record)\n→ traces/traces.jsonl\n(newline-delimited JSON, appended)"]
    end

    %% ── OUTPUTS ──────────────────────────────────────────
    subgraph OUTPUTS["OUTPUTS (Browser UI)"]
        O1["Element Mapping Table\n(dataframe — one row per claim element)"]
        O2["Overall Opinion\n(paragraph — weighted toward core\ntechnical advancement elements)"]
        O3["Run Metadata expander\n· Model name\n· Input / output token count\n· Latency (ms)\n· Run ID"]
        O4["traces/traces.jsonl\n(eval dataset — every run logged)"]
        O5["Error message\n(st.error if LLM call or\nparsing fails)"]
    end

    %% ── FLOW EDGES ───────────────────────────────────────
    A1 & A2 & A3 --> UI1
    B1 & B2 & B3 --> UI1
    UI1 --> UI2 --> UI3
    UI3 -->|"valid"| M1
    UI3 -->|"missing fields"| O5

    M1 --> P1
    M1 --> P2
    P2 --> T1
    T1 --> T2
    T2 -->|"spec_a (truncated)"| P3
    T2 -->|"spec_b (truncated)"| P3
    P1 --> L1
    P3 -->|"user_prompt + warnings"| L1

    L1 --> L2
    L2 -->|"raw_output"| R1
    R1 -->|"AnalysisReport"| M2
    M2 --> M3

    L2 --> TR1
    R1 --> TR1
    M1 --> TR1
    P1 --> TR1
    P3 --> TR1
    TR1 --> TR2 --> O4

    M3 --> O1
    M2 --> O2
    L2 --> O3
    TR1 --> O3

    L1 -->|"exception"| TR1
    L1 -->|"exception"| O5
    R1 -->|"ValueError"| TR1
    R1 -->|"ValueError"| O5
```

---

## Block Reference

| Block | File | Responsibility |
|-------|------|----------------|
| **PatentInput** | `core/models.py` | Pydantic model — validates and holds one patent's label, claim, and spec |
| **AnalysisReport** | `core/models.py` | Pydantic model — holds the full LLM analysis result |
| **ElementMapping** | `core/models.py` | Pydantic model — one row of the element-level analysis |
| **build_system_prompt()** | `core/llm.py` | Builds the static patent analyst system prompt with workflow and JSON schema |
| **Token budget calculation** | `core/llm.py` | Computes per-spec token budget from the 8,000-token Groq limit minus fixed overheads and claim sizes |
| **extract_keywords()** | `core/truncation.py` | Extracts technical terms from a claim by stripping stop words and short words |
| **smart_truncate_spec()** | `core/truncation.py` | Keyword-protected sentence-level truncation — always keeps sentences containing claim keywords, greedily fills remaining budget with other sentences |
| **build_user_prompt()** | `core/llm.py` | Combines truncated specs + claims into the LLM user prompt; returns `(prompt, truncation_warnings)` |
| **call_groq()** | `core/llm.py` | Calls the Groq API (openai/gpt-oss-120b) and returns raw output + usage metrics |
| **parse_llm_response()** | `core/report.py` | Strips markdown fences, JSON-decodes, and Pydantic-validates the LLM output into an AnalysisReport |
| **build_trace_record()** | `tracing/logger.py` | Assembles the full JSONL record for every run (inputs, prompts, LLM response, parsed output, status, warnings) |
| **append_trace()** | `tracing/store.py` | Appends one JSON record to `traces/traces.jsonl` (UTF-8, newline-delimited) |

---

## Data Shapes

### PatentInput (input to pipeline)
```
label:              str   — human-readable patent identifier
independent_claim:  str   — full text of the independent claim
specification:      str   — relevant specification paragraphs
```

### build_user_prompt() output
```
prompt:               str        — formatted markdown string for LLM user message
truncation_warnings:  list[str]  — ["Patent A specification truncated"] and/or
                                   ["Patent B specification truncated"], or []
```

### Groq API response dict
```
raw_output:      str  — raw LLM text (JSON or markdown-fenced JSON)
model:           str  — model name used
tokens_input:    int  — prompt tokens consumed
tokens_output:   int  — completion tokens generated
latency_ms:      int  — round-trip time in milliseconds
```

### ElementMapping (per claim element)
```
element_number:     int          — sequential element index
element_text:       str          — exact claim element text from Patent A
corresponding_text: str          — matching text found in Patent B (or "")
novelty:            "Y" | "N"   — Y = not novel (found in prior art)
inventive_step:     "Y" | "N"   — Y = obvious given prior art
verdict:            "Y" | "N"   — Y = prior art anticipates this element
comment:            str          — step-by-step reasoning
```

### Trace record (written to traces/traces.jsonl)
```
run_id:               str        — UUID v4
timestamp:            str        — UTC ISO 8601
inputs:               dict       — both patents (label, claim, spec)
prompt:               dict       — system_prompt + user_prompt
llm_response:         dict       — raw_output, model, tokens, latency
parsed_output:        dict|null  — AnalysisReport.model_dump() or null on error
status:               str        — "success" | "error"
error:                str|null   — exception message or null
truncation_warnings:  list[str]  — which specs were truncated ([] if none)
```

---

## Token Budget Logic

```
GROQ_TOKEN_LIMIT        = 8,000
− SYSTEM_PROMPT_TOKENS  =   500  (conservative estimate for system prompt)
− TEMPLATE_OVERHEAD     =   150  (markdown labels and separators)
− SAFETY_BUFFER         =   300  (headroom for estimation error)
− claim_A_tokens             (actual claim A word count × 1.3)
− claim_B_tokens             (actual claim B word count × 1.3)
─────────────────────────────
= available_tokens

per_spec_budget = max(available_tokens // 2, 500)
```

Token estimation: `int(len(text.split()) * 1.3)` — word count × 1.3 approximates subword tokenisation without an external library.

---

## Error Paths

| Failure point | Behaviour |
|---------------|-----------|
| Missing UI fields | `st.error()` shown, analysis does not start |
| `GROQ_API_KEY` not set | `ValueError` raised before API call, caught by except block |
| Groq API error (e.g. 413, 401, network) | Exception caught, error trace logged, `st.error()` shown |
| LLM returns invalid JSON | `parse_llm_response()` raises `ValueError`, error trace logged, `st.error()` shown |
| LLM returns JSON that fails schema validation | `parse_llm_response()` raises `ValueError`, same path as above |

In every error case a trace record with `status: "error"` and `error: "<message>"` is still appended to `traces/traces.jsonl`.
