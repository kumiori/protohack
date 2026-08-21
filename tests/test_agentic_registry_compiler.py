import json
from pathlib import Path

import pytest

from agentic_registry import (
    RegistryValidationError,
    StrictDuplicateKeyError,
    compile_registry,
    default_registry_path,
    load_compiled_artifacts,
    load_registry_strict,
    write_compiled_artifacts,
)


def _registry_text() -> str:
    return default_registry_path().read_text(encoding="utf-8")


def test_certified_snapshot_compiles_to_the_shared_renderer_contract() -> None:
    result = compile_registry()

    assert result.validation["valid"] is True
    assert result.validation["counts"] == {
        "actors": 41,
        "protocols": 6,
        "protocol_versions": 21,
        "protocol_events": 23,
        "actor_protocol_relations": 52,
        "protocol_protocol_relations": 7,
        "protocol_regimes": 34,
        "protocol_transitions": 6,
        "frontier_candidates": 5,
        "evidence_sources": 46,
    }
    assert len(result.timeline["items"]) == 15
    assert len(result.graph["nodes"]) == 47
    assert len(result.graph["edges"]) == 63
    assert len(result.graph["genealogy_edges"]) == 7
    assert len(result.transition_cards["cards"]) == 6


def test_a2a_regimes_drive_current_stewards_graph_edges_and_timeline_state() -> None:
    result = compile_registry()

    transition = next(
        card
        for card in result.transition_cards["cards"]
        if card["id"] == "transition_a2a_lf_contribution"
    )
    assert transition["effective"]["start"] == "2025-06-23"
    assert {regime["status"] for regime in transition["before"]} == {"unknown"}
    assert {
        (participant["actor_id"], participant["role"])
        for regime in transition["after"]
        for participant in regime["participants"]
    } == {
        ("org_linux_foundation", "institutional_home"),
        ("org_a2a_project", "governing_project"),
    }

    a2a = next(
        protocol
        for protocol in result.timeline["protocols"]
        if protocol["id"] == "protocol_a2a"
    )
    assert a2a["current_steward_ids"] == [
        "org_a2a_project",
        "org_linux_foundation",
    ]
    derived = {
        (edge["source"], edge["relation_type"], edge["valid_from"]["start"])
        for edge in result.graph["edges"]
        if edge.get("derived_from_regime_id") == "regime_a2a_lf_stewardship"
    }
    assert derived == {
        ("org_a2a_project", "STEWARDED_BY", "2025-06-23"),
        ("org_linux_foundation", "STEWARDED_BY", "2025-06-23"),
    }
    assert "evt_a2a_lf_transfer" not in {
        item["id"] for item in result.timeline["items"]
    }


def test_mcp_governance_changes_before_stewardship() -> None:
    result = compile_registry()
    transitions = {card["id"]: card for card in result.transition_cards["cards"]}

    governance = transitions["transition_mcp_governance_adoption"]
    stewardship = transitions["transition_mcp_aaif_donation"]
    assert governance["effective"]["start"] == "2025-07-31"
    assert stewardship["effective"]["start"] == "2025-12-09"
    assert governance["effective"]["start"] < stewardship["effective"]["start"]
    assert governance["after"][0]["regime_type"] == "governance"
    assert stewardship["after"][0]["regime_type"] == "stewardship"

    mcp_governor = next(
        edge
        for edge in result.graph["edges"]
        if edge.get("derived_from_regime_id") == "regime_mcp_maintainer_governance"
    )
    mcp_steward = next(
        edge
        for edge in result.graph["edges"]
        if edge.get("derived_from_regime_id") == "regime_mcp_aaif_stewardship"
    )
    assert mcp_governor["relation_type"] == "GOVERNED_BY"
    assert mcp_governor["valid_from"]["start"] == "2025-07-31"
    assert mcp_steward["relation_type"] == "STEWARDED_BY"
    assert mcp_steward["valid_from"]["start"] == "2025-12-09"


def test_ap2_transfer_preserves_asset_level_partial_effects() -> None:
    result = compile_registry()
    transition = next(
        card
        for card in result.transition_cards["cards"]
        if card["id"] == "transition_ap2_fido_contribution"
    )

    assert {item["asset"]: item["effect"] for item in transition["transfer_effect"]} == {
        "normative_specification": "transferred",
        "standards_process": "transferred",
        "reference_repository": "retained_by_originator",
        "implementation_maintenance": "unresolved",
    }
    repository_regime = next(
        regime
        for regime in result.timeline["regimes"]
        if regime["id"] == "regime_ap2_google_repository_control"
    )
    assert repository_regime["valid_to"]["value"] is None
    assert repository_regime["participants"][0]["actor_id"] == "org_google"
    ap2 = next(
        protocol
        for protocol in result.timeline["protocols"]
        if protocol["id"] == "protocol_ap2"
    )
    assert ap2["current_steward_ids"] == ["org_fido"]


def test_acp_merger_is_one_directed_transition_with_a_historical_archive() -> None:
    result = compile_registry()
    transition = next(
        card
        for card in result.transition_cards["cards"]
        if card["id"] == "transition_acp_a2a_merger"
    )

    assert [item["id"] for item in transition["source_protocols"]] == [
        "protocol_acp"
    ]
    assert transition["target_protocol"]["id"] == "protocol_a2a"
    assert transition["genealogy_relation_id"] == "pp_acp_a2a"
    assert transition["effective"]["start"] == "2025-08-27"
    assert transition["source_status_after"] == "archived"
    assert transition["migration_path"]
    assert transition["compatibility_effect"]

    acp = next(
        protocol
        for protocol in result.timeline["protocols"]
        if protocol["id"] == "protocol_acp"
    )
    assert acp["lifeline"]["end"]["start"] == "2025-08-27"
    assert "evt_acp_archive" in {item["id"] for item in result.timeline["items"]}
    assert "evt_a2a_acp_merge" not in {
        item["id"] for item in result.timeline["items"]
    }


def test_x402_preserves_the_uncertain_transfer_interval() -> None:
    result = compile_registry()
    transition = next(
        card
        for card in result.transition_cards["cards"]
        if card["id"] == "transition_x402_lf_contribution"
    )

    assert transition["announced_at"]["start"] == "2026-04-02"
    assert transition["effective"] == {
        "mode": "interval",
        "value": None,
        "precision": "interval",
        "start": "2026-04-02",
        "end": "2026-07-14",
    }
    assert transition["completion_confirmed_at"]["start"] == "2026-07-14"
    regimes = {regime["id"]: regime for regime in result.timeline["regimes"]}
    assert regimes["regime_x402_unknown_stewardship"]["valid_to"]["start"] == (
        "2026-07-14"
    )
    assert regimes["regime_x402_lf_stewardship"]["valid_from"]["start"] == (
        "2026-07-14"
    )


def test_unresolved_institutional_state_is_an_explicit_unknown_regime() -> None:
    result = compile_registry()
    ucp_regime = next(
        regime
        for regime in result.timeline["regimes"]
        if regime["id"] == "regime_ucp_unknown_stewardship"
    )
    ucp = next(
        protocol
        for protocol in result.timeline["protocols"]
        if protocol["id"] == "protocol_ucp"
    )

    assert ucp_regime["status"] == "unknown"
    assert ucp_regime["participants"] == []
    assert ucp_regime["evidence"]
    assert ucp["current_steward_ids"] == []


def test_timeline_and_graph_expose_the_same_stewardship_state_by_date() -> None:
    result = compile_registry()

    def active(start: str | None, end: str | None, selected: str) -> bool:
        return bool(start and start <= selected and (not end or selected < end))

    for selected_date in ("2025-06-22", "2025-06-23", "2026-07-14"):
        for protocol_id in result.timeline["protocol_order"]:
            timeline_actors = {
                participant["actor_id"]
                for regime in result.timeline["regimes"]
                if regime["protocol_id"] == protocol_id
                and regime["regime_type"] == "stewardship"
                and active(
                    regime["valid_from"]["start"],
                    regime["valid_to"]["start"],
                    selected_date,
                )
                for participant in regime["participants"]
            }
            graph_actors = {
                edge["source"]
                for edge in result.graph["edges"]
                if edge["target"] == protocol_id
                and edge["relation_type"] == "STEWARDED_BY"
                and active(
                    edge["valid_from"]["start"],
                    edge["valid_to"]["start"],
                    selected_date,
                )
            }
            assert graph_actors == timeline_actors


def test_institutional_state_is_not_authored_twice() -> None:
    raw = load_registry_strict(default_registry_path())

    assert all("current_steward_ids" not in protocol for protocol in raw["protocols"])
    assert not {
        relation["relation_type"]
        for relation in raw["actor_protocol_relations"]
    }.intersection({"STEWARDED_BY", "GOVERNED_BY"})
    assert raw["registry"]["institutional_state_contract"] == {
        "source_collection": "protocol_regimes",
        "current_steward_ids": "compiler_derived",
        "steward_graph_edges": "compiler_derived",
        "governor_graph_edges": "compiler_derived",
    }


def test_regime_overlap_is_rejected_only_within_matching_scope(tmp_path: Path) -> None:
    source = tmp_path / "overlap.yaml"
    source.write_text(
        _registry_text().replace(
            "  - id: regime_a2a_lf_stewardship\n"
            "    protocol_id: protocol_a2a\n"
            "    regime_type: stewardship\n"
            "    status: verified\n",
            "  - id: regime_a2a_lf_stewardship\n"
            "    protocol_id: protocol_a2a\n"
            "    regime_type: stewardship\n"
            "    status: verified\n",
            1,
        ).replace(
            "    valid_from: 2025-06-23\n"
            "    valid_to: null\n"
            "    asset_scope: [specification, sdk, tooling]\n",
            "    valid_from: 2025-06-22\n"
            "    valid_to: null\n"
            "    asset_scope: [specification, sdk, tooling]\n",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError) as caught:
        compile_registry(source)

    assert "overlapping_regime_scope" in {
        issue["code"] for issue in caught.value.report["errors"]
    }


def test_complete_transfer_must_cover_matching_before_and_after_scopes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incomplete_transfer.yaml"
    source.write_text(
        _registry_text().replace(
            "      - {asset: tooling, effect: transferred}\n"
            "    governance_instrument: A2A Project governance",
            "    governance_instrument: A2A Project governance",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError) as caught:
        compile_registry(source)

    assert "incomplete_transfer_scope" in {
        issue["code"] for issue in caught.value.report["errors"]
    }


def test_every_displayed_claim_has_resolvable_evidence_cards() -> None:
    result = compile_registry()
    displayed_claims = [
        *result.timeline["items"],
        *result.timeline["regimes"],
        *result.graph["edges"],
        *result.transition_cards["cards"],
    ]

    assert displayed_claims
    assert all(record["evidence"] for record in displayed_claims)
    assert all(
        card["id"] and card["title"] and card["url"].startswith("https://")
        for record in displayed_claims
        for card in record["evidence"]
    )
    assert all(card["observed_at"] == "2026-08-07" for record in displayed_claims for card in record["evidence"])


def test_partial_dates_are_half_open_intervals_and_unknown_dates_stay_off_axis() -> None:
    result = compile_registry()
    x402_launch = next(item for item in result.timeline["items"] if item["id"] == "evt_x402_launch")
    unknown_a2a_version = next(item for item in result.timeline["supplemental_versions"] if item["id"] == "a2a_0_1_0")
    yearly_vote = next(edge for edge in result.graph["edges"] if edge["id"] == "rel_a2a_ibm_vote")

    assert x402_launch["date"] == {
        "value": "2025-05",
        "precision": "month",
        "start": "2025-05-01",
        "end": "2025-06-01",
    }
    assert yearly_vote["valid_from"] == {
        "value": "2025",
        "precision": "year",
        "start": "2025-01-01",
        "end": "2026-01-01",
    }
    assert unknown_a2a_version["date"] == {
        "value": None,
        "precision": "unknown",
        "start": None,
        "end": None,
    }


def test_timeline_protocol_order_and_lifelines_are_compiler_owned() -> None:
    timeline = compile_registry().timeline

    assert [protocol["acronym"] for protocol in timeline["protocols"]] == [
        "MCP",
        "A2A",
        "ACP",
        "AP2",
        "UCP",
        "x402",
    ]
    assert timeline["protocol_order"] == [
        "protocol_mcp",
        "protocol_a2a",
        "protocol_acp",
        "protocol_ap2",
        "protocol_ucp",
        "protocol_x402",
    ]
    protocols = {item["id"]: item for item in timeline["protocols"]}
    assert protocols["protocol_mcp"]["lifeline"]["end"]["value"] == "2026-08-07"
    assert protocols["protocol_acp"]["lifeline"]["end"] == {
        "value": "2025-08-27",
        "precision": "day",
        "start": "2025-08-27",
        "end": None,
    }
    assert protocols["protocol_acp"]["lifeline"]["end_reason"] == "merged_into"
    assert protocols["protocol_acp"]["lifeline"]["target_protocol"]["id"] == (
        "protocol_a2a"
    )


def test_relation_taxonomy_remains_multiplex_and_superseded_protocol_is_retained() -> None:
    result = compile_registry()
    mapping = result.graph["metadata"]["relation_layer_map"]

    assert [layer["id"] for layer in result.graph["layers"]] == [
        "authorship",
        "governance",
        "maintenance",
        "implementation",
        "adoption",
        "funding",
        "endorsement",
        "convening",
    ]
    assert mapping["ANNOUNCES_SUPPORT_FOR"] == "endorsement"
    assert mapping["MEMBER_OF_STEWARD"] == "convening"
    assert mapping["CONTRIBUTES_CODE"] == "implementation"
    assert mapping["MAINTAINS"] == "maintenance"
    assert next(node for node in result.graph["nodes"] if node["id"] == "protocol_acp")["status"] == "superseded"


def test_governance_surface_exposes_exact_records_and_explicit_gaps() -> None:
    result = compile_registry()
    protocols = {item["id"]: item for item in result.timeline["protocols"]}
    a2a = protocols["protocol_a2a"]["governance_surface"]
    ap2 = protocols["protocol_ap2"]["governance_surface"]

    assert len(a2a["voting_organisations"]) == 8
    assert a2a["decision_procedure"] is None
    assert "decision_procedure" in a2a["gaps"]
    assert ap2["governing_body"][0]["actor"]["id"] == "body_fido_ptwg"
    assert ap2["technical_steering_committee"] == []
    assert ap2["named_representatives"] == []
    assert ap2["appointment_intervals"] == []
    assert ap2["maintainer_intervals"] == []
    assert ap2["transfer_of_stewardship"][0]["evidence"]


def test_duplicate_yaml_keys_are_rejected_before_semantic_compilation(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.yaml"
    source.write_text("registry:\n  id: first\n  id: second\n", encoding="utf-8")

    with pytest.raises(StrictDuplicateKeyError, match="duplicate YAML key 'id'"):
        load_registry_strict(source)


def test_missing_references_and_open_relation_sentinel_fail_validation(tmp_path: Path) -> None:
    source = tmp_path / "invalid.yaml"
    text = _registry_text().replace("actor_id: org_anthropic", "actor_id: org_missing", 1)
    text = text.replace("valid_to: null, evidence_state: primary_verified", "evidence_state: primary_verified", 1)
    source.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryValidationError) as caught:
        compile_registry(source)

    codes = {item["code"] for item in caught.value.report["errors"]}
    assert "unresolved_reference" in codes
    assert "missing_valid_to" in codes


def test_undeclared_partial_date_fails_validation(tmp_path: Path) -> None:
    source = tmp_path / "invalid_date.yaml"
    source.write_text(
        _registry_text().replace(
            "event_date: 2025-05, date_precision: month",
            "event_date: 2025-05",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError) as caught:
        compile_registry(source)

    assert "undeclared_date_precision" in {
        item["code"] for item in caught.value.report["errors"]
    }


def test_compact_artifacts_are_deterministic_and_load_as_one_snapshot(tmp_path: Path) -> None:
    first = compile_registry()
    paths = write_compiled_artifacts(first, tmp_path)
    first_bytes = {name: path.read_bytes() for name, path in paths.items()}
    write_compiled_artifacts(compile_registry(), tmp_path)

    assert {name: path.read_bytes() for name, path in paths.items()} == first_bytes
    assert all(b"\n  " not in content for content in first_bytes.values())
    loaded = load_compiled_artifacts(tmp_path)
    assert loaded.timeline == first.timeline
    assert loaded.graph == first.graph
    assert loaded.transition_cards == first.transition_cards
    assert json.loads(paths["validation"].read_text())["valid"] is True
