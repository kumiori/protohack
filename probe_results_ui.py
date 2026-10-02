"""Generic Streamlit consumer of Probe Engine's canonical representation contract."""
from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from protocol.probe_topology import topology_html
from probe_theme import PROBE_COLORS, typography_css
from protocol.probe_structures import (
    derive_action_actor_graph, derive_actionability, derive_completeness, derive_exchange_balance,
    leaves, provenance, record_rows,
)

STATE_LABELS = {'cohort': 'Cohorte', 'eligible': 'Éligibles', 'resolved': 'Résolu',
                'answered': 'Répondu', 'selected': 'Sélections', 'skipped': 'Passé',
                'flagged': 'Signalé', 'deferred': 'Différé', 'unanswered': 'Sans réponse'}
ROLE_LABELS = {'offer': 'Nous pouvons partager', 'need': 'Nous recherchons'}


def render_denominator(denominator: dict, *, label: str = '') -> None:
    d = denominator
    st.caption(f"{label + ' · ' if label else ''}{d.get('answered', 0)} / {d.get('eligible', 0)} réponses · "
               f"{d.get('selected', 0)} sélections")
    with st.expander(f"Dénominateur{(' · ' + label) if label else ''}"):
        for key, title in STATE_LABELS.items():
            st.text(f"{title} : {d.get(key, 0)}")
        st.caption('Les états ne sont pas tous exclusifs : un signalement peut accompagner une réponse.')


def _fields(probe: Any, result: dict) -> list:
    return [probe.question(key) for key in result['provenance'].get('field_revisions', {})]


def _options(probe: Any, field: Any) -> dict:
    options = probe.taxonomy(field.taxonomy_id).options if field.taxonomy_id else field.options
    return {str(option.value): option.label for option in options}


def _labels(probe: Any, result: dict) -> dict:
    return {key: label for field in _fields(probe, result) for key, label in _options(probe, field).items()}


def _dots(count: int) -> str:
    return '● ' * min(count, 40) + ('…' if count > 40 else '')


def distribution_html(rows: list[tuple[str, int]], answered: int) -> str:
    return '<div class="landscape-distribution">' + ''.join(
        f'<div class="landscape-row"><span>{escape(str(label))}</span>'
        f'<span class="landscape-count"><span aria-hidden="true">{_dots(count)}</span>'
        f'<b>{count} / {answered}</b></span></div>' for label, count in rows) + '</div>'


PORTRAIT_CSS = """
<style>
.portrait-pair {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2.5rem;}
.portrait-panel {min-width:0;color:#12211b;}
.portrait-panel h3 {margin:0 0 .5rem;font-size:1.25rem;}
.portrait-summary,.portrait-helper {margin:.4rem 0;}
.portrait-helper,.portrait-unanswered,.portrait-zero {color:#536158;}
.portrait-options {list-style:none;padding:0;margin:1.5rem 0;}
.portrait-option {padding:.75rem 0;border-bottom:1px solid #12211b26;}
.portrait-option-label {display:block;overflow-wrap:anywhere;}
.portrait-measure {display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1rem;align-items:center;margin-top:.4rem;}
.portrait-track {height:6px;background:#12211b12;min-width:0;}
.portrait-fill {height:100%;background:currentColor;}
.portrait-count {font-variant-numeric:tabular-nums;white-space:nowrap;}
.portrait-zero .portrait-track {background:transparent;}
.portrait-panel p {overflow-wrap:anywhere;}
@media(max-width:700px) {.portrait-pair {grid-template-columns:minmax(0,1fr);gap:2rem;}}
</style>
"""


def portrait_distribution_html(probe: Any, result: dict, title: str) -> str:
    """Aggregate multi-select panel, ordered exclusively by authored options."""
    denominator = result['denominator']
    answered = denominator['answered']
    people_label = 'personne' if answered == 1 else 'personnes'
    selection_label = 'sélection' if denominator['selected'] == 1 else 'sélections'
    labels = _labels(probe, result)
    values = result['data'].get('values', {})
    body = (f'<section class="portrait-panel" aria-label="{escape(title, quote=True)}">'
            f'<h3>{escape(title)}</h3>'
            f'<p class="portrait-summary">{answered} {people_label} · {denominator["selected"]} {selection_label}</p>'
            '<p class="portrait-helper">Plusieurs choix étaient possibles.</p>')
    if denominator.get('unanswered', 0):
        body += (f'<p class="portrait-unanswered">{denominator["unanswered"]} '
                 'trajectoire(s) sans réponse exploitable</p>')
    if not answered:
        return (body + '<p role="status">Aucune donnée collective disponible</p>'
                f'<p>{denominator["resolved"]} / {denominator["eligible"]} réponses résolues</p></section>')
    body += '<ul class="portrait-options">'
    for key, label in labels.items():
        count = values.get(key, {}).get('count', 0)
        width = min(100, max(0, 100 * count / answered))
        body += (f'<li class="portrait-option{(" portrait-zero" if count == 0 else "")}">'
                 f'<span class="portrait-option-label">{escape(label)}</span>'
                 '<div class="portrait-measure">'
                 f'<div class="portrait-track" aria-hidden="true"><div class="portrait-fill" style="width:{width:g}%"></div></div>'
                 f'<span class="portrait-count">{count} / {answered}</span></div></li>')
    body += '</ul>'
    # Unknown keys may contain free text. Disclose their presence, never their content.
    unknown = sum(value.get('count', 0) for key, value in values.items() if key not in labels)
    if unknown:
        body += f'<p>{unknown} sélection(s) hors des options du référentiel actuel.</p>'
    return body + '</section>'


def render_distribution(probe: Any, result: dict, *, presentation: str = 'default',
                        title: str = '', emit: bool = True) -> str | None:
    if presentation == 'portrait':
        html = portrait_distribution_html(probe, result, title)
        if emit:
            st.html(PORTRAIT_CSS + html)
        return html
    d, data = result['denominator'], result['data']
    render_denominator(d)
    if not d['answered']:
        st.info('Aucune donnée collective disponible')
        st.caption(f"{d['resolved']} / {d['eligible']} réponses résolues")
        return
    labels = _labels(probe, result)
    values = data.get('values', {})
    ordered = list(dict.fromkeys([*labels, *values]))
    grouped = set()
    fields = _fields(probe, result)
    group_labels = {g.id: g.label for f in fields if f.taxonomy_id
                    for g in probe.taxonomy(f.taxonomy_id).groups}
    for group_id, group in data.get('groups', {}).items():
        st.markdown(f"**{group_labels.get(group_id, group_id)}**")
        st.caption(f"{group['count']} sélections")
        keys = group['option_ids']
        grouped.update(keys)
        st.html(distribution_html([(labels.get(k, k), values.get(k, {}).get('count', 0)) for k in keys], d['answered']))
    keys = [key for key in ordered if key not in grouped]
    st.html(distribution_html([(labels.get(k, k), values.get(k, {}).get('count', 0)) for k in keys], d['answered']))
    if not values:
        st.caption('Aucune option sélectionnée parmi les réponses observées.')


def render_comparison(probe: Any, result: dict) -> None:
    roles = result['data'].get('roles', {})
    denominators = result['data'].get('denominators', {})
    labels = _labels(probe, result)
    for role in roles:
        render_denominator(denominators[role], label=ROLE_LABELS.get(role, role))
    keys = list(dict.fromkeys([*labels, *(key for values in roles.values() for key in values)]))
    html = '<div class="landscape-exchange' + (' bilateral' if len(roles) == 2 else '') + '">'
    for key in keys:
        html += f'<div class="landscape-topic"><strong>{escape(labels.get(key, key))}</strong><div class="landscape-sides">'
        for role, values in roles.items():
            count = values.get(key, 0)
            observed = denominators[role]['answered']
            value = f'{count} / {observed}' if observed else 'Aucune observation'
            html += (f'<div><small>{escape(ROLE_LABELS.get(role, role))}</small><br>'
                     f'<span aria-hidden="true">{_dots(count) if observed else ""}</span> <b>{value}</b></div>')
        html += '</div></div>'
    st.html(html + '</div>')
    fields = _fields(probe, result)
    taxonomy_ids = {f.taxonomy_id for f in fields}
    derived = derive_exchange_balance(result, same_taxonomy=len(taxonomy_ids) == 1 and '' not in taxonomy_ids)
    if isinstance(derived['data'], list):
        st.markdown('**STRUCTURES QUI APPARAISSENT**')
        st.caption('Structures dérivées des sélections observées · aucune attribution individuelle.')
        names = {'match': 'Correspondance', 'relative_surplus': 'Offre > besoin',
                 'relative_gap': 'Besoin > offre', 'unmet_need': 'Besoin sans offre observée',
                 'unrequested_capacity': 'Capacité sans demande observée'}
        for row in derived['data']:
            st.text(f"{labels.get(row['taxonomy_value'], row['taxonomy_value'])} · "
                    f"{row['offer_count']} ↔ {row['need_count']} · "
                    + ' · '.join(names[state] for state in row['states']))
        with st.expander('ⓘ Données · structures d’échange'):
            st.json(derived)


def _record_labels(probe: Any, result: dict) -> tuple[dict, dict]:
    fields = _fields(probe, result)
    nested = fields[0].item_fields if fields else ()
    return ({f.id: f.prompt for f in nested},
            {f.id: _options(probe, f) for f in nested})


def render_records(probe: Any, result: dict, *, context: dict) -> None:
    render_denominator(result['denominator'])
    rows = record_rows(result)
    if not rows:
        st.info('Aucune proposition collective disponible')
        return
    relation = context.get('record_relations', {}).get(result['representation_id'])
    allow_text = context.get('public_records') == 'verbatim' or context.get('synthetic', False)
    field_labels, options = _record_labels(probe, result)
    st.caption(f'{len(rows)} propositions · les propositions ne sont pas un nombre de personnes')
    if allow_text:
        for index, row in enumerate(rows):
            with st.container(border=True):
                st.markdown(f'**Proposition {index + 1}**')
                for key, value in row.items():
                    if key in {'id', 'participant_id', 'participation_id'}:
                        continue
                    st.caption(field_labels.get(key, key))
                    if isinstance(value, list):
                        st.text(' · '.join(options.get(key, {}).get(str(v), str(v)) for v in value))
                    else:
                        st.text(str(value) if value is not None else 'Non renseigné')
                for key in field_labels:
                    if key not in row or row[key] in (None, '', []):
                        st.caption(f'{field_labels[key]} · Non renseigné')
    else:
        st.caption('Vue publique agrégée : les textes libres restent réservés à une diffusion autorisée.')
    if not relation:
        if not allow_text:
            st.text(f'{len(rows)} enregistrements · contenu réservé')
        st.caption('Aucune relation entre champs n’est définie pour cette représentation.')
        return
    graph = derive_action_actor_graph(result, **relation)
    actor_labels = options.get(relation['actor_field'], {})
    # Public aggregates preserve explicit actor sets without disclosing free-text categories.
    combinations = Counter(tuple(sorted({edge['actor'] for edge in graph['data']['edges']
                                         if edge['action'] == action['id']}))
                           for action in graph['data']['actions'])
    if not allow_text:
        for actors, count in combinations.items():
            st.text(f"{count} proposition(s) ↔ " + (' · '.join(actor_labels.get(a, a) for a in actors) or 'Acteur·ices non renseignés'))
    st.markdown('**Actions ↔ acteur·ices**')
    st.caption('Chaque lien correspond à une association explicite dans une proposition.')
    components.html(topology_html(graph, actor_labels, rows, reveal_text=allow_text,
                                  record_labels=field_labels, record_options=options), height=650, scrolling=True)
    actors = list(graph['data']['actors'])
    choice = st.selectbox('Explorer un acteur', ['Tout', *actors],
                          format_func=lambda value: actor_labels.get(value, value),
                          key=f"actor-{result['representation_id']}")
    # Native, keyboard/touch-accessible adjacency view; preserves semantics on narrow screens.
    for actor in actors:
        if choice != 'Tout' and actor != choice:
            continue
        associated = [edge['action'] for edge in graph['data']['edges'] if edge['actor'] == actor]
        with st.expander(f"{actor_labels.get(actor, actor)} · {len(associated)} proposition(s)", expanded=choice == actor):
            if allow_text:
                for action in graph['data']['actions']:
                    if action['id'] in associated:
                        row = rows[action['record_index']]
                        st.text(f"Proposition {action['record_index']+1}")
                        for key, value in row.items():
                            if key not in {'id', 'participant_id', 'participation_id'}:
                                st.text(f'{field_labels.get(key, key)} : {value}')
            else:
                st.text(f'{len(associated)} associations explicites · textes réservés')
            st.caption('Source : ' + ', '.join(result['provenance'].get('field_revisions', {})))
    with st.expander('ⓘ Données · topologie'):
        # Never leak free text through the derived graph disclosure.
        safe = {**graph, 'data': {**graph['data'], 'actions': [
            {k: v for k, v in a.items() if k != 'category'} for a in graph['data']['actions']]}}
        st.json(safe)


def render_representation(probe: Any, result: dict, *, context: dict) -> None:
    kind = result['representation_type']
    if kind == 'composite':
        children = result['data'].get('components', [])
        position = 0
        while position < len(children):
            pair = children[position:position + 2]
            identifiers = [child['representation_id'] for child in pair]
            paired = (len(pair) == 2 and identifiers in context.get('distribution_pairs', [])
                      and all(child['representation_type'] in {'distribution', 'grouped_distribution'}
                              for child in pair))
            if paired:
                panels = []
                for child in pair:
                    fields = _fields(probe, child)
                    title = context.get('component_titles', {}).get(
                        child['representation_id'], ' · '.join(field.prompt for field in fields))
                    panels.append(render_distribution(probe, child, presentation='portrait', title=title, emit=False))
                st.html(PORTRAIT_CSS + '<div class="portrait-pair">' + ''.join(panels) + '</div>')
                for child in pair:
                    with st.expander(f"ⓘ Données · {child['representation_id']}"):
                        st.json(provenance(child))
                position += 2
            else:
                render_representation(probe, children[position], context=context)
                position += 1
    else:
        fields = _fields(probe, result)
        st.markdown('### ' + context.get('component_titles', {}).get(
            result['representation_id'], ' · '.join(f.prompt for f in fields) or result['representation_id']))
        if kind in {'distribution', 'grouped_distribution'}:
            render_distribution(probe, result)
        elif kind == 'comparison':
            render_comparison(probe, result)
        elif kind == 'records':
            render_records(probe, result, context=context)
        else:
            st.warning(f'Type de représentation non pris en charge : {kind}')
    with st.expander(f"ⓘ Données · {result['representation_id']}"):
        st.json(provenance(result))


def render_results_landscape(probe_definition: Any, representation_results: list[dict], *,
                             view_context: dict, theme: Any = None) -> None:
    probe, context = probe_definition, view_context
    colours = theme or PROBE_COLORS
    st.html('<style>' + typography_css() + f'''
    .landscape-row {{display:flex;justify-content:space-between;gap:1.5rem;padding:12px 0;border-bottom:1px solid #aaa6;}}
    .landscape-count {{flex-shrink:0;white-space:nowrap;color:{colours['ink']};font-variant-numeric:tabular-nums;}}
    .landscape-topic {{padding:18px 0;border-bottom:1px solid #aaa6;overflow-wrap:anywhere;}}
    .landscape-sides {{display:grid;grid-template-columns:1fr 1fr;gap:2rem;margin-top:12px;}}
    .bilateral .landscape-topic {{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:24px;align-items:center;}}
    .bilateral .landscape-topic>strong {{grid-column:2;grid-row:1;text-align:center;}}
    .bilateral .landscape-sides {{display:contents;}}
    .bilateral .landscape-sides>div:first-child {{grid-column:1;grid-row:1;text-align:right;}}
    .bilateral .landscape-sides>div:nth-child(2) {{grid-column:3;grid-row:1;}}
    @media(max-width:600px) {{.landscape-row {{flex-direction:column;gap:4px;}}
    .landscape-sides {{grid-template-columns:1fr;gap:12px;}}
    .bilateral .landscape-topic {{display:flex;flex-direction:column;align-items:stretch;gap:12px;}}
    .bilateral .landscape-topic>strong,.bilateral .landscape-sides>div:first-child {{text-align:left;}}}}
    </style>''')
    if context.get('show_title', True):
        st.title('Notre paysage commun')
    st.write('Les réponses individuelles font apparaître un paysage collectif : qui est présent, '
             'ce que nous pouvons partager, ce que nous recherchons, ce que nous souhaitons faire émerger '
             'et les chemins par lesquels nous pourrions agir.')
    cohort = context.get('cohort', 0)
    evaluated = representation_results[0]['provenance'].get('evaluated_at', '') if representation_results else ''
    st.caption(f"{cohort} PARTICIPANT·ES · {len(representation_results)} REPRÉSENTATIONS · {evaluated[:10]}")
    st.caption('Tout le collectif')
    with st.expander('Voir les données / provenance'):
        for result in representation_results:
            st.json(provenance(result))
    index = {}
    def register(result):
        index[result['representation_id']] = result
        for child in result['data'].get('components', []):
            register(child)
    for result in representation_results:
        register(result)
    rendered = set()
    sections = context.get('sections') or [
        {'title': definition.title or definition.id, 'representations': [definition.id]}
        for definition in probe.representations]
    for section in sections:
        st.divider()
        st.header(section['title'])
        if section.get('subtitle'):
            st.write(section['subtitle'])
        for identifier in section['representations']:
            result = index.get(identifier)
            if result is None:
                st.info(f'Représentation indisponible : {identifier}')
                continue
            if identifier not in rendered:
                render_representation(probe, result, context=context)
                rendered.add(identifier)
                rendered.update(leaf['representation_id'] for leaf in leaves(result))
    # Layout preferences can never hide additional authored results.
    for result in representation_results:
        for leaf in leaves(result):
            if leaf['representation_id'] not in rendered:
                render_representation(probe, leaf, context=context)
                rendered.add(leaf['representation_id'])
    actionability = context.get('actionability')
    if actionability:
        actions = index[actionability['actions']]
        contributions = index[actionability['contributions']]
        derived = derive_actionability(actions, contributions, actionability['mapping'],
                                       category_field=actionability['category_field'])
        st.markdown('**CHEMINS ET CAPACITÉS**')
        for row in derived['data']:
            st.text(f"{row['category']} · {row['proposed_records']} propositions · "
                    f"{row['available_selections']} sélections de contribution disponibles")
        st.caption('Plusieurs sélections peuvent appartenir à une même personne.')
        with st.expander('ⓘ Données · chemins et capacités'):
            st.json(derived)
    st.divider()
    st.markdown('**À PROPOS DE CE PAYSAGE**')
    st.caption(f"{cohort} participations · {len(representation_results)} représentations collectives · Données évaluées le {evaluated[:10]}")
    st.caption(f"{context.get('trajectories', cohort)} trajectoires actuelles · {context.get('excluded', 0)} soumissions exclues dans ce périmètre")
    st.caption(f"Audit du dépôt : {context.get('excluded_physical_rows', 0)} lignes physiques exclues au total (autres périmètres compris).")
    unresolved_projections = sum(
        leaf['denominator']['eligible'] > 0 and leaf['denominator']['resolved'] == 0
        for result in representation_results for leaf in leaves(result)
    )
    st.caption(f'{unresolved_projections} projections sans réponse résolue')
    for result in representation_results:
        record_fields = {
            leaf['representation_id']: tuple(nested.id for field in _fields(probe, leaf)
                                              for nested in field.item_fields)
            for leaf in leaves(result) if leaf['representation_type'] == 'records'
        }
        integrity = derive_completeness(result, record_fields=record_fields)
        for component in integrity['data']:
            if component['unresolved']:
                st.caption(f"{component['representation_id']} · {component['unresolved']} sans réponse")
            for key, count in component['missing_record_fields'].items():
                if count:
                    st.caption(f"{component['representation_id']} · {count} enregistrements sans {key}")
        with st.expander(f"Intégrité · {result['representation_id']}"):
            st.json(integrity)
