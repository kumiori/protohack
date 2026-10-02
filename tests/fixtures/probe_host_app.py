from unittest.mock import patch
import streamlit as st
from probe_engine import ProbeRuntime
from protocol.probe_registry import resolve_probe
from storage.memory import InMemoryRepository
from event_ui import event_page

registration = resolve_probe(event_slug='commons-montreal')
if 'fixture_repository' not in st.session_state:
    repository = InMemoryRepository()
    runtime = ProbeRuntime(registration.load(), participant_id='player-a', participation_id='participation-a', scope_id=registration.session_code)
    runtime.answer('name', 'Alice')
    runtime.answer('email', 'alice@example.org')
    runtime.answer('knowledge_offer', ['commons_principles'])
    runtime.flag('knowledge_offer')
    runtime.skip('dietary_preferences')
    row = dict(record_type='probe_submission', event_id=registration.session_code,
        probe_id=registration.probe_id, probe_revision=5, submission_id='submission-a',
        participant_id='player-a', participation_id='participation-a', state='submitted',
        integrated=True, integrated_at='2026-10-02T07:00:00+00:00',
        payload={'schema': 'probe-submission/v1'}, trajectory=runtime.trajectory.to_dict())
    repository.save_probe_trajectory(row)
    repository.save_probe_trajectory({**row, 'submission_id': 'foreign', 'event_id': 'foreign-event'})
    st.session_state.fixture_repository = repository
with patch('event_ui.get_test_repository', return_value=st.session_state.fixture_repository), patch('event_ui.get_repository', return_value=st.session_state.fixture_repository), patch('event_ui.repository_mode', return_value='production'):
    event_page('commons-montreal')
