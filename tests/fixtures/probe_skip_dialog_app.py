import streamlit as st
from probe_engine import ProbeRuntime

from probe_ui import render_registered_probe
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository


registration = resolve_probe(event_slug="commons-montreal", variant="short")
probe = registration.load()
participant_id = "skip-dialog-player"
participation_id = "skip-dialog-participation"
runtime = ProbeRuntime(
    probe,
    participant_id=participant_id,
    participation_id=participation_id,
    scope_id=registration.session_code,
)
runtime.answer("participation_acknowledgement", "accept")

st.session_state.setdefault(
    f"probe_entry_gate_{registration.session_code}_{probe.id}", participant_id
)
st.session_state.setdefault(
    f"probe_participation_{registration.session_code}", participation_id
)
st.session_state.setdefault(
    f"probe_session_trajectory_{participation_id}", runtime.trajectory
)
st.session_state.setdefault(f"probe_stage_{participation_id}", "steps")

render_registered_probe(
    registration=registration,
    probe=probe,
    repository=InMemoryRepository(),
    test_mode=True,
)
