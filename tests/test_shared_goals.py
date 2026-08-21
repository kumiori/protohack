from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from protocol.shared_goals import (
    BUNDLE_SCHEMA_VERSION,
    build_goal_bundle,
    build_goal_trajectory,
    build_shared_goal,
    goal_bundle_yaml,
    load_goal_bundle_yaml,
    revised_goal_trajectory,
)
from protocol.timeline_plan import build_plan_payload
from protocol.trajectory_schema import build_trajectory_document
from storage.memory import InMemoryRepository


ROOT = Path(__file__).parent.parent


def trajectory(title: str = "X path") -> dict[str, object]:
    plan = build_plan_payload(
        title=title,
        description="",
        initial_condition="We have an idea.",
        goal_statement="The panel has taken place.",
        goal_conditions="",
        landing_mode="Open",
        temporal_mode="Qualitative",
        created_at="2026-08-10T12:00:00+03:00",
    )
    return build_trajectory_document(plan=plan, primitives=[], uncertainty=[])


def contribution(agent_id: str = "x", title: str = "X path") -> dict[str, object]:
    return build_goal_trajectory(
        trajectory(title),
        goal_id="summit-2027",
        agent_id=agent_id,
        agent_display_name=agent_id.upper(),
        created_at="2026-08-10T13:00:00+03:00",
    )


def test_coordination_wraps_an_unchanged_canonical_trajectory() -> None:
    original = trajectory()
    shared = build_goal_trajectory(
        original,
        goal_id="summit-2027",
        agent_id="committee",
        agent_display_name="Organising committee",
        agent_type="team",
    )

    assert shared["goal_id"] == "summit-2027"
    assert shared["agent_type"] == "team"
    assert shared["trajectory_payload"] == original
    assert "goal_id" not in shared["trajectory_payload"]["plan"]
    assert "agent_id" not in shared["trajectory_payload"]["plan"]


def test_goal_is_public_but_does_not_define_time_landing_or_owner() -> None:
    goal = build_shared_goal(
        goal_id="summit-2027",
        title="AI Summit 2027",
        objective="Organise an intervention.",
        created_by_agent_id="andres",
    )

    assert goal["visibility"] == "public"
    assert goal["status"] == "open"
    assert "owner" not in goal
    assert "time_language" not in goal
    assert "landing_mode" not in goal


def test_bundle_snapshot_preserves_independent_contributions() -> None:
    goal = build_shared_goal(goal_id="summit-2027", title="AI Summit 2027")
    restored = load_goal_bundle_yaml(goal_bundle_yaml(build_goal_bundle(
        goal=goal,
        trajectories=[contribution("x", "X path"), contribution("y", "Y path")],
    )))

    assert restored["schema_version"] == BUNDLE_SCHEMA_VERSION
    assert [item["agent_id"] for item in restored["trajectories"]] == ["x", "y"]
    assert restored["trajectories"][0]["trajectory_payload"]["plan"]["title"] == "X path"


def test_repository_rejects_duplicate_agent_until_explicit_revision() -> None:
    repository = InMemoryRepository()
    repository.create_shared_goal(build_shared_goal(goal_id="summit-2027", title="Goal"))
    first = contribution()
    repository.record_goal_trajectory(first)

    with pytest.raises(ValueError, match="already has a trajectory"):
        repository.record_goal_trajectory(contribution(title="Alternate"))

    revised = revised_goal_trajectory(
        first,
        trajectory("Revised path"),
        agent_id="x",
        updated_at="2026-08-10T14:00:00+03:00",
    )
    saved = repository.record_goal_trajectory(revised, update_existing=True)
    assert saved["trajectory_id"] == first["trajectory_id"]
    assert saved["created_at"] == first["created_at"]
    assert saved["revision"] == 2


def test_shared_goal_routes_and_social_actions_are_discoverable() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    view = (ROOT / "views" / "shared_goals.py").read_text(encoding="utf-8")
    editor = (ROOT / "views" / "test_timeline_game.py").read_text(encoding="utf-8")
    onboarding = (ROOT / "views" / "test_sketch_plan.py").read_text(encoding="utf-8")

    assert 'url_path="shared-goals"' in app
    assert "Create public shared goal" in view
    assert "Sketch my trajectory" in view
    assert "Share existing trajectory" in view
    assert 'st.tabs(("Trajectories", "Shared history", "Compare", "Overlay"))' in view
    assert "Join existing goal" not in view
    assert "Share with a goal" in editor
    assert "Update shared trajectory" in editor
    assert "Nothing is shared until" in onboarding


def test_create_goal_form_never_deadlocks_its_required_title() -> None:
    app = AppTest.from_file(
        str(ROOT / "views" / "shared_goals.py"),
        default_timeout=10,
    ).run()

    create = next(
        button for button in app.button
        if button.label == "Create public shared goal"
    )
    assert create.disabled is False

    create.click().run()
    assert not app.exception
    assert any(
        error.value == "Enter a goal title before creating the shared goal."
        for error in app.error
    )
