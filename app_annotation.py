import streamlit as st
import pandas as pd
from pathlib import Path
from collections import Counter
from core.annotation import (
    load_annotations, save_annotations, detect_phase, load_taxonomy,
    parse_failure_modes, AnnotationRecord, ElementJudgment, OverallOpinionJudgment
)
from core.trace_loader import load_traces

# --- Configuration ---
TRACES_FILE = Path("traces/traces.jsonl")
ANNOTATIONS_FILE = Path("traces/traces_annotations.jsonl")
TAXONOMY_FILE = Path("traces/failure_taxonomy.json")

# --- App Setup ---
st.set_page_config(page_title="PatentDiff Annotation Tool", layout="wide")
st.title("PatentDiff Error Analysis Tool")

# --- Session State Initialization ---
if "traces" not in st.session_state:
    try:
        st.session_state.traces = {t.run_id: t for t in load_traces(TRACES_FILE)}
    except Exception as e:
        st.error(f"Failed to load traces: {e}")
        st.stop()

if "annotations" not in st.session_state:
    try:
        st.session_state.annotations = load_annotations(ANNOTATIONS_FILE)
    except Exception as e:
        st.error(f"Failed to load annotations: {e}")
        st.session_state.annotations = {}

if "current_run_id" not in st.session_state:
    st.session_state.current_run_id = None

if "phase" not in st.session_state:
    st.session_state.phase = detect_phase()

if "taxonomy" not in st.session_state:
    st.session_state.taxonomy = load_taxonomy(TAXONOMY_FILE)

# --- Helper Functions ---

def display_trace(trace):
    """Display full trace details in read-only format."""
    st.subheader("Trace Metadata")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Run ID", trace.run_id[:12] + "...")
    with col2:
        st.metric("Status", trace.status)
    with col3:
        st.metric("Timestamp", trace.timestamp[:10])
    with col4:
        st.metric("Model", trace.llm_response.model if trace.llm_response else "N/A")

    st.divider()

    # Patents
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Source Patent (A)")
        src = trace.inputs.get("source_patent", {})
        st.write(f"**Label:** {src.get('label', 'N/A')}")
        st.write("**Independent Claim:**")
        st.text_area("Claim A", value=src.get('independent_claim', ''), disabled=True, height=100, key="src_claim")
        st.write("**Specification:**")
        spec_preview = src.get('specification', '')[:500]
        if len(src.get('specification', '')) > 500:
            spec_preview += "..."
        st.text_area("Spec A", value=spec_preview, disabled=True, height=80, key="src_spec")

    with col_b:
        st.subheader("Target Patent (B)")
        tgt = trace.inputs.get("target_patent", {})
        st.write(f"**Label:** {tgt.get('label', 'N/A')}")
        st.write("**Independent Claim:**")
        st.text_area("Claim B", value=tgt.get('independent_claim', ''), disabled=True, height=100, key="tgt_claim")
        st.write("**Specification:**")
        spec_preview_b = tgt.get('specification', '')[:500]
        if len(tgt.get('specification', '')) > 500:
            spec_preview_b += "..."
        st.text_area("Spec B", value=spec_preview_b, disabled=True, height=80, key="tgt_spec")

    st.divider()

    # Parsed output
    if trace.parsed_output:
        st.subheader("Element Mappings")
        for em in trace.parsed_output.element_mappings:
            with st.expander(f"Element {em.element_number}: {em.verdict}"):
                st.write(f"**Element Text:** {em.element_text}")
                st.write(f"**Corresponding Text:** {em.corresponding_text}")
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Novelty", "✅" if em.novelty else "❌")
                with cols[1]:
                    st.metric("Inventive Step", "✅" if em.inventive_step else "❌")
                with cols[2]:
                    st.metric("Verdict", em.verdict)
                st.write(f"**Comment:** {em.comment}")

        st.subheader("Overall Opinion")
        st.text_area("Tool's Final Verdict", value=trace.parsed_output.overall_opinion, disabled=True, height=150, key="overall_display")

    # LLM Response metadata
    if trace.llm_response:
        st.subheader("Run Metadata")
        cols = st.columns(4)
        with cols[0]:
            st.metric("Input Tokens", trace.llm_response.tokens_input)
        with cols[1]:
            st.metric("Output Tokens", trace.llm_response.tokens_output)
        with cols[2]:
            st.metric("Latency (ms)", trace.llm_response.latency_ms)
        with cols[3]:
            st.metric("Model", trace.llm_response.model)

def element_critique_form(trace, run_id, current_annotation=None):
    """Build element-level critique form."""
    if not trace.parsed_output or not trace.parsed_output.element_mappings:
        st.warning("No element mappings found in this trace.")
        return None

    elements = trace.parsed_output.element_mappings
    element_numbers = [em.element_number for em in elements]

    st.subheader("Element-Level Critique")

    selected_element_num = st.selectbox("Select Element", element_numbers, key=f"element_select_{run_id}")
    selected_element = next(em for em in elements if em.element_number == selected_element_num)

    st.write(f"**Element {selected_element.element_number}**")
    st.write(f"Element Text: {selected_element.element_text}")
    st.write(f"Corresponding Text: {selected_element.corresponding_text}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tool's Novelty", "✅ Yes" if selected_element.novelty else "❌ No")
    with col2:
        st.metric("Tool's Inventive Step", "✅ Yes" if selected_element.inventive_step else "❌ No")
    with col3:
        st.metric("Tool's Verdict", selected_element.verdict)

    st.write("**Your Judgment:**")
    your_verdict = st.radio("Pass/Fail", ["PASS", "FAIL"], key=f"element_verdict_{run_id}_{selected_element_num}")
    critique = st.text_area("Critique", value="", placeholder="Explain your verdict for this element...",
                           key=f"element_critique_{run_id}_{selected_element_num}", height=100)

    return {
        "element_number": selected_element_num,
        "tool_novelty": selected_element.novelty,
        "tool_inventive_step": selected_element.inventive_step,
        "your_verdict": your_verdict,
        "critique": critique,
    }

def overall_opinion_critique_form(trace, run_id):
    """Build overall opinion critique form."""
    st.subheader("Overall Opinion Critique")

    if not trace.parsed_output:
        st.warning("No parsed output found.")
        return None

    st.write("**Tool's Final Verdict:**")
    st.text_area("Overall Opinion", value=trace.parsed_output.overall_opinion, disabled=True, height=150, key=f"overall_opinion_display_{run_id}")

    st.write("**Your Judgment:**")
    your_verdict = st.radio("Pass/Fail", ["PASS", "FAIL"], key=f"overall_verdict_{run_id}")
    critique = st.text_area("Critique", value="", placeholder="Explain your verdict for the overall opinion...",
                           key=f"overall_critique_{run_id}", height=100)

    return {
        "tool_verdict": trace.parsed_output.overall_opinion,
        "your_verdict": your_verdict,
        "critique": critique,
    }

def failure_mode_annotation_form(run_id, phase=1, current_annotation=None, taxonomy=None):
    """Build failure mode annotation form based on phase."""
    st.subheader("Failure Mode Annotation")

    if phase == 1:
        st.write("**Phase 1: Open Coding**")
        failure_modes_text = st.text_input("Open-Coded Failure Modes", value="",
                                          placeholder="Format: hallucination | truncation | claim_mismatch",
                                          key=f"open_failure_modes_{run_id}")
        failure_modes = parse_failure_modes(failure_modes_text)
    else:  # phase == 3
        st.write("**Phase 3: Re-annotation with Taxonomy**")
        failure_modes_text = st.text_input("Failure Modes", value="",
                                          placeholder="Format: mode1 | mode2",
                                          key=f"failure_modes_{run_id}")
        failure_modes = parse_failure_modes(failure_modes_text)

    annotation_text = st.text_area("Annotation/Critique", value="",
                                  placeholder="Describe all failure modes found in this trace...",
                                  key=f"annotation_text_{run_id}", height=120)

    return {"failure_modes": failure_modes, "failure_modes_text": failure_modes_text, "annotation": annotation_text}

def save_annotation(run_id, element_judgments, overall_opinion, failure_modes, annotation_text, phase):
    """Save annotation to session state and file."""
    if not run_id or not annotation_text:
        st.error("Run ID and annotation text are required.")
        return False

    element_objs = [ElementJudgment(**ej) for ej in element_judgments]
    overall_obj = OverallOpinionJudgment(**overall_opinion)

    open_coded = failure_modes if phase == 1 else None
    standardized = failure_modes if phase == 3 else None

    record = AnnotationRecord(
        run_id=run_id, phase=phase, element_judgments=element_objs,
        overall_opinion_judgment=overall_obj, open_coded_failure_modes=open_coded,
        failure_modes=standardized, annotation=annotation_text, reviewed=True,
    )

    st.session_state.annotations[run_id] = record
    save_annotations(ANNOTATIONS_FILE, st.session_state.annotations)
    st.success("Annotation saved!")
    return True

def build_analysis_dashboard():
    """Build tabular view of all annotations."""
    st.subheader("All Annotations")

    rows = []
    for run_id, annotation in st.session_state.annotations.items():
        trace = st.session_state.traces.get(run_id)
        if trace:
            src_label = trace.inputs.get("source_patent", {}).get("label", "?")
            tgt_label = trace.inputs.get("target_patent", {}).get("label", "?")
            failure_modes = annotation.failure_modes or annotation.open_coded_failure_modes or []
            failure_modes_str = "; ".join(failure_modes) if failure_modes else ""

            rows.append({
                "Run ID": run_id[:12] + "...",
                "Status": trace.status,
                "Source": src_label,
                "Target": tgt_label,
                "Failure Modes": failure_modes_str,
                "Phase": annotation.phase,
                "Your Verdict": annotation.overall_opinion_judgment.your_verdict,
                "Reviewed": "✅" if annotation.reviewed else "❌",
                "Annotation": annotation.annotation[:50] + "..." if annotation.annotation else "",
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Frequency analysis
        st.subheader("Failure Mode Frequency")
        all_modes = []
        for annotation in st.session_state.annotations.values():
            modes = annotation.failure_modes or annotation.open_coded_failure_modes or []
            all_modes.extend(modes)

        mode_counts = Counter(all_modes)
        if mode_counts:
            freq_df = pd.DataFrame(sorted(mode_counts.items(), key=lambda x: x[1], reverse=True),
                                 columns=["Failure Mode", "Count"])
            st.bar_chart(freq_df.set_index("Failure Mode"))
            st.dataframe(freq_df, use_container_width=True, hide_index=True)
        else:
            st.info("No failure modes annotated yet.")

        # Verdict summary
        st.subheader("Verdict Summary")
        verdicts = [a.overall_opinion_judgment.your_verdict for a in st.session_state.annotations.values()]
        verdict_counts = Counter(verdicts)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("PASS", verdict_counts.get("PASS", 0))
        with col2:
            st.metric("FAIL", verdict_counts.get("FAIL", 0))

        # Export
        st.divider()
        st.subheader("Export")
        csv = df.to_csv(index=False)
        st.download_button(label="📥 Download as CSV", data=csv, file_name="annotations_export.csv", mime="text/csv")
    else:
        st.info("No annotations yet. Start with Annotation Interface to begin annotating traces.")

# --- Main Navigation ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("View", ["Annotation Interface", "Analysis Dashboard"])
st.sidebar.divider()

# --- Annotation Interface ---
if view == "Annotation Interface":
    st.sidebar.subheader("Trace Navigator")

    search_term = st.sidebar.text_input("Search by Run ID or annotation", value="")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        filter_reviewed = st.selectbox("Reviewed", ["All", "Reviewed", "Unreviewed"])
    with col2:
        filter_phase = st.selectbox("Phase", ["All", "Phase 1", "Phase 3"])

    filtered_traces = []
    for run_id, trace in st.session_state.traces.items():
        annotation = st.session_state.annotations.get(run_id)

        if search_term and search_term.lower() not in run_id.lower():
            if annotation and search_term.lower() not in annotation.annotation.lower():
                continue

        if filter_reviewed == "Reviewed" and (not annotation or not annotation.reviewed):
            continue
        if filter_reviewed == "Unreviewed" and annotation and annotation.reviewed:
            continue

        if filter_phase == "Phase 1" and annotation and annotation.phase != 1:
            continue
        if filter_phase == "Phase 3" and annotation and annotation.phase != 3:
            continue

        filtered_traces.append((run_id, trace, annotation))

    reviewed_count = sum(1 for _, _, a in filtered_traces if a and a.reviewed)
    total_count = len(filtered_traces)
    st.sidebar.progress(reviewed_count / total_count if total_count > 0 else 0)
    st.sidebar.caption(f"Reviewed {reviewed_count}/{total_count} traces")

    st.sidebar.subheader("Traces")
    for run_id, trace, annotation in filtered_traces:
        status_icon = "✅" if annotation and annotation.reviewed else "⭕"
        phase_icon = "🔹" if annotation and annotation.phase == 3 else ""
        label = trace.inputs.get("source_patent", {}).get("label", "?")
        display_text = f"{status_icon} {phase_icon} {label[:15]}..."

        if st.sidebar.button(display_text, key=f"trace_{run_id}", use_container_width=True):
            st.session_state.current_run_id = run_id

    st.divider()

    if st.session_state.current_run_id and st.session_state.current_run_id in st.session_state.traces:
        trace = st.session_state.traces[st.session_state.current_run_id]
        current_annotation = st.session_state.annotations.get(st.session_state.current_run_id)

        col_trace, col_form = st.columns([1.5, 1])

        with col_trace:
            display_trace(trace)

        with col_form:
            st.subheader("Annotation Form")
            element_judgment = element_critique_form(trace, st.session_state.current_run_id, current_annotation)

            st.divider()

            overall_opinion = overall_opinion_critique_form(trace, st.session_state.current_run_id)

            st.divider()

            failure_mode_data = failure_mode_annotation_form(
                st.session_state.current_run_id, phase=st.session_state.phase,
                current_annotation=current_annotation, taxonomy=st.session_state.taxonomy
            )

            st.divider()

            col_save, col_next, col_prev = st.columns(3)

            with col_save:
                if st.button("💾 Save", use_container_width=True):
                    if element_judgment and overall_opinion and failure_mode_data:
                        all_element_judgments = []
                        if trace.parsed_output:
                            for em in trace.parsed_output.element_mappings:
                                all_element_judgments.append({
                                    "element_number": em.element_number,
                                    "tool_novelty": em.novelty,
                                    "tool_inventive_step": em.inventive_step,
                                    "your_verdict": "PASS",
                                    "critique": "",
                                })

                        save_annotation(
                            st.session_state.current_run_id, all_element_judgments,
                            overall_opinion, failure_mode_data["failure_modes"],
                            failure_mode_data["annotation"], st.session_state.phase
                        )
                    else:
                        st.error("Please complete all fields before saving.")

            with col_next:
                if st.button("→ Next", use_container_width=True):
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx < len(trace_ids) - 1:
                        st.session_state.current_run_id = trace_ids[current_idx + 1]
                        st.rerun()
                    else:
                        st.info("No more traces.")

            with col_prev:
                if st.button("← Prev", use_container_width=True):
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx > 0:
                        st.session_state.current_run_id = trace_ids[current_idx - 1]
                        st.rerun()
    else:
        st.info("Select a trace from the sidebar to begin annotation.")

# --- Analysis Dashboard ---
elif view == "Analysis Dashboard":
    build_analysis_dashboard()
