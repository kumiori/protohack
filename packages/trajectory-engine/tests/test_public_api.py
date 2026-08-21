from datetime import datetime, timezone

import pytest

from trajectory_engine import (
    build_trajectory_document, normalise_trajectory_document, realize_primitive,
)


def test_realisation_is_append_only_and_does_not_move_plan():
    primitive = {"id": "m1", "type": "event", "time_parameter": 0.25, "status": "Planned"}
    realised = realize_primitive(
        primitive, status="Done", changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actual_timestamp="2026-01-01T00:00:00+00:00",
    )
    assert realised["time_parameter"] == 0.25
    assert realised["realization_history"][0]["status"] == "Planned"


def test_unknown_schema_fails_explicitly():
    with pytest.raises(ValueError, match="Unsupported trajectory schema"):
        normalise_trajectory_document({"schema_version": "trajectory-plan/v99"})


def test_canonical_document_preserves_explicit_branch_topology():
    document = build_trajectory_document(
        plan={"title": "Plan"},
        primitives=[{"id": "b", "type": "event", "time_parameter": 0.5, "topology_mode": "branching"}],
        uncertainty=[],
    )
    assert document["primitives"][0]["topology_mode"] == "branching"
    assert len(document["primitives"][0]["branch_labels"]) == 2
