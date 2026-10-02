"""Rendered paired-portrait contract; intentionally no browser/screenshot use."""
from html import escape
import json

import pytest
from streamlit.testing.v1 import AppTest

import event_ui
from protocol.probe_registry import resolve_probe
from test_probe_portrait_projection import split_repository


IDS = ('participant_portrait.component.1', 'participant_portrait.component.2')


def panels(app):
    return next(item.proto.body for item in app.get('html') if '<div class="portrait-pair">' in item.proto.body)


def test_actual_montreal_route_pairs_authored_options_and_preserves_restoration(monkeypatch):
    repository = split_repository()
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
    html = panels(app)
    assert '<h3>Secteurs</h3>' in html and '<h3>Fonctions</h3>' in html
    assert '1 personne · 2 sélections' in html  # two choices by one person is valid
    assert 'Plusieurs choix étaient possibles.' in html
    assert html.count('class="portrait-panel"') == 2
    assert '1 / 1' in html and '0 / 1' in html
    assert 'portrait-zero' in html
    probe = resolve_probe(event_slug='commons-montreal').load()
    for taxonomy, section in zip(('sectors', 'functions'), html.split('<section')[1:]):
        labels = [escape(o.label) for o in probe.taxonomy(taxonomy).options]
        assert all(label in section for label in labels)
        assert [section.index(label) for label in labels] == sorted(section.index(label) for label in labels)
    # Confirm the actual emitted pair belongs to Le Champ, before the next section.
    current_header = None
    found = False
    for node in app.main:
        if node.type == 'header':
            current_header = node.value
        if node.type == 'html' and '<div class="portrait-pair">' in node.proto.body:
            assert current_header == '01 · LE CHAMP'
            found = True
    assert found
    disclosures = [json.loads(item.value) for item in app.json]
    for identifier in IDS:
        disclosure = next(item for item in disclosures if isinstance(item, dict) and item.get('representation_id') == identifier)
        assert set(('cohort', 'eligible', 'resolved', 'answered', 'selected', 'unanswered')) <= disclosure['denominator'].keys()
        assert set(('probe_id', 'probe_revision', 'snapshot_id')) <= disclosure.keys()
    assert all('private-person' not in item.value and 'private-player' not in item.value for item in app.json)
    assert 'private-person' not in html and 'trajectory_events' not in html


@pytest.mark.parametrize('answered,selected,unanswered', [(6, 11, 0), (4, 7, 2), (0, 0, 6)])
def test_rendered_portrait_denominator_scale_and_missingness(answered, selected, unanswered):
    app = AppTest.from_string(f'''
from probe_engine import evaluate_representation
from protocol.probe_registry import resolve_probe
from probe_results_ui import render_distribution
p=resolve_probe(event_slug='commons-montreal').load()
r=evaluate_representation(p,'participant_portrait',()).to_dict()['data']['components'][0]
r['denominator'].update(cohort=6,eligible=6,resolved={answered},answered={answered},selected={selected},unanswered={unanswered})
r['data']['values']={{'research':{{'count':{min(answered, 3)}}}}}
r['data']['other']='PRIVATE-OTHER-SPECIFICATION'
r['provenance']['participation_ids']=['PRIVATE-PARTICIPANT']
render_distribution(p,r,presentation='portrait',title='Secteurs')
''').run()
    assert not app.exception
    html = '\n'.join(item.proto.body for item in app.get('html'))
    assert f'{answered} personnes · {selected} sélections' in html
    assert 'PRIVATE-' not in html
    if unanswered:
        assert f'{unanswered} trajectoire(s) sans réponse exploitable' in html
    if answered:
        assert f'{min(answered, 3)} / {answered}' in html
        assert f'style="width:{100 * min(answered, 3) / answered:g}%"' in html
        assert '0 / ' + str(answered) in html
    else:
        assert 'Aucune donnée collective disponible' in html
        assert '0 / 6 réponses résolues' in html
        assert '<ul class="portrait-options">' not in html


def test_rendered_pair_responsive_contract_retains_all_content():
    # AppTest has no viewport or CSS layout engine. Check the emitted responsive
    # contract, not pretend these are measured browser overflow assertions.
    code = '''
import yaml
from probe_engine import evaluate_representation
from protocol.probe_registry import resolve_probe
from probe_results_ui import render_representation
reg=resolve_probe(event_slug='commons-montreal')
p=reg.load()
r=evaluate_representation(p,'participant_portrait',()).to_dict()
layout=yaml.safe_load(reg.source_path.with_suffix('.results.yaml').read_text())
render_representation(p,r,context=layout)
'''
    app = AppTest.from_string(code).run()
    assert not app.exception
    html = panels(app)
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in html
    assert '@media(max-width:700px) {.portrait-pair {grid-template-columns:minmax(0,1fr)' in html
    assert '.portrait-panel {min-width:0;' in html
    assert 'overflow-wrap:anywhere' in html
    assert 'grid-template-columns:minmax(0,1fr) auto' in html
    assert 'overflow:hidden' not in html and 'display:none' not in html
    assert html.count('Aucune donnée collective disponible') == 2
    assert 'tabindex="-1"' not in html
    assert [x.label for x in app.expander][:2] == [f'ⓘ Données · {identifier}' for identifier in IDS]
