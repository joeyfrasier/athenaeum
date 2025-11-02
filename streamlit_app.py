"""Streamlit UI for the Worksuite Temporal agent prototype."""
from __future__ import annotations

import json
from typing import Any, Dict

import streamlit as st

from worksuite_agent.examples.sample_data import SAMPLE_TABLES
from worksuite_agent.orchestration import generate_diagrams_locally
from worksuite_agent.repository import InMemoryConfigurationRepository
from worksuite_agent.visualization import summarize_configuration


st.set_page_config(page_title="Worksuite SE Assistant", page_icon="🤖", layout="wide")

st.title("🤖 Worksuite Solution Engineering Assistant")
st.write(
    "This prototype leverages Temporal-style orchestration to inspect a customer tenant "
    "configuration and produce Mermaid diagrams for Solution Engineers."
)

with st.sidebar:
    st.header("Configuration Source")
    tenant_id = st.text_input("Tenant ID", value="tenant-123")
    data_source = st.radio(
        "Load data from",
        options=("Sample dataset", "Upload JSON"),
        help="Upload a JSON document with table -> rows structure to mirror Worksuite tables.",
    )

    uploaded_data: Dict[str, Any] | None = None
    if data_source == "Upload JSON":
        uploaded_file = st.file_uploader("Tenant export (JSON)", type="json")
        if uploaded_file is not None:
            try:
                parsed = json.load(uploaded_file)
            except json.JSONDecodeError as exc:
                st.error(f"Could not parse JSON: {exc}")
            else:
                if not isinstance(parsed, dict):
                    st.error("Expected a JSON object mapping table name to rows.")
                else:
                    uploaded_data = parsed
    else:
        uploaded_data = SAMPLE_TABLES

    run_button = st.button("Generate diagrams", type="primary")

if run_button:
    if not uploaded_data:
        st.warning("Provide configuration data to continue.")
        st.stop()

    try:
        repository = InMemoryConfigurationRepository(uploaded_data)
        diagrams = generate_diagrams_locally(tenant_id=tenant_id, repository=repository)
        configuration = repository.load_configuration(tenant_id)
    except Exception as exc:  # pragma: no cover - surfaced to UI
        st.error(f"Failed to generate diagrams: {exc}")
    else:
        st.success("Diagrams generated successfully.")

        st.subheader("Tenant summary")
        for bullet in summarize_configuration(configuration):
            st.markdown(f"- {bullet}")

        st.subheader("Mermaid diagrams")
        for name, diagram in diagrams.items():
            st.markdown(f"**{name.replace('_', ' ').title()}**")
            st.markdown(f"```mermaid\n{diagram}\n```")
else:
    st.info("Use the sidebar to choose a configuration source and generate diagrams.")
