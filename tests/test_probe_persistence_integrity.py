from protocol.probe_cleanup import plan_probe_cleanup
from protocol.probe_results import (
    assert_integrated_submission,
    audit_probe_submissions,
)

import pytest


def _row(**changes):
    row = {
        "_page_id": "response-1",
        "record_type": "probe_submission",
        "event_id": "montreal_communs_2026",
        "probe_id": "montreal_communs_data_ai_short_2026",
        "probe_revision": 5,
        "submission_id": "submission-1",
        "state": "submitted",
        "created_at": "2026-09-24T10:00:00+00:00",
        "integrated_at": "2026-09-24T10:05:00+00:00",
        "revision": 1,
        "environment": "test",
        "participant_id": "participant-1",
        "player_page_id": "player-1",
        "payload": {"schema": "probe-submission/v1"},
        "trajectory": {"events": [{"kind": "answered"}]},
    }
    row.update(changes)
    return row


@pytest.mark.parametrize(
    "missing",
    ["event_id", "probe_id", "probe_revision", "submission_id", "integrated_at"],
)
def test_integrated_submission_rejects_each_missing_canonical_field(missing: str) -> None:
    row = _row()
    row[missing] = ""
    with pytest.raises(ValueError, match=missing):
        assert_integrated_submission(row)


def test_results_use_latest_valid_submission_per_player_and_explain_exclusions() -> None:
    first = _row()
    latest = _row(
        _page_id="response-2",
        submission_id="submission-2",
        revision=2,
        integrated_at="2026-09-24T11:05:00+00:00",
        trajectory={"events": [{"kind": "answered"}, {"kind": "integrated"}]},
    )
    malformed = _row(
        _page_id="response-3",
        submission_id="",
        player_page_id="",
    )
    other_event = _row(
        _page_id="response-4",
        participant_id="participant-2",
        player_page_id="player-2",
        event_id="another_event",
    )

    audit = audit_probe_submissions(
        [first, latest, malformed, other_event],
        event_id="montreal_communs_2026",
        probe_id="montreal_communs_data_ai_short_2026",
    )

    assert audit.counts["physical_rows"] == 4
    assert audit.counts["valid_canonical_envelopes"] == 2
    assert audit.counts["distinct_submission_ids"] == 2
    assert audit.counts["distinct_participants"] == 1
    assert audit.counts["trajectories_used"] == 1
    assert [row["submission_id"] for row in audit.included] == ["submission-2"]
    reasons = [reason for row in audit.excluded for reason in row["exclusion_reasons"]]
    assert "superseded by later submission" in reasons
    assert "missing submission_id" in reasons
    assert "different event_id" in reasons


def test_cleanup_scope_is_exact_and_players_are_archived_only_when_orphaned() -> None:
    target = _row()
    shared_player_production = _row(
        _page_id="response-production",
        submission_id="production",
        environment="production",
        created_at="2026-09-23T10:00:00+00:00",
    )
    other_player = _row(
        _page_id="response-2",
        submission_id="submission-2",
        participant_id="participant-2",
        player_page_id="player-2",
    )
    legacy = _row(
        _page_id="legacy",
        name="montreal_communs_data_ai_short_2026 trajectory",
        event_id="",
        probe_id="",
        environment="",
    )

    plan = plan_probe_cleanup(
        [target, shared_player_production, other_player, legacy],
        event_id="montreal_communs_2026",
        probe_id="montreal_communs_data_ai_short_2026",
        cutoff="2026-09-25T00:00:00+00:00",
    )

    assert {row["_page_id"] for row in plan.responses} == {"response-1", "response-2"}
    assert plan.player_page_ids == ("player-2",)
    assert [row["_page_id"] for row in plan.legacy_candidates] == ["legacy"]
    assert plan.responses_export()["kind"] == "Responses"
