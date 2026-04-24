import streamlit as st
import pandas as pd
from pathlib import Path
from collections import Counter
from core.annotation import (
    load_annotations, save_annotations, detect_phase, load_taxonomy,
    parse_failure_modes, AnnotationRecord
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
        st.text_area("Spec A", value=src.get('specification', ''), disabled=True, height=250, key="src_spec")

    with col_b:
        st.subheader("Target Patent (B)")
        tgt = trace.inputs.get("target_patent", {})
        st.write(f"**Label:** {tgt.get('label', 'N/A')}")
        st.write("**Independent Claim:**")
        st.text_area("Claim B", value=tgt.get('independent_claim', ''), disabled=True, height=100, key="tgt_claim")
        st.write("**Specification:**")
        st.text_area("Spec B", value=tgt.get('specification', ''), disabled=True, height=250, key="tgt_spec")

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



def annotation_form(run_id, previous_annotation=None):
    """Build simplified annotation form for Phase 1 (verdict + failure modes + comment)."""
    st.subheader("Annotation Form")

    # Pre-fill with previous annotation if it exists
    prev_verdict = previous_annotation.verdict if previous_annotation else "PASS"
    prev_failure_modes = " | ".join(previous_annotation.open_coded_failure_modes) if previous_annotation and previous_annotation.open_coded_failure_modes else ""
    prev_comment = previous_annotation.comment if previous_annotation else ""
    prev_reviewed = previous_annotation.reviewed if previous_annotation else False

    st.write("**Trace Quality Verdict:**")
    verdict = st.radio(
        "Pass/Fail",
        ["PASS", "FAIL"],
        index=0 if prev_verdict == "PASS" else 1,
        key=f"verdict_{run_id}",
        horizontal=True
    )

    st.write("**Failure Modes:**")
    failure_modes_text = st.text_input(
        "Delimited failure modes",
        value=prev_failure_modes,
        placeholder="Format: hallucination | truncation | claim_mismatch",
        key=f"failure_modes_{run_id}"
    )
    failure_modes = parse_failure_modes(failure_modes_text)

    st.write("**Comment:**")
    comment = st.text_area(
        "Explain the failure modes",
        value=prev_comment,
        placeholder="Describe what failure modes you found and why...",
        key=f"comment_{run_id}",
        height=150
    )

    reviewed = st.checkbox("Reviewed", value=prev_reviewed, key=f"reviewed_{run_id}")

    return {
        "verdict": verdict,
        "failure_modes": failure_modes,
        "comment": comment,
        "reviewed": reviewed,
    }

def save_annotation(run_id, verdict, failure_modes, comment, reviewed):
    """Save annotation to session state and file."""
    if not comment:
        st.error("Comment is required.")
        return False

    if verdict == "FAIL" and not failure_modes:
        st.warning("FAIL verdict but no failure modes noted. Please add at least one mode or mark as PASS.")
        return False

    record = AnnotationRecord(
        run_id=run_id,
        phase=1,
        open_coded_failure_modes=failure_modes,
        verdict=verdict,
        comment=comment,
        reviewed=reviewed,
    )

    st.session_state.annotations[run_id] = record
    save_annotations(ANNOTATIONS_FILE, st.session_state.annotations)
    st.success("Annotation saved!")
    return True

def build_analysis_dashboard():
    """Build simplified analysis dashboard for Phase 1."""
    st.subheader("All Annotations")

    if not st.session_state.annotations:
        st.info("No annotations yet. Start with Annotation Interface to annotate traces.")
        return

    # Build dataframe
    rows = []
    for run_id, annotation in st.session_state.annotations.items():
        trace = st.session_state.traces.get(run_id)
        if trace:
            src_label = trace.inputs.get("source_patent", {}).get("label", "?")
            tgt_label = trace.inputs.get("target_patent", {}).get("label", "?")
            failure_modes = annotation.open_coded_failure_modes or []
            failure_modes_str = "; ".join(failure_modes) if failure_modes else "none"

            rows.append({
                "Run ID": run_id[:12] + "...",
                "Status": trace.status,
                "Source": src_label,
                "Target": tgt_label,
                "Verdict": annotation.verdict,
                "Failure Modes": failure_modes_str,
                "Comment": annotation.comment[:50] + "..." if annotation.comment else "",
                "Reviewed": "✅" if annotation.reviewed else "❌",
            })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Failure mode frequency
    st.subheader("Failure Mode Frequency")
    all_modes = []
    for annotation in st.session_state.annotations.values():
        modes = annotation.open_coded_failure_modes or []
        all_modes.extend(modes)

    from collections import Counter
    mode_counts = Counter(all_modes)

    if mode_counts:
        freq_df = pd.DataFrame(
            sorted(mode_counts.items(), key=lambda x: x[1], reverse=True),
            columns=["Failure Mode", "Count"]
        )
        st.bar_chart(freq_df.set_index("Failure Mode"))
        st.dataframe(freq_df, use_container_width=True, hide_index=True)
    else:
        st.info("No failure modes annotated yet.")

    # Verdict summary
    st.subheader("Verdict Summary")
    verdicts = [a.verdict for a in st.session_state.annotations.values()]
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
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name="annotations_export.csv",
        mime="text/csv"
    )

# --- Main Navigation ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("View", ["Annotation Interface", "Analysis Dashboard"])
st.sidebar.divider()

# --- Annotation Interface ---
if view == "Annotation Interface":
    st.sidebar.subheader("Trace Navigator")

    search_term = st.sidebar.text_input("Search by Run ID or comment", value="")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        filter_verdict = st.selectbox("Verdict", ["All", "PASS", "FAIL"])
    with col2:
        filter_reviewed = st.selectbox("Reviewed", ["All", "Reviewed", "Unreviewed"])

    # Build filtered trace list
    filtered_traces = []
    for run_id, trace in st.session_state.traces.items():
        annotation = st.session_state.annotations.get(run_id)

        if search_term:
            if search_term.lower() not in run_id.lower():
                if not annotation or search_term.lower() not in annotation.comment.lower():
                    continue

        if filter_verdict != "All" and annotation and annotation.verdict != filter_verdict:
            continue

        if filter_reviewed == "Reviewed" and (not annotation or not annotation.reviewed):
            continue
        if filter_reviewed == "Unreviewed" and annotation and annotation.reviewed:
            continue

        filtered_traces.append((run_id, trace, annotation))

    # Progress bar
    reviewed_count = sum(1 for _, _, a in filtered_traces if a and a.reviewed)
    total_count = len(filtered_traces)
    st.sidebar.progress(reviewed_count / total_count if total_count > 0 else 0)
    st.sidebar.caption(f"Reviewed {reviewed_count}/{total_count} traces")

    # Trace list
    st.sidebar.subheader("Traces")
    for run_id, trace, annotation in filtered_traces:
        status_icon = "✅" if annotation and annotation.reviewed else "⭕"
        label = trace.inputs.get("source_patent", {}).get("label", "?")
        display_text = f"{status_icon} {label[:15]}..."

        if st.sidebar.button(display_text, key=f"trace_{run_id}", use_container_width=True):
            st.session_state.current_run_id = run_id

    st.divider()

    if st.session_state.current_run_id and st.session_state.current_run_id in st.session_state.traces:
        trace = st.session_state.traces[st.session_state.current_run_id]

        col_trace, col_form = st.columns([1.5, 1])

        with col_trace:
            display_trace(trace)

        with col_form:
            previous_annotation = st.session_state.annotations.get(st.session_state.current_run_id)
            form_data = annotation_form(st.session_state.current_run_id, previous_annotation)

            st.divider()

            col_save, col_next, col_prev = st.columns(3)

            with col_save:
                if st.button("💾 Save", use_container_width=True):
                    if save_annotation(
                        st.session_state.current_run_id,
                        form_data["verdict"],
                        form_data["failure_modes"],
                        form_data["comment"],
                        form_data["reviewed"]
                    ):
                        pass  # Success message already shown

            with col_next:
                if st.button("→ Next", use_container_width=True):
                    trace_ids = list(st.session_state.traces.keys())
                    current_idx = trace_ids.index(st.session_state.current_run_id)
                    if current_idx < len(trace_ids) - 1:
                        st.session_state.current_run_id = trace_ids[current_idx + 1]
                        st.rerun()

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
