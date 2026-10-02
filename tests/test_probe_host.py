from pathlib import Path
from streamlit.testing.v1 import AppTest

FIXTURE = Path(__file__).parent / 'fixtures' / 'probe_host_app.py'


def app(authenticated=True):
    at = AppTest.from_file(str(FIXTURE), default_timeout=30)
    at.query_params['view'] = 'host'
    at.session_state['host_authenticated'] = authenticated
    return at.run()


def test_host_route_authenticates_before_showing_participant_data(monkeypatch):
    monkeypatch.setenv('PROTOHACK_HOST_CODE', 'fixture-host-code')
    at = app(False)
    assert not at.exception
    assert not at.dataframe
    assert at.text_input[0].label == 'Host access code'
    at.text_input[0].set_value('wrong')
    at.button[0].click().run()
    assert not at.dataframe
    at.text_input[0].set_value('fixture-host-code')
    at.button[0].click().run()
    assert not at.exception
    assert at.dataframe


def test_overview_scopes_submissions_and_preserves_resolution_states():
    at = app()
    assert not at.exception
    assert at.selectbox[0].options == ['Forum Communs de données et IA']
    metrics = {m.label: m.value for m in at.metric}
    assert metrics['Participants'] == '1'
    assert metrics['Completed submissions'] == '1'
    assert metrics['Participants missing contact'] == '0'
    grid = at.dataframe[0].value
    assert grid.shape[0] == 1
    assert grid.filter(like='knowledge_offer').iloc[0, 0] == '● ⚑'
    assert grid.filter(like='dietary_preferences').iloc[0, 0] == 'S'
    assert [s.value for s in at.subheader][:2] == ['Response Field', 'Response Timeline']
    next(b for b in at.button if b.label == 'Refresh data').click().run()
    assert not at.exception


def test_all_dashboard_sections_render_and_keep_operations_available():
    at = app()
    for label in ['Participants', 'Access & Recovery', 'Question set', 'Submissions', 'Event log']:
        at.get('button_group')[0].set_value(label).run()
        assert not at.exception, label
        assert any(e.label == 'Repository diagnostics and test cleanup' for e in at.expander)
        if label == 'Question set':
            assert any('questionnaire_id = montreal_communs_data_ai_short_2026' in c.value for c in at.code)
            assert any('future_conditions' in m.value for m in at.markdown)
        if label == 'Access & Recovery':
            assert any('No access recovery' in i.value for i in at.info)
        if label == 'Event log':
            assert 'metadata' not in at.dataframe[0].value.columns
    next(b for b in at.button if b.label == 'Lock host view').click().run()
    assert not at.dataframe


def test_refresh_reloads_snapshot_and_empty_state():
    at = app()
    repository = at.session_state['fixture_repository']
    repository._probe_trajectories.clear()
    at.run()
    assert next(m.value for m in at.metric if m.label == 'Participants') == '1'
    next(b for b in at.button if b.label == 'Refresh data').click().run()
    assert not at.exception
    assert next(m.value for m in at.metric if m.label == 'Participants') == '0'
    assert any('No response field' in i.value for i in at.info)


def test_read_failure_does_not_render_false_zeroes_or_exception_details():
    at = app()
    repository = at.session_state['fixture_repository']
    def fail():
        raise RuntimeError('sensitive-internal-detail')
    repository.list_probe_response_audit_rows = fail
    next(b for b in at.button if b.label == 'Refresh data').click().run()
    assert not at.exception
    assert any('Host data could not be loaded' in e.value for e in at.error)
    assert 'Participants' not in [m.label for m in at.metric]
    assert 'sensitive-internal-detail' not in str(at)


def test_latest_revision_and_allowlisted_log():
    from probe_host_ui import load_snapshot
    from protocol.probe_registry import resolve_probe
    at = app()
    repository = at.session_state['fixture_repository']
    source = next(iter(repository._probe_trajectories.values()))
    from copy import deepcopy
    latest = deepcopy(source)
    latest.update(submission_id='latest', integrated_at='2026-10-02T09:00:00+00:00')
    latest['trajectory']['events'][0]['value'] = 'Updated name'
    latest['trajectory']['events'][0]['metadata'] = {'credential': 'never-render-this'}
    repository.save_probe_trajectory(latest)
    registration = resolve_probe(event_slug='commons-montreal')
    snapshot = load_snapshot(repository, registration, registration.load())
    assert len(snapshot['participants']) == 1
    assert snapshot['participants'][0]['Participant'] == 'Updated name'
    assert snapshot['participants'][0]['Submission'] == 'latest'
    assert 'never-render-this' not in str(snapshot)


def test_test_cleanup_remains_reachable_on_host_surface():
    at = app()
    at.query_params['test'] = '1'
    at.run()
    assert not at.exception
    assert any(b.label == 'Dry-run cleanup scope' for b in at.button)
    assert any(s.value == 'Nettoyer les données de test' for s in at.subheader)
