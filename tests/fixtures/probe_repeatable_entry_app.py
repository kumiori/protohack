import streamlit as st
from probe_engine import ProbeRuntime

from probe_ui import render_registered_probe
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository


registration = resolve_probe(event_slug="commons-montreal", variant="short")
probe = registration.load()
participant_id = "repeatable-entry-player"
participation_id = "repeatable-entry-participation"
runtime = ProbeRuntime(
    probe,
    participant_id=participant_id,
    participation_id=participation_id,
    scope_id=registration.session_code,
)
runtime.answer("participation_acknowledgement", "accept")
for step in probe.steps:
    if step.id == "future_conditions":
        break
    for field_id in step.field_ids:
        field = probe.question(field_id)
        if field.id != "participation_acknowledgement" and field.visible_if is None:
            runtime.skip(field.id, reason_codes=["prefer_not"])

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
st.session_state.setdefault(
    f"probe_information_steps_{participation_id}", ("future_intro",)
)

render_registered_probe(
    registration=registration,
    probe=probe,
    repository=InMemoryRepository(),
    test_mode=True,
)
