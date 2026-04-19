# core/llm.py
import os
import time

from groq import Groq

from core.models import PatentInput
from core.truncation import smart_truncate_spec

GROQ_TOKEN_LIMIT = 8000
SYSTEM_PROMPT_TOKENS = 500
TEMPLATE_OVERHEAD_TOKENS = 150
SAFETY_BUFFER_TOKENS = 300


def _estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def build_system_prompt() -> str:
    return """You are an expert patent analyst. Your task is to assess the validity of a source patent's independent claim against a target patent (prior art).

## Workflow

1. **Parse the source patent's independent claim into individual elements.** Use claim language conventions — semicolons, line breaks, and preamble vs. body structure — to identify each discrete claim element. Number them sequentially.

2. **For each element, search the target patent's independent claim and specification** for corresponding language, concepts, or disclosure.

3. **For each element, evaluate:**
   - **Novelty:** Is this element disclosed in the target patent? If the target patent describes the same technical feature, the element is NOT novel (Y). If not found, it IS novel (N).
   - **Inventive Step:** Given the target patent's teaching, is this technical approach obvious? If obvious, mark Y. If it represents a meaningful, non-obvious technical improvement, mark N.

4. **Produce a verdict per element:**
   - "Y" = element is found in target patent AND is obvious (source patent LACKS novelty/inventive step for this element)
   - "N" = element is novel OR non-obvious (source patent HAS novelty/inventive step for this element)
   - Include a comment with step-by-step reasoning through novelty and inventive step before the verdict.

5. **Produce an overall opinion** on the source patent's validity. Focus your assessment on the **core technical advancement elements** — give less weight to routine pre-processing steps or standard output/display elements, and more weight to the main novel technical contribution. Base your overall opinion primarily on whether the key technical advancement elements are mapped as Y or N and explain your reasoning.

## Output Format

Return ONLY valid JSON matching this exact schema — no markdown fences, no extra text:

{
  "element_mappings": [
    {
      "element_number": 1,
      "element_text": "the exact text of the claim element from the source patent",
      "corresponding_text": "the corresponding text found in the target patent's claim or specification, or empty string if not found",
      "novelty": "Y or N",
      "inventive_step": "Y or N",
      "verdict": "Y or N",
      "comment": "Step-by-step reasoning: first assess novelty, then inventive step, then conclude with verdict"
    }
  ],
  "overall_opinion": "Final validity assessment focusing on the core technical advancement elements"
}"""


def build_user_prompt(
    source: PatentInput,
    target: PatentInput,
) -> tuple[str, list[str]]:
    """Build the user prompt with smart spec truncation to stay within token budget.

    Returns (prompt_string, truncation_warnings).
    truncation_warnings is empty if no truncation was needed.
    """
    claim_a_tokens = _estimate_tokens(source.independent_claim)
    claim_b_tokens = _estimate_tokens(target.independent_claim)

    available = (
        GROQ_TOKEN_LIMIT
        - SYSTEM_PROMPT_TOKENS
        - TEMPLATE_OVERHEAD_TOKENS
        - SAFETY_BUFFER_TOKENS
        - claim_a_tokens
        - claim_b_tokens
    )
    # Note: `available` can be negative if both claims together exceed the fixed headroom
    # (GROQ_TOKEN_LIMIT minus system/template/buffer). The max(..., 500) floor ensures
    # smart_truncate_spec always receives a usable budget even in that edge case.
    per_spec_budget = max(available // 2, 500)

    spec_a, a_truncated = smart_truncate_spec(
        source.specification, source.independent_claim, per_spec_budget
    )
    spec_b, b_truncated = smart_truncate_spec(
        target.specification, target.independent_claim, per_spec_budget
    )

    warnings = []
    if a_truncated:
        warnings.append("Patent A specification truncated")
    if b_truncated:
        warnings.append("Patent B specification truncated")

    prompt = f"""## SOURCE PATENT (Patent A) — The patent being assessed for validity

**Label:** {source.label}

**Independent Claim:**
{source.independent_claim}

**Specification Support:**
{spec_a}

---

## TARGET PATENT (Patent B) — Prior art reference

**Label:** {target.label}

**Independent Claim:**
{target.independent_claim}

**Specification Support:**
{spec_b}"""

    return prompt, warnings


def call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict:
    """Call the Groq API and return a dict with raw_output, model, token counts, and latency.

    Returns:
        {
            "raw_output": str,
            "model": str,
            "tokens_input": int,
            "tokens_output": int,
            "latency_ms": int,
        }
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    client = Groq(api_key=api_key)
    model_name = model or os.environ.get("PATENTDIFF_MODEL", "openai/gpt-oss-120b")

    start = time.time()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )
    latency_ms = int((time.time() - start) * 1000)

    choice = response.choices[0]
    usage = response.usage

    return {
        "raw_output": choice.message.content,
        "model": model_name,
        "tokens_input": usage.prompt_tokens if usage else 0,
        "tokens_output": usage.completion_tokens if usage else 0,
        "latency_ms": latency_ms,
    }
