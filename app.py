import streamlit as st
import pandas as pd

from core.llm import build_system_prompt, build_user_prompt, call_groq
from core.models import PatentInput
from core.report import parse_llm_response
from tracing.logger import build_trace_record
from tracing.store import append_trace

st.set_page_config(page_title="PatentDiff", layout="wide")
st.title("PatentDiff — Patent Claim Analysis")

# --- Input Area ---
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Patent A (Source)")
    label_a = st.text_input("Label", key="label_a", placeholder="e.g., US10,123,456")
    claim_a = st.text_area("Independent Claim", key="claim_a", height=200)
    spec_a = st.text_area("Specification Support", key="spec_a", height=200)

with col_b:
    st.subheader("Patent B (Target / Prior Art)")
    label_b = st.text_input("Label", key="label_b", placeholder="e.g., US9,876,543")
    claim_b = st.text_area("Independent Claim", key="claim_b", height=200)
    spec_b = st.text_area("Specification Support", key="spec_b", height=200)

analyze = st.button("Analyze", use_container_width=True)

# --- Analysis ---
if analyze:
    if not all([label_a, claim_a, spec_a, label_b, claim_b, spec_b]):
        st.error("Please fill in all fields for both patents.")
    else:
        source = PatentInput(label=label_a, independent_claim=claim_a, specification=spec_a)
        target = PatentInput(label=label_b, independent_claim=claim_b, specification=spec_b)

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(source, target)

        with st.spinner("Analyzing patents — this may take a minute..."):
            llm_response = None
            report = None
            try:
                llm_response = call_groq(system_prompt, user_prompt)
                report = parse_llm_response(llm_response["raw_output"])

                trace = build_trace_record(
                    source_patent=source,
                    target_patent=target,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    llm_response=llm_response,
                    parsed_output=report,
                    status="success",
                    error=None,
                )
                append_trace(trace)

            except Exception as e:
                trace = build_trace_record(
                    source_patent=source,
                    target_patent=target,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    llm_response=llm_response or {"raw_output": "", "model": "", "tokens_input": 0, "tokens_output": 0, "latency_ms": 0},
                    parsed_output=None,
                    status="error",
                    error=str(e),
                )
                append_trace(trace)
                st.error(f"Analysis failed: {e}")
                st.stop()

        # --- Results Area ---
        st.divider()
        st.subheader("Element Mapping")

        rows = []
        for em in report.element_mappings:
            rows.append({
                "Element #": em.element_number,
                "Patent A Element": em.element_text,
                "Patent B Corresponding Text": em.corresponding_text,
                "Novelty": em.novelty,
                "Inventive Step": em.inventive_step,
                "Verdict": em.verdict,
                "Comment": em.comment,
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Overall Opinion")
        st.write(report.overall_opinion)

        # Show metadata
        with st.expander("Run Metadata"):
            st.write(f"**Model:** {llm_response['model']}")
            st.write(f"**Input tokens:** {llm_response['tokens_input']}")
            st.write(f"**Output tokens:** {llm_response['tokens_output']}")
            st.write(f"**Latency:** {llm_response['latency_ms']}ms")
            st.write(f"**Run ID:** {trace['run_id']}")
