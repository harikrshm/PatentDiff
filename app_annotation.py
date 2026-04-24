import streamlit as st
from pathlib import Path
from core.annotation import load_annotations, save_annotations
from core.trace_loader import load_traces

# --- Configuration ---
TRACES_FILE = Path("traces/traces.jsonl")
ANNOTATIONS_FILE = Path("traces/traces_annotations.jsonl")
TAXONOMY_FILE = Path("traces/failure_taxonomy.json")

# --- App Setup ---
st.set_page_config(page_title="PatentDiff Annotation Tool", layout="wide")
st.title("PatentDiff Error Analysis Tool")

# --- Session State ---
if "traces" not in st.session_state:
    st.session_state.traces = {t.run_id: t for t in load_traces(TRACES_FILE)}
if "annotations" not in st.session_state:
    st.session_state.annotations = load_annotations(ANNOTATIONS_FILE)
if "current_run_id" not in st.session_state:
    st.session_state.current_run_id = None

# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
view = st.sidebar.radio("View", ["Annotation Interface", "Analysis Dashboard"])

# --- Main Content ---
if view == "Annotation Interface":
    st.write("Annotation Interface coming soon...")
elif view == "Analysis Dashboard":
    st.write("Analysis Dashboard coming soon...")
