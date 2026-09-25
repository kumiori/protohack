"""Live, sequential Probe persistence contract against disposable Notion rows.

Run explicitly with:
PROTOHACK_RUN_LIVE_NOTION=1 pytest -q -s tests/test_notion_persistence_kernel_live.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

import pytest
from probe_engine import ProbeRuntime, trajectory_from_dict

from protocol.probe_access import access_code_from_key, latest_returning_record
from protocol.probe_draft import load_probe_state
from protocol.probe_registry import resolve_probe
from protocol.probe_store import ProbeRepositoryStore
from storage.context import notion_token
from storage.notion import NotionRepository, _rich
from storage.notion import ProbeSubmissionCommitError


FIXTURE = Path(__file__).parent / "fixtures" / "montreal_comprehensive_response.yaml"
LIVE = os.getenv("PROTOHACK_RUN_LIVE_NOTION") == "1"


def _physical_player_pages(repository: NotionRepository, participant_id: str):
    return [
        page
        for page in repository._query_all(
            "players",
            filter_={
                "property": "participant_id",
                "rich_text": {"equals": participant_id},
            },
        )
        if _rich(page.get("properties") or {}, "participant_id") == participant_id
    ]


def _physical_response_pages(repository: NotionRepository, participation_id: str):
    return [
        page
        for page in repository._query_all(
            "responses",
            filter_={
                "property": "participation_id",
                "rich_text": {"equals": participation_id},
            },
        )
        if _rich(page.get("properties") or {}, "participation_id") == participation_id
    ]


def _cleanup(
    repository: NotionRepository, participant_id: str, participation_id: str
) -> dict[str, int]:
    players = _physical_player_pages(repository, participant_id)
    player_ids = [str(page["id"]) for page in players]
    responses = _physical_response_pages(repository, participation_id)
    response_ids = [str(page["id"]) for page in responses]
    result = repository.archive_probe_cleanup(response_ids, player_ids)
    for page_id in response_ids + player_ids:
        assert repository._client.pages.retrieve(page_id=page_id)["archived"] is True
    return result


def _submit(repository, probe, runtime, code, participation_id):
    store = ProbeRepositoryStore(
        repository,
        probe=probe,
        probe_id=probe.id,
        participant_id=runtime.trajectory.participation.participant_id,
        scope_id=runtime.trajectory.participation.scope_id,
        environment="test",
        batch_id="persistence-kernel-live",
    )
    store.set_access_code(
        emoji=code.emoji,
        selector=code.selector,
        selector_6=code.selector_6,
        verifier=code.verifier,
    )
    prepared = runtime.prepare_finalisation(idempotency_key=participation_id)
    try:
        runtime.finalise(store, idempotency_key=participation_id, prepared=prepared)
    except ProbeSubmissionCommitError as exc:
        print("PERSISTENCE_KERNEL_FAILURE " + json.dumps(exc.receipt, sort_keys=True))
        raise
    assert store.last_receipt and store.last_receipt["success"] is True
    return store.last_receipt["repository_result"]


@pytest.mark.skipif(not LIVE, reason="explicit live Notion opt-in required")
@pytest.mark.parametrize("run_index", range(3))
def test_notion_player_response_create_recover_revise_retry_cleanup(run_index: int):
    token = notion_token()
    assert token, "Notion credential is required for the live persistence contract"
    repository = NotionRepository(token=token)
    registration = resolve_probe(event_slug="commons-montreal", variant="short")
    probe = registration.load()
    participant_id = f"probe-kernel-live-{run_index}"
    participation_id = f"probe-kernel-live-participation-{run_index}"
    _cleanup(repository, participant_id, participation_id)

    source = FIXTURE.read_text(encoding="utf-8")
    trajectory = load_probe_state(
        source,
        probe=probe,
        participant_id=participant_id,
        participation_id=participation_id,
        expected_scope_id=registration.session_code,
    )
    runtime = ProbeRuntime.hydrate(
        probe,
        trajectory,
        participant_id=participant_id,
        scope_id=registration.session_code,
    )
    code = access_code_from_key(str(uuid.uuid4()))

    first_receipt = _submit(
        repository, probe, runtime, code, participation_id
    )
    assert first_receipt["revision"] == 1
    players = _physical_player_pages(repository, participant_id)
    responses = _physical_response_pages(repository, participation_id)
    assert len(players) == 1
    assert len(responses) == 1
    player_id = str(players[0]["id"])
    assert _rich(players[0]["properties"], "access_code_emoji") == code.emoji
    assert [item["id"] for item in responses[0]["properties"]["player"]["relation"]] == [player_id]

    recovered_rows = repository.find_probe_trajectories_by_access_selector(code.selector)
    recovered = latest_returning_record(recovered_rows, supplied_verifier=code.verifier)
    assert recovered["participant_id"] == participant_id
    first_submission_id = recovered["submission_id"]
    revised = ProbeRuntime.hydrate(
        probe,
        trajectory_from_dict(recovered["trajectory"]),
        participant_id=participant_id,
        scope_id=registration.session_code,
    )
    revised.answer("availability", ["oct28_pm_inrs"])
    second_receipt = _submit(
        repository, probe, revised, code, participation_id
    )
    assert second_receipt["revision"] == 2

    players = _physical_player_pages(repository, participant_id)
    responses = _physical_response_pages(repository, participation_id)
    assert len(players) == 1
    assert len(responses) == 2
    assert all(
        [item["id"] for item in page["properties"]["player"]["relation"]] == [player_id]
        for page in responses
    )
    assert _rich(players[0]["properties"], "access_code_emoji") == code.emoji
    recovered_latest = latest_returning_record(
        repository.find_probe_trajectories_by_access_selector(code.selector),
        supplied_verifier=code.verifier,
    )
    assert recovered_latest["submission_id"] != first_submission_id
    second_submission_id = recovered_latest["submission_id"]

    retry_receipt = _submit(
        repository,
        probe,
        ProbeRuntime.hydrate(
            probe,
            trajectory_from_dict(recovered_latest["trajectory"]),
            participant_id=participant_id,
            scope_id=registration.session_code,
        ),
        code,
        participation_id,
    )
    assert retry_receipt["revision"] == 2
    assert len(_physical_player_pages(repository, participant_id)) == 1
    assert len(_physical_response_pages(repository, participation_id)) == 2
    assert _rich(_physical_player_pages(repository, participant_id)[0]["properties"], "access_code_emoji") == code.emoji

    cleanup = _cleanup(repository, participant_id, participation_id)
    assert cleanup == {"responses": 2, "players": 1, "other": 0}
    report = {
        "run": run_index + 1,
        "player_page_id": player_id,
        "submission_ids": [first_submission_id, second_submission_id],
        "receipts": [
            first_receipt.get("response_page_id"),
            second_receipt.get("response_page_id"),
            retry_receipt.get("response_page_id"),
        ],
        "revisions": [1, 2, 2],
        "counts": {"players": 1, "responses": 2},
        "cleanup": cleanup,
    }
    print("PERSISTENCE_KERNEL " + json.dumps(report, sort_keys=True))
