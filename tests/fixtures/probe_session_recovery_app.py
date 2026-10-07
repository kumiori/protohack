import streamlit as st

from probe_ui import render_registered_probe
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository


registration = resolve_probe(event_slug="commons-montreal", variant="short")
repository = st.session_state.setdefault(
    "session_recovery_repository", InMemoryRepository()
)
render_registered_probe(
    registration=registration,
    probe=registration.load(),
    repository=repository,
    test_mode=False,
)
