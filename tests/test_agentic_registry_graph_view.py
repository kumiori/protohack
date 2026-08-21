from copy import deepcopy
from pathlib import Path

import pytest

from agentic_registry import load_compiled_artifacts
from agentic_registry.graph_view import (
    GraphArtifactError,
    SHARED_PROTOCOL_FILTER_KEY,
    build_multiplex_graph_html,
)


ROOT = Path(__file__).parent.parent


def _compiled_graph() -> dict:
    return load_compiled_artifacts(ROOT / "agentic_registry" / "generated").graph


def _compiled_transition(transition_id: str) -> dict:
    cards = load_compiled_artifacts(
        ROOT / "agentic_registry" / "generated"
    ).transition_cards["cards"]
    return next(card for card in cards if card["id"] == transition_id)


def test_renderer_consumes_compiled_graph_contract_and_vendored_cytoscape() -> None:
    graph = _compiled_graph()

    html = build_multiplex_graph_html(graph)

    assert "Cytoscape Consortium" in html
    assert "cdn.jsdelivr" not in html
    assert "unpkg.com" not in html
    assert 'layout: { name: "preset"' in html
    assert 'position: node.position' in html
    assert "new ResizeObserver(fitWhenVisible)" in html
    renderer_source = html.split("</script>", 1)[1]
    assert '"width": 42, "height": 42' in renderer_source
    assert "generic influence" not in renderer_source


def test_renderer_has_exact_layers_and_operational_default() -> None:
    graph = _compiled_graph()

    html = build_multiplex_graph_html(graph)

    assert 'option(controls.layer, "operational", "Operational / institutional", true)' in html
    assert 'if (selectedLayer === "operational" && !edge.default_visible) return false;' in html
    assert "visible.has(node.id())" in html
    for layer in graph["layers"]:
        assert f'"id":"{layer["id"]}"' in html
    assert "All recorded relations" in html


def test_renderer_uses_half_open_time_predicate_and_exposes_genealogy() -> None:
    html = build_multiplex_graph_html(_compiled_graph())

    assert "start <= day && (!end || day < end)" in html
    assert 'id="apg-date" type="date"' in html
    assert 'id="apg-genealogy" type="checkbox"' in html
    assert "graph.genealogy_edges" in html


def test_renderer_exposes_evidence_and_layered_neighbourhood_details() -> None:
    html = build_multiplex_graph_html(_compiled_graph())

    assert "Supporting evidence" in html
    assert "edge.evidence_state" in html
    assert "edge.confidence" in html
    assert "Neighbourhood by active layer" in html
    assert "Governance surface" in html
    assert "Transfer of stewardship" in html
    assert "Open primary source" in html


def test_renderer_accepts_page_level_protocol_selection_without_repositioning() -> None:
    graph = _compiled_graph()

    html = build_multiplex_graph_html(
        graph, protocol_ids=["protocol_mcp", "not_an_admitted_protocol"]
    )

    assert '"shared_protocol_ids":["protocol_mcp"]' in html
    assert "Page selection (" in html
    assert SHARED_PROTOCOL_FILTER_KEY == "agentic_map_protocols"
    assert "cy.nodes().ungrabify()" in html


def test_transition_selection_sets_graph_date_and_highlights_the_same_state() -> None:
    graph = _compiled_graph()
    transition = _compiled_transition("transition_a2a_lf_contribution")

    html = build_multiplex_graph_html(
        graph,
        protocol_ids=["protocol_a2a"],
        selected_date="2025-06-23",
        selected_transition=transition,
    )

    assert '"selected_date":"2025-06-23"' in html
    assert '"selected_transition_id":"transition_a2a_lf_contribution"' in html
    assert '"transition_actor_ids":["org_a2a_project","org_linux_foundation"]' in html
    assert "config.selected_date || graph.metadata.observed_at" in html
    assert 'selector: ".transition-focus"' in html
    assert "transitionFocus.has(node.id())" in html


def test_renderer_rejects_graph_without_compiled_fixed_positions() -> None:
    graph = deepcopy(_compiled_graph())
    graph["nodes"][0].pop("position")

    with pytest.raises(GraphArtifactError, match="fixed position"):
        build_multiplex_graph_html(graph)
