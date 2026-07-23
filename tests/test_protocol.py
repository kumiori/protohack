from pathlib import Path

import pytest

from protocol import build_strategic_profile, load_protocol, normalize_rationale


def test_smoke_protocol_has_semantic_identifiers_and_authored_tags() -> None:
    protocol = load_protocol()

    assert protocol.scenario.id.startswith("SCN_")
    assert protocol.scenario.decision.id.startswith("DEC_")
    assert {action.id for action in protocol.scenario.decision.actions} == {
        "ACT_001",
        "ACT_002",
        "ACT_003",
    }
    assert all(action.semantic_tags for action in protocol.scenario.decision.actions)
    assert protocol.tagger_version == "authored-actions-v1"
    assert protocol.interaction.question_actions == ("continue", "flag", "skip")
    assert protocol.interaction.feedback_profile == "iceicebaby-v1"
    assert protocol.interaction.skip_requires_reason is True
    assert protocol.interaction.confirmation_before_integration is True
    assert protocol.interaction.show_textual_return_key is True
    assert protocol.interaction.show_full_verification_hash is True
    assert protocol.interaction.balloons_after_integration is True


def test_yaml_yes_remains_a_string(tmp_path: Path) -> None:
    source = Path("protocol/specs/commons_smoke_v1.yaml").read_text(encoding="utf-8")
    source = source.replace("Questioning the Commons", "Yes", 1)
    candidate = tmp_path / "protocol.yaml"
    candidate.write_text(source, encoding="utf-8")

    assert load_protocol(candidate).title == "Yes"


def test_profile_uses_authored_action_tags_and_verbatim_rationale() -> None:
    protocol = load_protocol()
    profile = build_strategic_profile(
        protocol=protocol,
        participant_uuid="00000000-0000-4000-8000-000000000001",
        action_id="ACT_002",
        rationale="  People affected should frame   the problem together.  ",
        integrated_at="2026-07-22T12:00:00+00:00",
    )

    assert profile["semantic_tags"] == ["participation", "legitimacy", "dialogue"]
    assert profile["rationale"] == "People affected should frame the problem together."
    assert profile["participant_alias"].startswith("P-")
    assert "00000000" not in profile["participant_alias"]


def test_rationale_is_required_and_bounded() -> None:
    with pytest.raises(ValueError):
        normalize_rationale("   ")
    with pytest.raises(ValueError):
        normalize_rationale("x" * 601)
