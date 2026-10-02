"""Results must hydrate split Player events after selecting audited submissions."""
from copy import deepcopy
import json
from types import SimpleNamespace

from probe_engine import ProbeRuntime
from streamlit.testing.v1 import AppTest

import event_ui
from protocol.probe_registry import resolve_probe
from storage.base import RepositoryHealth
from storage.notion import NotionRepository


def split_repository():
    registration = resolve_probe(event_slug='commons-montreal')
    probe = registration.load()
    runtime = ProbeRuntime(probe, participant_id='private-person',
                           participation_id='private-participation', scope_id=registration.session_code)
    runtime.answer('sectors', ['research', 'technology'])
    runtime.answer('functions', ['research_teaching'])
    runtime.answer('participation_position', 'individual')
    full = runtime.trajectory.to_dict()
    profile_events = [e for e in full['events'] if e.get('question_id') in {'sectors', 'functions'}]
    response = deepcopy(full)
    response['events'] = [e for e in full['events'] if e.get('question_id') not in {'sectors', 'functions'}]
    envelope = {
        'record_type': 'probe_submission', 'event_id': registration.session_code,
        'probe_id': probe.id, 'probe_revision': probe.revision,
        'participant_id': 'private-person', 'participation_id': 'private-participation',
        'submission_id': 'selected-submission', 'state': 'submitted',
        'integrated_at': '2026-10-01T00:00:00+00:00', 'revision': 1,
        'payload': {'schema': 'probe-submission/v1'}, 'trajectory': response,
    }
    def rich(value):
        return {'rich_text': [{'plain_text': value, 'text': {'content': value}}]}
    response_page = {'id': 'selected-page', 'properties': {
        'value_json': rich(json.dumps(envelope)), 'player': {'relation': [{'id': 'private-player'}]}}}
    player_page = {'id': 'private-player', 'properties': {
        'profile_json': rich(json.dumps({'trajectory_events': profile_events,
                                         'answer_field_ids': ['sectors', 'functions']}))}}
    repository = object.__new__(NotionRepository)
    repository._query_all = lambda *args, **kwargs: [deepcopy(response_page)]
    repository._client = SimpleNamespace(pages=SimpleNamespace(retrieve=lambda **kwargs: deepcopy(player_page)))
    repository.health_check = lambda: RepositoryHealth(available=True, integration='fixture', data_source_id='fixture', status='available')
    return repository


def test_results_route_restores_profile_events_before_evaluation(monkeypatch):
    repository = split_repository()
    # Physical audit data really has no profile events; the canonical loader has them.
    audit_row = repository.list_probe_response_audit_rows()[0]
    assert not any(e.get('question_id') == 'sectors' for e in audit_row['trajectory']['events'])
    monkeypatch.setattr(event_ui, 'get_repository', lambda: repository)
    monkeypatch.setattr(event_ui, 'repository_mode', lambda: 'notion')
    app = AppTest.from_string('''
from event_ui import render_event
from protocol.probe_registry import resolve_event
render_event(resolve_event(slug='commons-montreal'))
''')
    app.query_params['view'] = 'results'
    app.run()
    assert not app.exception
    disclosures = [json.loads(value.value) for value in app.json]
    portrait = [value for value in disclosures if isinstance(value, dict)
                and value.get('representation_id') in {'participant_portrait.component.1', 'participant_portrait.component.2'}]
    assert len(portrait) == 2
    assert [value['denominator']['answered'] for value in portrait] == [1, 1]
    assert [value['denominator']['selected'] for value in portrait] == [2, 1]
    assert all('private-person' not in value.value for value in app.json)
