from copy import deepcopy
from pathlib import Path

from probe_engine import ProbeRuntime, evaluate_representation
from streamlit.testing.v1 import AppTest

from protocol.probe_registry import resolve_probe
from protocol.probe_structures import (derive_exchange_balance, derive_action_actor_graph,
                                      derive_completeness, leaves, provenance, record_rows)
from protocol.probe_topology import topology_html

ROOT = Path(__file__).resolve().parents[1]


def probe():
    return resolve_probe(event_slug='commons-montreal').load()


def result(identifier, population=()):
    p = probe()
    return evaluate_representation(p, identifier, population).to_dict()


def test_empty_composite_preserves_order_and_provenance():
    value = result('future_landscape')
    assert [next(iter(x['provenance']['field_revisions'])) for x in leaves(value)] == [
        'future_outcome', 'future_effects', 'future_conditions', 'future_contribution', 'scenario_position']
    assert all(x['denominator']['answered'] == 0 for x in leaves(value))
    assert 'participation_ids' not in provenance(value)
    assert provenance(value)['snapshot_id']


def test_resolution_and_selection_counts_remain_distinct():
    p = probe()
    a = ProbeRuntime(p, participant_id='private-a', participation_id='private-a', scope_id='fixture')
    b = ProbeRuntime(p, participant_id='private-b', participation_id='private-b', scope_id='fixture')
    c = ProbeRuntime(p, participant_id='private-c', participation_id='private-c', scope_id='fixture')
    a.answer('knowledge_offer', ['commons_principles', 'open_data_evolution'])
    b.skip('knowledge_offer')
    value = result('knowledge_exchange', [a.trajectory, b.trajectory, c.trajectory])
    d = value['data']['denominators']['offer']
    assert (d['cohort'], d['answered'], d['selected'], d['skipped'], d['unanswered']) == (3, 1, 2, 1, 1)
    assert list(value['data']['roles']) == ['offer', 'need']


def test_balance_exact_keys_and_overlapping_structural_states():
    value = result('knowledge_exchange')
    value['data']['roles'] = {'offer': {'a': 1, 'b': 3, 'Similar label': 1},
                              'need': {'a': 3, 'c': 2, 'similar label': 1}}
    original = deepcopy(value)
    derived = derive_exchange_balance(value, same_taxonomy=True)
    rows = {x['taxonomy_value']: x for x in derived['data']}
    assert rows['a']['states'] == ['match', 'relative_gap']
    assert rows['c']['states'] == ['relative_gap', 'unmet_need']
    assert rows['Similar label']['need_count'] == 0
    assert derived['provenance']['snapshot_id'] == value['provenance']['snapshot_id']
    assert value == original
    assert not derive_exchange_balance(value, same_taxonomy=False)['data']['available']


def test_records_not_repaired_and_topology_only_explicit_edges():
    value = leaves(result('future_landscape'))[2]
    value['data']['records'] = [{'participant_id': 'SECRET-UUID', 'value': [
        {'details': '  Exact prose <script> & accents é\nsecond line', 'actors': ['government']},
        {'category': 'Unconnected', 'details': 'No actor'},
        {'category': 'Other', 'actors': ['researcher', 'government']}]}]
    rows = record_rows(value)
    graph = derive_action_actor_graph(value, actor_field='actors', category_field='category')
    assert len(graph['data']['edges']) == 3
    assert graph['data']['actions'][0]['category'] is None
    assert all(e['action'] != 'action-2' for e in graph['data']['edges'])
    assert rows[0]['details'].startswith('  Exact prose')
    completeness = derive_completeness(value, record_fields=('category', 'actors', 'details'))
    assert completeness['data'][0]['missing_record_fields'] == {'category': 1, 'actors': 1, 'details': 1}
    public_html = topology_html(graph, {}, rows, reveal_text=False)
    assert 'SECRET-UUID' not in public_html and 'Exact prose' not in public_html
    disclosed_html = topology_html(graph, {}, rows, reveal_text=True)
    assert '<script> & accents' not in disclosed_html
    assert 'Exact prose \\u003cscript\\u003e' in disclosed_html
    assert '@media(max-width:600px)' in public_html


def app():
    value = AppTest.from_file(str(ROOT / 'tests/fixtures/probe_results_landscape_app.py'))
    value.query_params.update(view='results', test='1')
    return value.run()


def test_route_empty_and_synthetic_all_authored_components_reach_surface():
    value = app()
    assert not value.exception
    assert [h.value for h in value.header] == [
        '01 · LE CHAMP', '02 · LES ÉCHANGES', '03 · L’HORIZON', '04 · LES CHEMINS', '05 · NOS CAPACITÉS D’ACTION']
    assert any('Aucune donnée collective disponible' in x.value for x in value.info)
    value.toggle[0].set_value(True).run()
    assert not value.exception
    assert value.selectbox[0].label == 'Explorer un acteur'
    labels = [e.label for e in value.expander]
    for definition in probe().representations:
        for leaf in leaves(result(definition.id)):
            assert f"ⓘ Données · {leaf['representation_id']}" in labels
    value.selectbox[0].select('government').run()
    assert not value.exception
    assert any('associés' in x.value or 'Source :' in x.value for x in value.caption)
    exposed = ' '.join(x.value for x in value.json)
    assert 'synthetic-1' not in exposed


def test_new_probe_generic_without_layout_or_probe_specific_python():
    code = '''
from dataclasses import replace
from probe_engine import evaluate_representation
from protocol.probe_registry import resolve_probe
from probe_results_ui import render_results_landscape
original=resolve_probe(event_slug='commons-montreal').load()
p=replace(original, id='a-brand-new-probe')
results=[evaluate_representation(p, r, ()).to_dict() for r in p.representations]
render_results_landscape(p, results, view_context={'cohort':0})
'''
    value = AppTest.from_string(code).run()
    assert not value.exception
    assert len(value.header) == 4
    assert any('Aucune donnée collective disponible' in x.value for x in value.info)


def test_zero_selection_differs_from_no_observation_and_grouping_is_visible():
    code = '''
from dataclasses import replace
from probe_engine import evaluate_representation
from protocol.probe_registry import resolve_probe
from probe_results_ui import render_representation
p=resolve_probe(event_slug='commons-montreal').load()
r=evaluate_representation(p,'participant_portrait',()).to_dict()['data']['components'][0]
r['denominator'].update(cohort=5,eligible=5,answered=5,resolved=5,unanswered=0)
r['data']['groups']={'authored-group':{'option_ids':['cultural_action'],'count':0}}
render_representation(p,r,context={})
'''
    value = AppTest.from_string(code).run()
    assert not value.exception
    assert not value.info
    assert any('Aucune option sélectionnée' in x.value for x in value.caption)
    assert any('authored-group' in x.value for x in value.markdown)
    assert any('0 / 5' in x.proto.body for x in value.get('html'))


def test_unknown_type_explicit_and_unlisted_results_never_disappear():
    code = '''
from probe_engine import evaluate_representation
from protocol.probe_registry import resolve_probe
from probe_results_ui import render_results_landscape
p=resolve_probe(event_slug='commons-montreal').load()
r=evaluate_representation(p,'knowledge_exchange',()).to_dict()
r['representation_type']='future_unknown_type'
render_results_landscape(p,[r],view_context={'sections':[{'title':'Custom','representations':[]}]})
'''
    value = AppTest.from_string(code).run()
    assert not value.exception
    assert any('future_unknown_type' in x.value for x in value.warning)


def test_actionability_requires_exact_authored_mapping_and_does_not_claim_people():
    from protocol.probe_structures import derive_actionability
    components = leaves(result('future_landscape'))
    actions, contributions = components[2], components[3]
    actions['data']['records'] = [{'value': [{'category': 'coalition'}, {'category': 'Coalition'}]}]
    contributions['data']['values'] = {'join_coalition': {'count': 3}, 'initiate_coalition': {'count': 1}}
    mapping = {'coalition': {'contribution': ['join_coalition', 'initiate_coalition']}}
    derived = derive_actionability(actions, contributions, mapping, category_field='category')
    assert derived['data'][0]['proposed_records'] == 1
    assert derived['data'][0]['available_selections'] == 4
    assert len(derived['sources']) == 2
    assert derive_actionability(actions, contributions, {}, category_field='category')['data'] == []


def test_explicit_actionability_mapping_reaches_generic_surface():
    code = '''
from probe_engine import evaluate_representation
from protocol.probe_registry import resolve_probe
from probe_results_ui import render_results_landscape
p=resolve_probe(event_slug='commons-montreal').load()
r=evaluate_representation(p,'future_landscape',()).to_dict()
a=r['data']['components'][2]
a['data']['records']=[{'value':[{'category':'coalition','actors':[]}]}]
c=r['data']['components'][3]
c['data']['values']={'join_coalition':{'count':3}}
render_results_landscape(p,[r],view_context={'actionability':{
 'actions':a['representation_id'],'contributions':c['representation_id'],
 'category_field':'category','mapping':{'coalition':{'contribution':['join_coalition']}}}})
'''
    value = AppTest.from_string(code).run()
    assert not value.exception
    assert any('1 propositions · 3 sélections' in x.value for x in value.text)
    assert 'ⓘ Données · chemins et capacités' in [e.label for e in value.expander]


def test_public_structured_data_retains_counts_but_not_identity_or_prose():
    from protocol.probe_structures import public_result
    value = result('future_landscape')
    value['provenance']['participation_ids'] = ['PRIVATE-UUID']
    value['data']['components'][2]['data']['records'] = [{'participant_id': 'PRIVATE-UUID',
                                                       'value': [{'details': 'PRIVATE-PROSE'}]}]
    safe = public_result(value)
    assert 'PRIVATE' not in str(safe)
    assert safe['data']['components'][2]['data']['record_count'] == 1
    assert 'denominator' in safe['data']['components'][0]
    assert 'values' in safe['data']['components'][0]['data']
