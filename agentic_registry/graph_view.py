"""Interactive renderer for the compiled actor–protocol multiplex graph.

This module is deliberately a presentation boundary.  It accepts the graph
artifact emitted by :mod:`agentic_registry.compiler`; it never opens or
interprets the registry YAML.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import json
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from .compiler import ARTIFACT_CONTRACT_VERSION


SHARED_PROTOCOL_FILTER_KEY = "agentic_map_protocols"
_CYTOSCAPE_BUNDLE = (
    Path(__file__).with_name("vendor") / "cytoscape-3.34.0.min.js"
)


class GraphArtifactError(ValueError):
    """Raised when a renderer receives something other than the graph contract."""


def _validated_protocol_ids(
    graph: Mapping[str, Any], protocol_ids: Iterable[str] | None
) -> list[str]:
    admitted = {
        str(node["id"])
        for node in graph["nodes"]
        if node.get("kind") == "protocol"
    }
    if protocol_ids is None:
        return []
    return sorted({str(item) for item in protocol_ids if str(item) in admitted})


def _validate_graph_contract(graph: Mapping[str, Any]) -> None:
    if graph.get("contract_version") != ARTIFACT_CONTRACT_VERSION:
        raise GraphArtifactError("graph artifact contract version is not supported")
    for key in ("nodes", "edges", "genealogy_edges", "layers", "metadata"):
        if key not in graph:
            raise GraphArtifactError(f"graph artifact is missing {key}")
    for node in graph["nodes"]:
        position = node.get("position")
        if not isinstance(position, Mapping) or not {"x", "y"} <= position.keys():
            raise GraphArtifactError(
                f"compiled node {node.get('id', '<unknown>')} has no fixed position"
            )


def _script_safe_json(value: Any) -> str:
    """Encode data for a script element without allowing an early close tag."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def build_multiplex_graph_html(
    graph: Mapping[str, Any],
    *,
    protocol_ids: Iterable[str] | None = None,
    selected_date: str | None = None,
    selected_transition: Mapping[str, Any] | None = None,
) -> str:
    """Build a self-contained graph instrument from a compiled graph artifact."""

    _validate_graph_contract(graph)
    transition = selected_transition or {}
    transition_actor_ids = sorted(
        {
            str(participant.get("actor_id"))
            for side in ("before", "after")
            for regime in transition.get(side) or []
            for participant in regime.get("participants") or []
            if participant.get("actor_id")
        }
    )
    renderer_config = {
        "shared_protocol_ids": _validated_protocol_ids(graph, protocol_ids),
        "selected_date": selected_date,
        "selected_transition_id": str(transition.get("id") or ""),
        "transition_actor_ids": transition_actor_ids,
        "transition_protocol_ids": sorted(
            str(value) for value in transition.get("affected_protocol_ids") or []
        ),
    }
    bundle = _CYTOSCAPE_BUNDLE.read_text(encoding="utf-8")
    return (
        _HTML_TEMPLATE.replace("__CYTOSCAPE_BUNDLE__", bundle)
        .replace("__GRAPH_DATA__", _script_safe_json(graph))
        .replace("__RENDERER_CONFIG__", _script_safe_json(renderer_config))
    )


def render_multiplex_graph(
    graph: Mapping[str, Any],
    *,
    protocol_ids: Iterable[str] | None = None,
    selected_date: str | None = None,
    selected_transition: Mapping[str, Any] | None = None,
) -> None:
    """Render the multiplex graph, coordinated with the page protocol filter.

    Callers may pass ``protocol_ids`` explicitly.  Otherwise the renderer uses
    ``st.session_state['agentic_map_protocols']`` when that page-level selection
    exists.  Graph-local controls never mutate the shared selection.
    """

    selected = protocol_ids
    if selected is None:
        selected = st.session_state.get(SHARED_PROTOCOL_FILTER_KEY)
    components.html(
        build_multiplex_graph_html(
            graph,
            protocol_ids=selected,
            selected_date=selected_date,
            selected_transition=selected_transition,
        ),
        height=940,
        scrolling=True,
    )


_HTML_TEMPLATE = r"""
<style>
  .apg-shell {
    --ink: #18221e;
    --muted: #64716b;
    --paper: #fbfaf5;
    --panel: #ffffff;
    --line: #d9ddd7;
    --accent: #315c46;
    color: var(--ink);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    border: 1px solid var(--line);
    border-radius: 18px;
    overflow: hidden;
    background: var(--paper);
  }
  .apg-controls {
    display: grid;
    grid-template-columns: minmax(180px, 1.35fr) repeat(4, minmax(130px, 1fr));
    gap: 10px;
    padding: 14px;
    border-bottom: 1px solid var(--line);
    background: rgba(255, 255, 255, .78);
  }
  .apg-field { display: grid; gap: 5px; min-width: 0; }
  .apg-field label, .apg-toggle {
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .07em;
    text-transform: uppercase;
  }
  .apg-field select, .apg-field input {
    width: 100%; min-width: 0; box-sizing: border-box;
    padding: 8px 9px; border: 1px solid var(--line); border-radius: 8px;
    color: var(--ink); background: #fff; font: inherit; font-size: 13px;
  }
  .apg-toggle-row {
    grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center;
    justify-content: space-between; gap: 12px; padding-top: 2px;
  }
  .apg-toggle { display: inline-flex; align-items: center; gap: 7px; text-transform: none; letter-spacing: 0; }
  .apg-toggle input { accent-color: var(--accent); }
  .apg-count { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
  .apg-workspace { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(280px, .75fr); min-height: 700px; }
  .apg-graph-wrap { position: relative; min-width: 0; background: radial-gradient(circle at 50% 50%, #fff 0, var(--paper) 66%); }
  .apg-graph { position: absolute; inset: 0; }
  .apg-axis-label {
    position: absolute; top: 12px; z-index: 2; color: var(--muted); font-size: 10px;
    font-weight: 750; letter-spacing: .1em; text-transform: uppercase; pointer-events: none;
  }
  .apg-axis-label.company { left: 18px; }
  .apg-axis-label.protocol { left: 50%; transform: translateX(-50%); }
  .apg-axis-label.institution { right: 18px; }
  .apg-detail { border-left: 1px solid var(--line); padding: 18px; overflow: auto; max-height: 700px; background: var(--panel); }
  .apg-detail h3 { margin: 0 0 6px; font-size: 18px; line-height: 1.25; }
  .apg-detail h4 { margin: 20px 0 8px; font-size: 12px; letter-spacing: .06em; text-transform: uppercase; }
  .apg-detail p { margin: 4px 0 10px; color: var(--muted); font-size: 13px; line-height: 1.5; }
  .apg-kicker { color: var(--accent); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  .apg-pills { display: flex; flex-wrap: wrap; gap: 5px; margin: 8px 0 12px; }
  .apg-pill { padding: 3px 7px; border-radius: 999px; background: #eef2ed; color: #415048; font-size: 11px; }
  .apg-card { margin: 8px 0; padding: 10px; border: 1px solid var(--line); border-radius: 10px; background: #fcfcf9; }
  .apg-card strong { display: block; font-size: 12px; line-height: 1.35; }
  .apg-card span { display: block; margin-top: 4px; color: var(--muted); font-size: 11px; line-height: 1.4; }
  .apg-card a { display: inline-block; margin-top: 6px; color: var(--accent); font-size: 11px; font-weight: 700; text-decoration: none; }
  .apg-empty { display: grid; place-items: center; min-height: 420px; color: var(--muted); text-align: center; line-height: 1.55; }
  .apg-governance { display: grid; gap: 7px; }
  .apg-governance-row { padding: 8px 0; border-top: 1px solid #eceeea; }
  .apg-governance-row b { display: block; margin-bottom: 3px; color: var(--muted); font-size: 10px; letter-spacing: .05em; text-transform: uppercase; }
  .apg-governance-row span { font-size: 12px; line-height: 1.45; }
  @media (max-width: 900px) {
    .apg-controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .apg-toggle-row { grid-column: 1 / -1; }
    .apg-workspace { grid-template-columns: 1fr; }
    .apg-graph-wrap { min-height: 620px; }
    .apg-detail { border-left: 0; border-top: 1px solid var(--line); max-height: none; }
  }
</style>
<div class="apg-shell" id="agentic-multiplex-graph">
  <div class="apg-controls">
    <div class="apg-field"><label for="apg-layer">Multiplex layer</label><select id="apg-layer"></select></div>
    <div class="apg-field"><label for="apg-protocol">Protocol</label><select id="apg-protocol"></select></div>
    <div class="apg-field"><label for="apg-actor">Actor type</label><select id="apg-actor"></select></div>
    <div class="apg-field"><label for="apg-date">Network on</label><input id="apg-date" type="date"></div>
    <div class="apg-field"><label for="apg-confidence">Minimum confidence</label><select id="apg-confidence"><option value="high">High</option><option value="medium" selected>Medium</option><option value="low">Low</option></select></div>
    <div class="apg-toggle-row">
      <label class="apg-toggle"><input id="apg-genealogy" type="checkbox"> Show protocol genealogy</label>
      <span class="apg-count" id="apg-count" aria-live="polite"></span>
    </div>
  </div>
  <div class="apg-workspace">
    <div class="apg-graph-wrap">
      <span class="apg-axis-label company">Companies</span>
      <span class="apg-axis-label protocol">Protocols</span>
      <span class="apg-axis-label institution">Institutions &amp; projects</span>
      <div class="apg-graph" id="apg-canvas" aria-label="Actor-protocol multiplex graph"></div>
    </div>
    <aside class="apg-detail" id="apg-detail" aria-live="polite"></aside>
  </div>
</div>
<script type="application/json" id="apg-data">__GRAPH_DATA__</script>
<script type="application/json" id="apg-config">__RENDERER_CONFIG__</script>
<script>
document.getElementById("agentic-multiplex-graph").dataset.apgRuntime = "started";
var module = undefined, exports = undefined, define = undefined;
__CYTOSCAPE_BUNDLE__
const cytoscapeFactory = globalThis.cytoscape;
document.getElementById("agentic-multiplex-graph").dataset.apgRuntime =
  typeof cytoscapeFactory;
(() => {
  const root = document.getElementById("agentic-multiplex-graph");
  const graph = JSON.parse(document.getElementById("apg-data").textContent);
  const config = JSON.parse(document.getElementById("apg-config").textContent);
  root.dataset.apgTransition = config.selected_transition_id || "";
  const nodesById = new Map(graph.nodes.map(node => [node.id, node]));
  const edgesById = new Map([
    ...graph.edges.map(edge => [edge.id, {...edge, genealogy: false}]),
    ...graph.genealogy_edges.map(edge => [edge.id, {...edge, layer: "genealogy", genealogy: true}]),
  ]);
  const sharedProtocols = new Set(config.shared_protocol_ids || []);
  const controls = {
    layer: root.querySelector("#apg-layer"), protocol: root.querySelector("#apg-protocol"),
    actor: root.querySelector("#apg-actor"), date: root.querySelector("#apg-date"),
    confidence: root.querySelector("#apg-confidence"), genealogy: root.querySelector("#apg-genealogy"),
    count: root.querySelector("#apg-count"), detail: root.querySelector("#apg-detail"),
  };

  function option(select, value, label, selected = false) {
    const item = document.createElement("option"); item.value = value; item.textContent = label; item.selected = selected; select.append(item);
  }
  option(controls.layer, "operational", "Operational / institutional", true);
  graph.layers.forEach(layer => option(controls.layer, layer.id, layer.label));
  option(controls.layer, "all", "All recorded relations");
  option(controls.protocol, "all", "All protocols", sharedProtocols.size === 0);
  if (sharedProtocols.size) option(controls.protocol, "shared", `Page selection (${sharedProtocols.size})`, true);
  graph.nodes.filter(n => n.kind === "protocol").sort((a,b) => a.label.localeCompare(b.label)).forEach(node => option(controls.protocol, node.id, `${node.label} · ${node.name}`));
  option(controls.actor, "all", "All actor types", true);
  [...new Set(graph.nodes.filter(n => n.kind === "actor").map(n => n.actor_type))].sort().forEach(type => option(controls.actor, type, type.replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase())));
  controls.date.value = config.selected_date || graph.metadata.observed_at || new Date().toISOString().slice(0, 10);

  const layerColours = {
    authorship: "#7c3aed", governance: "#b45309", maintenance: "#0f766e", implementation: "#0369a1",
    adoption: "#15803d", funding: "#be123c", endorsement: "#6b7280", convening: "#9333ea", genealogy: "#334155",
  };
  const cy = cytoscapeFactory({
    container: root.querySelector("#apg-canvas"),
    elements: graph.nodes.map(node => ({ data: { id: node.id, label: node.label, kind: node.kind, actorType: node.actor_type || "", column: node.column }, position: node.position, locked: true })),
    layout: { name: "preset", fit: true, padding: 54 },
    minZoom: .28, maxZoom: 2.2, boxSelectionEnabled: false,
    style: [
      { selector: "node", style: { "label": "data(label)", "font-size": 12, "font-weight": 600, "text-wrap": "wrap", "text-max-width": 115, "text-valign": "center", "text-halign": "center", "border-width": 1.5, "border-color": "#53615a", "background-color": "#f9faf7", "color": "#17221d", "width": 42, "height": 42 } },
      { selector: "node[kind = 'protocol']", style: { "shape": "round-rectangle", "width": 78, "height": 48, "background-color": "#263f33", "border-color": "#182b22", "color": "#ffffff", "font-size": 13 } },
      { selector: "node[actorType = 'company']", style: { "shape": "ellipse", "background-color": "#fff8e7" } },
      { selector: "node[actorType = 'foundation'], node[actorType = 'standards_body']", style: { "shape": "diamond", "background-color": "#edf5f1" } },
      { selector: "node[actorType = 'open_source_project']", style: { "shape": "round-hexagon", "background-color": "#eef2ff" } },
      { selector: "edge", style: { "width": 2, "curve-style": "bezier", "line-color": "data(colour)", "target-arrow-color": "data(colour)", "target-arrow-shape": "triangle", "arrow-scale": .75, "opacity": .72 } },
      { selector: "edge[genealogy]", style: { "line-style": "dashed", "width": 2.4, "opacity": .82 } },
      { selector: ":selected", style: { "border-width": 4, "border-color": "#c96f2d", "line-color": "#c96f2d", "target-arrow-color": "#c96f2d", "opacity": 1 } },
      { selector: ".transition-focus", style: { "border-width": 4, "border-color": "#c96f2d", "background-color": "#fff1df", "opacity": 1 } },
      { selector: ".faded", style: { "opacity": .13 } },
    ],
  });
  root.dataset.apgRuntime = "ready";
  cy.nodes().ungrabify();
  const transitionFocus = new Set([
    ...(config.transition_actor_ids || []),
    ...(config.transition_protocol_ids || []),
  ]);
  cy.nodes().forEach(node => {
    if (transitionFocus.has(node.id())) node.addClass("transition-focus");
  });

  const confidenceRank = { low: 1, medium: 2, high: 3 };
  function activeAt(edge, day) {
    const start = edge.valid_from?.start;
    const end = edge.valid_to?.start;
    return Boolean(start && start <= day && (!end || day < end));
  }
  function protocolAllowed(id) {
    const value = controls.protocol.value;
    if (value === "all") return true;
    if (value === "shared") return sharedProtocols.has(id);
    return id === value;
  }
  function relationAllowed(edge) {
    const selectedLayer = controls.layer.value;
    if (selectedLayer === "operational" && !edge.default_visible) return false;
    if (selectedLayer !== "operational" && selectedLayer !== "all" && edge.layer !== selectedLayer) return false;
    if (!protocolAllowed(edge.target)) return false;
    const actor = nodesById.get(edge.source);
    if (controls.actor.value !== "all" && actor?.actor_type !== controls.actor.value) return false;
    if ((confidenceRank[edge.confidence] || 0) < confidenceRank[controls.confidence.value]) return false;
    return activeAt(edge, controls.date.value);
  }
  function genealogyAllowed(edge) {
    if (!controls.genealogy.checked || !activeAt(edge, controls.date.value)) return false;
    const value = controls.protocol.value;
    if (value === "all") return true;
    if (value === "shared") return sharedProtocols.has(edge.source) || sharedProtocols.has(edge.target);
    return edge.source === value || edge.target === value;
  }
  function edgeElement(edge) {
    return { data: { id: edge.id, source: edge.source, target: edge.target, colour: layerColours[edge.layer] || "#6b7280", genealogy: Boolean(edge.genealogy) } };
  }
  function updateGraph() {
    const activeRelations = graph.edges.filter(relationAllowed);
    const activeGenealogy = graph.genealogy_edges.map(edge => ({...edge, layer: "genealogy", genealogy: true})).filter(genealogyAllowed);
    const active = [...activeRelations, ...activeGenealogy];
    cy.batch(() => {
      cy.edges().remove();
      cy.add(active.map(edgeElement));
      const visible = new Set();
      active.forEach(edge => { visible.add(edge.source); visible.add(edge.target); });
      graph.nodes.filter(node => node.kind === "protocol" && protocolAllowed(node.id)).forEach(node => visible.add(node.id));
      cy.nodes().forEach(node =>
        node.style("display", visible.has(node.id()) ? "element" : "none")
      );
      root.dataset.apgVisibility = `${visible.size}/${cy.nodes().length}`;
    });
    controls.count.textContent = `${activeRelations.length} actor relations · ${activeGenealogy.length} genealogy relations`;
    showPrompt(active.length);
  }

  function clearElement(element) { while (element.firstChild) element.firstChild.remove(); }
  function addText(tag, text, className) { const el = document.createElement(tag); el.textContent = text; if (className) el.className = className; return el; }
  function pill(text) { return addText("span", text, "apg-pill"); }
  function formatDate(item) {
    if (!item?.value) return "open";
    return `${item.value}${item.precision && item.precision !== "day" ? ` (${item.precision} precision)` : ""}`;
  }
  function interval(edge) { return `${formatDate(edge.valid_from)} → ${edge.valid_to?.value ? formatDate(edge.valid_to) : "present"}`; }
  function evidenceCards(cards) {
    const fragment = document.createDocumentFragment();
    (cards || []).forEach(card => {
      const wrapper = document.createElement("div"); wrapper.className = "apg-card";
      wrapper.append(addText("strong", card.title || card.claim || card.id));
      wrapper.append(addText("span", [card.publisher, card.authority, card.published_at ? `published ${card.published_at}` : "publication date unresolved", card.observed_at ? `observed ${card.observed_at}` : ""].filter(Boolean).join(" · ")));
      if (card.url) { const link = addText("a", "Open primary source ↗"); link.href = card.url; link.target = "_blank"; link.rel = "noopener noreferrer"; wrapper.append(link); }
      fragment.append(wrapper);
    });
    return fragment;
  }
  function showPrompt(count) {
    clearElement(controls.detail);
    const box = document.createElement("div"); box.className = "apg-empty";
    box.append(addText("p", count ? "Select a protocol, actor or relation to inspect its evidence and layer-specific neighbourhood." : "No relations satisfy these filters. Try an earlier layer, lower confidence threshold or later date."));
    controls.detail.append(box);
  }
  function compactValue(value) {
    if (value == null || value === "" || (Array.isArray(value) && !value.length)) return "Not established in the certified evidence";
    if (!Array.isArray(value)) return typeof value === "object" ? (value.label || value.name || value.summary || JSON.stringify(value)) : String(value);
    return value.map(item => {
      if (typeof item !== "object") return String(item);
      if (item.actor?.label) return `${item.actor.label}${item.valid_from ? ` (${formatDate(item.valid_from)} → ${item.valid_to?.value ? formatDate(item.valid_to) : "present"})` : ""}`;
      if (item.summary) return `${item.summary}${item.date ? ` (${formatDate(item.date)})` : ""}`;
      return item.label || item.name || item.id || item.relation_id || item.event_id || "Recorded entry";
    }).join("; ");
  }
  function governanceSurface(node) {
    const surface = node.governance_surface; if (!surface) return;
    controls.detail.append(addText("h4", "Governance surface"));
    const list = document.createElement("div"); list.className = "apg-governance";
    const rows = [
      ["Governing body", surface.governing_body], ["Technical steering committee", surface.technical_steering_committee],
      ["Voting organisations", surface.voting_organisations], ["Named representatives", surface.named_representatives],
      ["Appointment interval", surface.appointment_intervals], ["Maintainer interval", surface.maintainer_intervals],
      ["Decision procedure", surface.decision_procedure], ["Transfer of stewardship", surface.transfer_of_stewardship],
    ];
    rows.forEach(([label, value]) => { const row = document.createElement("div"); row.className = "apg-governance-row"; row.append(addText("b", label), addText("span", compactValue(value))); list.append(row); });
    controls.detail.append(list);
    if (surface.gaps?.length) { controls.detail.append(addText("p", `Evidence gaps: ${surface.gaps.map(item => item.replaceAll("_", " ")).join(", ")}.`)); }
    if (surface.governance_evidence?.length) { controls.detail.append(addText("h4", "Governance evidence"), evidenceCards(surface.governance_evidence)); }
  }
  function showEdge(id) {
    const edge = edgesById.get(id); if (!edge) return;
    clearElement(controls.detail);
    controls.detail.append(addText("div", edge.genealogy ? "Protocol genealogy" : edge.layer, "apg-kicker"));
    controls.detail.append(addText("h3", edge.claim));
    const pills = document.createElement("div"); pills.className = "apg-pills";
    [edge.relation_type, interval(edge), edge.evidence_state, edge.confidence].filter(Boolean).forEach(item => pills.append(pill(item.replaceAll("_", " ")))); controls.detail.append(pills);
    if (edge.relation_label) controls.detail.append(addText("p", edge.relation_label));
    controls.detail.append(addText("h4", "Supporting evidence"), evidenceCards(edge.evidence));
  }
  function showNode(id) {
    const node = nodesById.get(id); if (!node) return;
    clearElement(controls.detail);
    controls.detail.append(addText("div", node.kind, "apg-kicker"));
    controls.detail.append(addText("h3", node.kind === "protocol" ? `${node.label} · ${node.name}` : node.label));
    const pills = document.createElement("div"); pills.className = "apg-pills";
    [node.actor_type, node.layer, node.status, node.certification_verdict].filter(Boolean).forEach(item => pills.append(pill(item.replaceAll("_", " ")))); controls.detail.append(pills);
    const activeIds = new Set(cy.edges().map(edge => edge.id()));
    const neighbours = [...edgesById.values()].filter(edge => activeIds.has(edge.id) && (edge.source === id || edge.target === id));
    const groups = new Map(); neighbours.forEach(edge => { const layer = edge.layer || "other"; if (!groups.has(layer)) groups.set(layer, []); groups.get(layer).push(edge); });
    controls.detail.append(addText("h4", "Neighbourhood by active layer"));
    if (!groups.size) controls.detail.append(addText("p", "No neighbouring relations satisfy the active filters."));
    [...groups].sort(([a],[b]) => a.localeCompare(b)).forEach(([layer, relations]) => {
      const card = document.createElement("div"); card.className = "apg-card"; card.append(addText("strong", `${layer.replaceAll("_", " ")} · ${relations.length}`));
      card.append(addText("span", relations.map(edge => { const other = nodesById.get(edge.source === id ? edge.target : edge.source); return `${other?.label || "Unknown"} — ${edge.relation_type.replaceAll("_", " ")}`; }).join("; "))); controls.detail.append(card);
    });
    if (node.kind === "protocol") governanceSurface(node);
  }

  cy.on("tap", "edge", event => showEdge(event.target.id()));
  cy.on("tap", "node", event => {
    cy.elements().removeClass("faded");
    const neighbourhood = event.target.closedNeighborhood();
    cy.elements().difference(neighbourhood).addClass("faded");
    showNode(event.target.id());
  });
  cy.on("tap", event => { if (event.target === cy) { cy.elements().removeClass("faded"); showPrompt(cy.edges().length); } });
  Object.values(controls).filter(item => item instanceof HTMLSelectElement || item instanceof HTMLInputElement).forEach(control => control.addEventListener("change", () => { cy.elements().removeClass("faded"); updateGraph(); }));
  updateGraph();
  const graphWrap = root.querySelector(".apg-graph-wrap");
  let fittedWidth = 0;
  const hostIsVisible = () => {
    const frame = window.frameElement;
    return !frame || (
      frame.offsetParent !== null &&
      getComputedStyle(frame).visibility !== "hidden"
    );
  };
  const fitWhenVisible = (force = false) => {
    const width = graphWrap.getBoundingClientRect().width;
    if (hostIsVisible() && width > 0 && (force || width !== fittedWidth)) {
      fittedWidth = width;
      cy.resize();
      const displayed = cy.nodes().filter(node => node.style("display") !== "none");
      cy.fit(displayed, 54);
      root.dataset.apgFit = `${displayed.length}/${cy.edges().length}`;
    }
  };
  new ResizeObserver(fitWhenVisible).observe(graphWrap);
  const visibilityTimer = window.setInterval(() => {
    if (hostIsVisible()) {
      fitWhenVisible(true);
      window.clearInterval(visibilityTimer);
    }
  }, 200);
  requestAnimationFrame(() => fitWhenVisible());
})();
</script>
"""
