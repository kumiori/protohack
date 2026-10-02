"""Opt-in read-only acceptance check against the current six-person reference cohort."""
import os
import json
import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.skipif(os.getenv('PROBE_RESULTS_LIVE') != '1', reason='Explicit live read opt-in')


def test_six_person_sample_on_public_results_surface(monkeypatch):
    # This explicitly opted-in test overrides the suite-wide offline fixture.
    monkeypatch.setenv("PROTOHACK_DEMO_MODE", "false")
    app = AppTest.from_string('''
import event_ui
from protocol.probe_registry import resolve_event
event_ui.repository_mode=lambda: 'notion'
event_ui.render_event(resolve_event(slug='commons-montreal'))
''', default_timeout=60)
    app.query_params['view'] = 'results'
    app.run()
    assert not bool(app.exception), 'Live Results surface raised an exception'
    assert any('6 PARTICIPANT·ES · 4 REPRÉSENTATIONS' in c.value for c in app.caption)
    paired = next(x.proto.body for x in app.get('html') if '<div class="portrait-pair">' in x.proto.body)
    assert '6 personnes · 11 sélections' in paired
    assert '6 personnes · 14 sélections' in paired
    assert 'Plusieurs choix étaient possibles.' in paired
    assert ' / 6' in paired
    assert not [i for i in app.info if i.value == 'Aucune donnée collective disponible']
    disclosures = [json.loads(item.value) for item in app.json]
    portrait = {item['representation_id']: item['denominator'] for item in disclosures
                if isinstance(item, dict) and item.get('representation_id') in {
                    'participant_portrait.component.1', 'participant_portrait.component.2'}}
    assert portrait['participant_portrait.component.1']['answered'] == 6
    assert portrait['participant_portrait.component.1']['selected'] == 11
    assert portrait['participant_portrait.component.2']['answered'] == 6
    assert portrait['participant_portrait.component.2']['selected'] == 14
    portrait_sources = [item for item in disclosures if isinstance(item, dict) and item.get('representation_id') in portrait]
    assert all(item['snapshot_id'] == 'fd708743f85473bf' for item in portrait_sources)
    assert any('Vue publique agrégée' in c.value for c in app.caption)
    assert app.selectbox[0].label == 'Explorer un acteur'
    app.selectbox[0].select('government').run()
    assert not bool(app.exception), 'Live actor selection raised an exception'
