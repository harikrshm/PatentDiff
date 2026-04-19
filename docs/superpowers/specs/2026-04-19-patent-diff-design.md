# PatentDiff — Design Specification

## Overview

PatentDiff is a local web application that compares two patents to assess the validity of a source patent's independent claim against a target patent's prior art. It replicates a patent professional's workflow — parsing claim elements, evaluating novelty and inventive step — using an LLM via the Groq API.

The project also serves as a trace-generation tool: every analysis run produces structured logs (inputs, prompts, raw LLM output, parsed results) stored as JSONL, intended for building an evaluation framework.

## Goals

- Replicate a patent professional's claim analysis workflow using an LLM
- Provide a simple browser-based UI for local testing
- Generate structured traces for every run to support eval framework development

## Non-Goals

- PDF or document export (MVP)
- Dependent claim analysis
- Patent document upload or auto-fetch by patent number
- Multi-turn or multi-call LLM workflows
- Production deployment

---

## Architecture

### Project Structure

```
patentdiff/
├── app.py                  # Streamlit UI
├── core/
│   ├── llm.py              # Groq API call, prompt construction
│   ├── report.py           # Parse LLM output into structured report
│   └── models.py           # Data classes for inputs/outputs
├── tracing/
│   ├── logger.py           # Structured trace logging
│   └── store.py            # JSONL persistence
├── traces/                 # Output directory for trace files
├── requirements.txt        # Dependencies
└── README.md
```

### Dependencies

- `streamlit` — UI framework
- `groq` — Groq Python SDK for LLM inference
- `pydantic` — data models with validation

---

## Data Models

### Inputs

**PatentInput**
- `label: str` — patent name/identifier (e.g., "US10,123,456")
- `independent_claim: str` — full text of the independent claim
- `specification: str` — specification text supporting the independent claim

**AnalysisRequest**
- `source_patent: PatentInput` — Patent A (the patent being assessed for validity)
- `target_patent: PatentInput` — Patent B (the prior art reference)

### Outputs

**ElementMapping**
- `element_number: int` — sequential element index
- `element_text: str` — the claim element from Patent A
- `corresponding_text: str` — corresponding text found in Patent B's claim/specification
- `novelty: str` — "Y" if the element is disclosed in Patent B (i.e., NOT novel), "N" if the element is not found in Patent B (i.e., novel)
- `inventive_step: str` — "Y" if the element is obvious given Patent B's teaching (i.e., NOT inventive), "N" if the element represents a non-obvious technical improvement (i.e., inventive)
- `verdict: str` — "Y" if the element is found AND obvious (Patent A lacks novelty/inventive step for this element), "N" if the element is novel OR non-obvious (Patent A has novelty/inventive step for this element)
- `comment: str` — reasoning explaining the assessment

**AnalysisReport**
- `element_mappings: list[ElementMapping]` — element-by-element mapping table
- `overall_opinion: str` — final validity/infringement assessment

---

## LLM Prompt & Workflow

### Provider

Groq API calling an open-source 120B parameter model. Single API call per analysis.

### System Prompt

The system prompt instructs the LLM to act as a patent professional with the following workflow:

1. **Parse Patent A's independent claim into elements** — using claim language conventions (semicolons, line breaks, preamble vs. body structure) to identify individual claim elements. Up to ~10 elements expected.

2. **For each element, search Patent B** — look through Patent B's independent claim text and specification support for corresponding language, concepts, or disclosure.

3. **For each element, evaluate:**
   - **Novelty** — Is this element disclosed in Patent B? Is the technical feature already known from Patent B, or is it new?
   - **Inventive Step** — Given Patent B's teaching, is this technical approach obvious? Or does it represent a meaningful, non-obvious technical improvement?

4. **Produce a verdict per element** — Y (found/obvious) or N (novel/non-obvious) with a comment explaining the reasoning. The LLM must think step by step through novelty and inventive step before arriving at the verdict.

5. **Produce an overall opinion** — a final assessment of Patent A's validity considering all element mappings together but the main emphasis will be on the whether the Novel/ Technical claim element in Patent A is mapped with Patent B i.e. less weightage on pre-processing steps or final output claim elements and more weightage on the main technical advancement claim element in Patent A mapping as Y/N. Then overall opinion must be based on that verdict of technical advancement claim element and its reasoning.

### Output Format

The LLM is instructed to return structured JSON matching the `AnalysisReport` schema. The prompt will include the exact JSON schema to follow.

### Prompt Construction

The user prompt combines:
- Patent A label, independent claim, and specification
- Patent B label, independent claim, and specification

All passed as clearly labeled sections in the user message.

---

## Tracing & Logging

### Purpose

Every analysis run produces a trace record for use in building an evaluation framework. Both successful and failed runs are logged.

### Trace Record Structure

```json
{
  "run_id": "uuid",
  "timestamp": "ISO-8601",
  "inputs": {
    "source_patent": {
      "label": "...",
      "claim": "...",
      "specification": "..."
    },
    "target_patent": {
      "label": "...",
      "claim": "...",
      "specification": "..."
    }
  },
  "prompt": {
    "system_prompt": "...",
    "user_prompt": "..."
  },
  "llm_response": {
    "raw_output": "...",
    "model": "...",
    "tokens_input": 1234,
    "tokens_output": 567,
    "latency_ms": 890
  },
  "parsed_output": {
    "element_mappings": [...],
    "overall_opinion": "..."
  },
  "status": "success | error",
  "error": null
}
```

### Storage

- Traces append to `traces/traces.jsonl` — one JSON object per line per run
- Loadable with `pandas.read_json("traces/traces.jsonl", lines=True)`
- On error (LLM call failure, JSON parse failure), the trace is still logged with `status: "error"` and the error message

---

## Streamlit UI

### Layout

Single-page application:

**Input Area (top half):**
- Two columns side by side
  - Left column: Patent A (Source) — text input for label, large text area for independent claim, large text area for specification support
  - Right column: Patent B (Target) — same three fields
- "Analyze" button centered below both columns

**Results Area (bottom half, shown after analysis):**
- **Element Mapping Table** — columns: Element #, Patent A Element Text, Patent B Corresponding Text, Novelty (Y/N), Inventive Step (Y/N), Verdict (Y/N), Comment
- **Overall Opinion** — text block with the final validity assessment

**Loading State:**
- Spinner with status text during LLM call

---

## Constraints & Assumptions

- Maximum ~10 claim elements per analysis (single LLM call)
- Only independent claims analyzed (no dependent claims)
- User provides specification support text manually (no auto-extraction)
- Groq API key provided via environment variable (`GROQ_API_KEY`)
- Local use only — no authentication, no multi-user support
- The LLM model name is configurable (default: the 120B OSS model on Groq)
