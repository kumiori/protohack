from pathlib import Path


ROOT = Path(__file__).parent.parent
PAGE = ROOT / "views" / "agentic_protocol_map.py"


def test_agentic_protocol_map_is_a_discoverable_registered_capability() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    feature_registry = (ROOT / "FEATURE_REGISTRY.md").read_text(encoding="utf-8")

    assert '"views/agentic_protocol_map.py"' in app_source
    assert 'url_path="agentic-protocol-map"' in app_source
    assert "| Certified agentic protocol timeline and evidence cards |" in feature_registry
    assert "| Institutional regime rails, transitions and before/after cards |" in feature_registry
    assert "| Temporal multiplex actor–protocol network |" in feature_registry
    assert "| Strict registry compiler and semantic safeguards |" in feature_registry


def test_page_consumes_one_compiled_contract_for_both_views() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "load_compiled_artifacts()" in source
    assert "compiled.timeline" in source
    assert "compiled.graph" in source
    assert "compiled.transition_cards" in source
    assert "transition_cards=transition_cards" in source
    assert "selected_transition=selected_transition" in source
    assert "selected_date=_transition_graph_date(selected_transition)" in source
    assert 'SHARED_PROTOCOL_KEY = "agentic_map_protocols"' in source
    assert "yaml" not in source.lower()


def test_page_exposes_all_requested_governance_dimensions_without_inference() -> None:
    source = PAGE.read_text(encoding="utf-8")

    for field in (
        "governing_body",
        "technical_steering_committee",
        "voting_organisations",
        "named_representatives",
        "appointment_intervals",
        "maintainer_intervals",
        "decision_procedure",
        "transfer_of_stewardship",
    ):
        assert f'("{field}",' in source
    assert "Not recorded in the certified registry" in source
    assert "Missing fields are not inferred" in source


def test_timeline_dominates_the_header_and_counters_are_compact() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'class="agentic-map-stats"' in source
    assert "st.columns(6)" not in source
    assert ".metric(" not in source
    assert 'with st.popover("Filter protocols"' in source
    assert source.index("agentic-map-stats") < source.index("st.tabs(")
