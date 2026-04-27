import streamlit as st
import pandas as pd
import json
from pathlib import Path
from collections import Counter
from datetime import datetime
from typing import Optional, Dict
from core.annotation import (
    load_annotations, save_annotations, detect_phase, load_taxonomy,
    parse_failure_modes, AnnotationRecord
)
from core.trace_loader import load_traces

# --- Configuration ---
TRACES_FILE = Path("traces/traces.jsonl")
ANNOTATIONS_FILE = Path("traces/traces_annotations.jsonl")
TAXONOMY_FILE = Path("failure_taxonomy.json")

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

    # Row 1: Run ID, Source, Status
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Run ID:** {trace.run_id[:12]}...")
    with col2:
        src_label = trace.inputs.get("source_patent", {}).get("label", "N/A")
        st.write(f"**Source:** {src_label}")
    with col3:
        st.write(f"**Status:** {trace.status}")

    # Row 2: Claim Type, Claim Length, Relationship
    dimensions = trace.dimensions or {}
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Claim Type:** {dimensions.get('claim_type', 'N/A')}")
    with col2:
        st.write(f"**Claim Length:** {dimensions.get('claim_length', 'N/A')}")
    with col3:
        st.write(f"**Relationship:** {dimensions.get('relationship', 'N/A')}")

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



def annotation_form(run_id: str, previous_annotation: Optional[AnnotationRecord] = None, phase: int = 1) -> Dict:
    """Build annotation form for Phase 1 or Phase 3."""
    st.subheader("Annotation Form")

    # Pre-fill with previous annotation if it exists
    prev_verdict = previous_annotation.verdict if previous_annotation else "PASS"
    prev_comment = previous_annotation.comment if previous_annotation else ""
    prev_reviewed = previous_annotation.reviewed if previous_annotation else False

    # PHASE 1: Open Coding (Free-form)
    if phase == 1:
        prev_failure_modes = " | ".join(previous_annotation.open_coded_failure_modes) if previous_annotation and previous_annotation.open_coded_failure_modes else ""

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
        failure_modes_ids = failure_modes

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
            "failure_modes_ids": failure_modes_ids,
            "comment": comment,
            "reviewed": reviewed,
        }

    # PHASE 3: Re-annotation with Standardized Taxonomy
    else:
        taxonomy = st.session_state.taxonomy if st.session_state.taxonomy else {}
        failure_categories = {cat['id']: cat['name'] for cat in taxonomy.get('failure_categories', [])}
        category_names = [cat['name'] for cat in taxonomy.get('failure_categories', [])]

        st.write("**VERDICT:**")
        verdict = st.radio(
            "Pass/Fail",
            ["PASS", "FAIL"],
            index=0 if prev_verdict == "PASS" else 1,
            key=f"verdict_{run_id}",
            horizontal=True
        )

        failure_modes = []
        failure_modes_ids = []

        if verdict == "FAIL":
            st.write("**FAILURE MODES:** (Required for FAIL verdict)")

            # Get previous failure modes for defaults
            prev_failure_modes_names = []
            if previous_annotation and previous_annotation.failure_modes:
                prev_failure_modes_names = [
                    failure_categories.get(mode_id, mode_id)
                    for mode_id in previous_annotation.failure_modes
                ]

            # Multi-select for failure modes
            failure_modes = st.multiselect(
                "Select failure modes that apply to this trace:",
                options=category_names,
                default=prev_failure_modes_names,
                key=f"failure_modes_{run_id}"
            )

            # Map category names back to IDs
            if failure_modes and taxonomy:
                failure_modes_ids = [
                    cat['id']
                    for cat in taxonomy.get('failure_categories', [])
                    if cat['name'] in failure_modes
                ]

            if not failure_modes:
                st.warning("⚠️ FAIL verdict requires at least one failure mode")
        else:
            st.info("✓ PASS verdict: no failure modes applicable")
            failure_modes_ids = []

        st.write("**COMMENT:**")
        comment = st.text_area(
            "Explain the verdict and failure modes",
            value=prev_comment,
            placeholder="Describe the verdict and failure modes you found...",
            key=f"comment_{run_id}",
            height=150
        )

        reviewed = st.checkbox("Reviewed", value=prev_reviewed, key=f"reviewed_{run_id}")

        return {
            "verdict": verdict,
            "failure_modes": failure_modes,
            "failure_modes_ids": failure_modes_ids,
            "comment": comment,
            "reviewed": reviewed,
        }

def save_annotation(run_id, verdict, failure_modes, failure_modes_ids, comment, reviewed, phase=1):
    """Save annotation to session state and file."""
    # Validation
    errors = []

    if not comment:
        errors.append("Comment is required")

    if verdict == "PASS" and failure_modes:
        errors.append("PASS verdict cannot have failure modes selected")

    if verdict == "FAIL" and not failure_modes:
        errors.append("FAIL verdict requires at least one failure mode")

    if errors:
        for error in errors:
            st.error(f"❌ {error}")
        return False

    # Get dimensions from trace
    trace = st.session_state.traces.get(run_id)
    dimensions = trace.dimensions if trace else None

    # Create record based on phase
    if phase == 1:
        record = AnnotationRecord(
            run_id=run_id,
            phase=1,
            open_coded_failure_modes=failure_modes_ids if verdict == "FAIL" else [],
            verdict=verdict,
            comment=comment,
            reviewed=reviewed,
            dimensions=dimensions,
        )
    else:
        record = AnnotationRecord(
            run_id=run_id,
            phase=3,
            failure_modes=failure_modes_ids if verdict == "FAIL" else [],
            verdict=verdict,
            comment=comment,
            reviewed=reviewed,
            dimensions=dimensions,
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

# Phase selector
st.sidebar.divider()
st.sidebar.subheader("Phase Selection")
phase_option = st.sidebar.radio(
    "Coding Phase",
    [1, 3],
    format_func=lambda x: f"Phase {x}: {'Open Coding (Free-form)' if x == 1 else 'Re-annotation (Standardized)'}",
    key="phase_selector"
)
st.session_state.phase = phase_option

st.sidebar.divider()

# --- Annotation Interface ---
if view == "Annotation Interface":
    st.sidebar.subheader("Trace Navigator")

    # Filter out token_limit traces (not for error analysis)
    token_limit_run_ids = set()
    try:
        with open(ANNOTATIONS_FILE, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if 'token_limit' in record.get('open_coded_failure_modes', []) or \
                       'toke_limit' in record.get('open_coded_failure_modes', []):
                        token_limit_run_ids.add(record['run_id'])
                except:
                    pass
    except:
        pass

    search_term = st.sidebar.text_input("Search by Run ID or comment", value="")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        filter_verdict = st.selectbox("Verdict", ["All", "PASS", "FAIL"])
    with col2:
        filter_reviewed = st.selectbox("Reviewed", ["All", "Reviewed", "Unreviewed"])

    # Build filtered trace list (excluding token_limit traces)
    filtered_traces = []
    for run_id, trace in st.session_state.traces.items():
        # Skip token_limit traces
        if run_id in token_limit_run_ids:
            continue
        annotation = st.session_state.annotations.get(run_id)

        if search_term:
            if search_term.lower() not in run_id.lower():
                if not annotation or search_term.lower() not in (annotation.comment or "").lower():
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
            form_data = annotation_form(st.session_state.current_run_id, previous_annotation, phase=st.session_state.phase)

            st.divider()

            col_save, col_next, col_prev = st.columns(3)

            with col_save:
                if st.button("💾 Save", use_container_width=True):
                    if save_annotation(
                        st.session_state.current_run_id,
                        form_data["verdict"],
                        form_data["failure_modes"],
                        form_data["failure_modes_ids"],
                        form_data["comment"],
                        form_data["reviewed"],
                        phase=st.session_state.phase
                    ):
                        st.rerun()  # Refresh to show updated data

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
