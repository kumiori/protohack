"""Pure, inspectable structures downstream of canonical RepresentationResults.

No storage, UI, raw trajectories, text classification or response repair here.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


def leaves(result: dict) -> list[dict]:
    if result['representation_type'] == 'composite':
        return [leaf for child in result['data'].get('components', []) for leaf in leaves(child)]
    return [result]


def provenance(result: dict) -> dict:
    value = deepcopy(result.get('provenance', {}))
    value['participation_ids_count'] = len(value.pop('participation_ids', []))
    value.pop('scope_ids', None)
    return {'representation_id': result['representation_id'], **value,
            'denominator': deepcopy(result['denominator'])}


def structure(result: dict, kind: str, method: str, data: Any) -> dict:
    return {'schema': 'probe-derived-structure/v1',
            'id': f"{result['representation_id']}.{kind}", 'kind': kind,
            'sources': [{'representation_id': result['representation_id']}],
            'derivation': {'method': method}, 'data': data,
            'provenance': {**provenance(result), 'representation_ids': [result['representation_id']]}}


def derive_exchange_balance(result: dict, *, same_taxonomy: bool) -> dict:
    roles = result['data'].get('roles', {})
    if not same_taxonomy or set(roles) != {'offer', 'need'}:
        return structure(result, 'bilateral_balance', 'exact_taxonomy_key_comparison',
                         {'available': False, 'reason': 'Requires offer/need roles and one authored taxonomy.'})
    offer, need = roles['offer'], roles['need']
    rows = []
    for key in dict.fromkeys([*offer, *need]):
        a, b = offer.get(key, 0), need.get(key, 0)
        states = []
        if a and b:
            states.append('match')
        if a > b:
            states.append('relative_surplus')
        if b > a:
            states.append('relative_gap')
        if not a and b:
            states.append('unmet_need')
        if not b and a:
            states.append('unrequested_capacity')
        rows.append({'taxonomy_value': key, 'offer_count': a, 'need_count': b,
                     'balance': a-b, 'states': states})
    return structure(result, 'bilateral_balance', 'exact_taxonomy_key_comparison', rows)


def record_rows(result: dict) -> list[dict]:
    rows = []
    for envelope in result['data'].get('records', []):
        value = envelope.get('value')
        for row in value if isinstance(value, list) else [value]:
            rows.append(deepcopy(row) if isinstance(row, dict) else {'value': row})
    return rows


def derive_action_actor_graph(result: dict, *, actor_field: str, category_field: str) -> dict:
    """Each record remains a distinct action; edges use only its explicit actors."""
    actions, edges, actors = [], [], Counter()
    for index, row in enumerate(record_rows(result)):
        action_id = f'action-{index+1}'
        actions.append({'id': action_id, 'category': row.get(category_field), 'record_index': index})
        values = row.get(actor_field) or []
        if not isinstance(values, list):
            values = [values]
        for actor in dict.fromkeys(str(value) for value in values):
            actors[actor] += 1
            edges.append({'action': action_id, 'actor': actor, 'count': 1})
    return structure(result, 'bipartite_graph', 'explicit_record_relations_only',
                     {'actions': actions, 'actors': dict(actors), 'edges': edges})


def derive_completeness(result: dict, *, record_fields: tuple[str, ...] | dict[str, tuple[str, ...]] = ()) -> dict:
    components = []
    for leaf in leaves(result):
        d = leaf['denominator']
        fields = record_fields.get(leaf['representation_id'], ()) if isinstance(record_fields, dict) else record_fields
        rows = record_rows(leaf) if leaf['representation_type'] == 'records' else []
        components.append({'representation_id': leaf['representation_id'],
                           'denominator': deepcopy(d),
                           'unresolved': d.get('unanswered', 0),
                           'records': len(rows),
                           'missing_record_fields': {key: sum(row.get(key) in (None, '', []) for row in rows)
                                                     for key in fields} if rows else {},
                           'provenance': provenance(leaf)})
    return structure(result, 'completeness', 'canonical_resolution_and_record_presence', components)


def derive_actionability(actions: dict, contributions: dict, mapping: dict, *, category_field: str) -> dict:
    """Compare only an explicit authored map; quantities are records and selections.

    A contribution selection is not a unique participant across multiple keys.
    Mapping keys are exact canonical category values, never normalised free text.
    """
    counts = Counter(row.get(category_field) for row in record_rows(actions)
                     if isinstance(row.get(category_field), str))
    values = contributions['data'].get('values', {})
    data = [{'category': key, 'proposed_records': counts.get(key, 0),
             'available_selections': sum(values.get(value, {}).get('count', 0)
                                         for value in dict.fromkeys(spec['contribution'])),
             'contribution_keys': list(dict.fromkeys(spec['contribution']))}
            for key, spec in mapping.items()]
    result = structure(actions, 'actionability', 'authored_exact_key_mapping', data)
    result['sources'].append({'representation_id': contributions['representation_id']})
    result['provenance']['representation_ids'].append(contributions['representation_id'])
    result['provenance']['contributions'] = provenance(contributions)
    result['derivation']['mapping'] = deepcopy(mapping)
    return result


def public_result(result: dict) -> dict:
    """Inspectable aggregate payload with no participant IDs or record prose."""
    kind = result['representation_type']
    if kind == 'composite':
        data = {'components': [public_result(child) for child in result['data'].get('components', [])]}
    elif kind in {'distribution', 'grouped_distribution', 'comparison'}:
        data = deepcopy(result['data'])
    elif kind == 'records':
        data = {'record_count': len(record_rows(result)), 'public_records': 'aggregate'}
    else:
        data = {'unsupported_type': kind}
    return {**{key: deepcopy(value) for key, value in result.items() if key not in {'data', 'provenance'}},
            'data': data, 'provenance': provenance(result)}
