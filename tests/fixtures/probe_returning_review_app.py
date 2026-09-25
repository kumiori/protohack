import streamlit as st
from pathlib import Path
from probe_engine import ProbeRuntime

from probe_ui import render_registered_probe
from protocol.probe_access import access_code_from_key
from protocol.probe_draft import load_probe_state
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository


registration = resolve_probe(event_slug="commons-montreal", variant="short")
probe = registration.load()
participant_id = "returning-review-player"
participation_id = "returning-review-participation"
trajectory = load_probe_state(
    (Path(__file__).parent / "montreal_comprehensive_response.yaml").read_text(
        encoding="utf-8"
    ),
    probe=probe,
    participant_id=participant_id,
    participation_id=participation_id,
    expected_scope_id=registration.session_code,
)
runtime = ProbeRuntime.hydrate(
    probe,
    trajectory=trajectory,
    participant_id=participant_id,
    scope_id=registration.session_code,
)
credential = access_code_from_key("12345678-1234-5678-1234-567812345678")

st.session_state.setdefault(
    f"probe_entry_gate_{registration.session_code}_{probe.id}", participant_id
)
st.session_state.setdefault(
    f"probe_participation_{registration.session_code}", participation_id
)
st.session_state.setdefault(
    f"probe_session_trajectory_{participation_id}", runtime.trajectory
)
st.session_state.setdefault(f"probe_stage_{participation_id}", "review")
st.session_state[f"probe_returning_player_{participant_id}"] = True
st.session_state.setdefault(
    f"probe_player_credential_{participant_id}",
    {
        "emoji": credential.emoji,
        "selector": credential.selector,
        "selector_6": credential.selector_6,
        "verifier": credential.verifier,
    },
)

render_registered_probe(
    registration=registration,
    probe=probe,
    repository=InMemoryRepository(),
    test_mode=True,
)
