"""Accessible standalone topology view over an already-derived explicit graph."""
from html import escape
import json


def topology_html(graph: dict, actor_labels: dict, rows: list[dict], *, reveal_text: bool, record_labels: dict | None = None,
                  record_options: dict | None = None) -> str:
    record_labels, record_options = record_labels or {}, record_options or {}
    data = graph['data']
    actions = data['actions']
    actors = list(data['actors'])
    height = max(len(actions), len(actors), 1) * 54 + 70
    nodes, links, details = [], [], {}
    actor_ids = {actor: f'actor-{index}' for index, actor in enumerate(actors)}
    for index, action in enumerate(actions):
        key = action['id']
        label = f'Proposition {index+1}'
        nodes.append((key, label, 210, 50 + index * 54))
        associated = [actor_labels.get(e['actor'], e['actor']) for e in data['edges'] if e['action'] == key]
        record = {k: v for k, v in rows[index].items() if k not in {'id', 'participant_id', 'participation_id'}} if reveal_text else {}
        record = {record_labels.get(k, k): (
            ' · '.join(record_options.get(k, {}).get(str(item), str(item)) for item in value)
            if isinstance(value, list) else value) for k, value in record.items()}
        details[key] = {'label': label, 'record': record, 'actors': associated,
                        'source': list(graph['provenance'].get('field_revisions', {}))}
    for index, actor in enumerate(actors):
        key = actor_ids[actor]
        label = actor_labels.get(actor, actor)
        nodes.append((key, label, 610, 50 + index * 54))
        details[key] = {'label': label, 'record': {},
                        'actors': [f"Proposition {int(e['action'].split('-')[1])}" for e in data['edges'] if e['actor'] == actor],
                        'source': list(graph['provenance'].get('field_revisions', {}))}
    positions = {key: (x, y) for key, _, x, y in nodes}
    for edge in data['edges']:
        a, b = edge['action'], actor_ids[edge['actor']]
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        links.append(f'<line data-a="{a}" data-b="{b}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
    svg_nodes = []
    mobile = []
    for key, label, x, y in nodes:
        short = label if len(label) < 31 else label[:28] + '…'
        tx, anchor = (x - 15, 'end') if key.startswith('action') else (x + 15, 'start')
        svg_nodes.append(f'<g data-node="{key}" role="button" tabindex="0" aria-label="{escape(label, quote=True)}">'
                         f'<title>{escape(label)}</title><circle cx="{x}" cy="{y}" r="7"/>'
                         f'<text x="{tx}" y="{y+5}" text-anchor="{anchor}">{escape(short)}</text></g>')
        mobile.append(f'<button data-node="{key}">{escape(label)}</button>')
    payload = json.dumps(details, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return f'''<!doctype html><html lang="fr"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font:16px system-ui;color:#12211b;margin:0}}svg{{width:100%;height:auto}}line{{stroke:#9baba3;stroke-width:1}}circle{{fill:#12211b}}text{{font-size:13px;fill:currentColor}}g[role=button]{{cursor:pointer}}g:focus{{outline:2px solid #12211b}}.dim{{opacity:.55}}.active{{stroke-width:3}}button{{font:inherit;padding:12px;background:transparent;border:1px solid #aaa6;text-align:left;cursor:pointer}}#mobile{{display:none}}#detail{{position:sticky;top:0;z-index:2;background:#f3f0e8;border-bottom:1px solid #aaa;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto}}@media(max-width:600px){{svg{{display:none}}#mobile{{display:grid;gap:8px;grid-template-columns:1fr}}}}
</style><div id="detail" aria-live="polite">Sélectionnez une proposition ou un acteur pour explorer ses associations explicites.</div><svg viewBox="0 0 880 {height}" aria-label="Propositions et acteur·ices explicitement associés">{''.join(links)}{''.join(svg_nodes)}</svg>
<div id="mobile">{''.join(mobile)}</div>
<script>
const detail={payload};
function highlight(key){{
const linked=new Set([key]);document.querySelectorAll('line').forEach(e=>{{const on=e.dataset.a===key||e.dataset.b===key;if(on){{linked.add(e.dataset.a);linked.add(e.dataset.b)}}e.classList.toggle('dim',!on);e.classList.toggle('active',on)}});
document.querySelectorAll('[data-node]').forEach(e=>e.classList.toggle('dim',!linked.has(e.dataset.node)));}}
function show(key){{highlight(key);const d=detail[key];const box=document.getElementById('detail');box.replaceChildren();const h=document.createElement('strong');h.textContent=d.label;box.append(h);const p=document.createElement('p');p.textContent=d.actors.join(' · ')||'Aucun acteur associé';box.append(p);Object.entries(d.record).forEach(([k,v])=>{{const p=document.createElement('p');p.textContent=k+' : '+(typeof v==='string'?v:JSON.stringify(v));box.append(p)}});const s=document.createElement('small');s.textContent='Source : '+d.source.join(', ');box.append(s);}}
document.querySelectorAll('[data-node]').forEach(e=>{{e.addEventListener('mouseenter',()=>highlight(e.dataset.node));e.addEventListener('focus',()=>highlight(e.dataset.node));e.addEventListener('click',()=>show(e.dataset.node));e.addEventListener('keydown',ev=>{{if(ev.key==='Enter'||ev.key===' '){{ev.preventDefault();show(e.dataset.node)}}}})}});
</script></html>'''
