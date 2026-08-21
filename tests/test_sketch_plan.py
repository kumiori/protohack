from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from protocol.timeline_plan import (
    QUALITATIVE_TIME_ANCHORS,
    build_plan_payload,
    duration_in_days,
    linear_time_ticks,
    plan_summary,
    qualitative_time_label,
)
from protocol.trajectory_schema import (
    DEFAULT_CAMERA,
    SCHEMA_VERSION,
    build_trajectory_document,
    load_trajectory_yaml,
    trajectory_yaml,
)


ROOT = Path(__file__).parent.parent
VIEW = ROOT / "views" / "test_sketch_plan.py"
GAME_VIEW = ROOT / "views" / "test_timeline_game.py"
APP = ROOT / "app.py"


def button(app: AppTest, label: str):
    matches = [candidate for candidate in app.button if candidate.label == label]
    assert len(matches) == 1
    return matches[0]


def button_group(app: AppTest, label: str):
    matches = [candidate for candidate in app.button_group if candidate.label == label]
    assert len(matches) == 1
    return matches[0]


def open_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "title": "Launch the field guide",
        "description": "Make the first public prototype available.",
        "initial_condition": "A draft exists but nobody has tested it.",
        "goal_statement": "The prototype is publicly accessible.",
        "goal_conditions": "A reader can complete the main path.",
        "landing_mode": "Open",
        "temporal_mode": "Qualitative",
        "created_at": "2026-08-05T10:30:00+03:00",
    }
    values.update(overrides)
    return build_plan_payload(**values)  # type: ignore[arg-type]


def test_qualitative_time_is_an_ordered_nonuniform_parameterisation() -> None:
    assert QUALITATIVE_TIME_ANCHORS == (
        ("Now", 0.0),
        ("Soon", 0.12),
        ("Later", 0.35),
        ("Sometime", 0.58),
        ("Eventually", 0.80),
        ("Landing", 1.0),
    )
    assert qualitative_time_label(0.10) == "Soon"
    assert qualitative_time_label(0.60) == "Sometime"
    assert qualitative_time_label(0.96) == "Landing"


def test_open_plan_begins_now_without_an_authored_start_or_target_date() -> None:
    payload = open_payload()

    assert payload["start_date"] == "2026-08-05"
    assert payload["created_at"] == "2026-08-05T10:30:00+03:00"
    assert payload["landing_mode"] == "open"
    assert payload["target_date"] is None
    assert "end_date" not in payload
    assert payload["temporal_mode"] == "qualitative"
    assert payload["axis_y_label"] == "Uncertainty"


def test_guided_and_fixed_landings_preserve_their_distinct_meanings() -> None:
    guided = open_payload(
        landing_mode="Guided",
        guided_value=6,
        guided_unit="Months",
    )
    fixed = open_payload(
        landing_mode="Fixed",
        temporal_mode="Linear",
        fixed_kind="Duration",
        fixed_value=6,
        fixed_unit="Weeks",
        linear_unit="Weeks",
    )

    assert guided["landing_mode"] == "guided"
    assert guided["duration_label"] == "6 months"
    assert guided["guided_value"] == 6
    assert guided["guided_unit"] == "Months"
    assert guided["horizon_days"] == 180
    assert guided["target_date"] is None
    assert fixed["landing_mode"] == "planned"
    assert fixed["horizon_days"] == 42
    assert fixed["end_date"] == "2026-09-16"
    assert duration_in_days(48, "Hours") == 2


def test_linear_time_ticks_are_proportional_and_calendar_facing() -> None:
    day_ticks = linear_time_ticks(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 21),
        unit="Days",
    )
    month_ticks = linear_time_ticks(
        start_date=date(2026, 8, 15),
        end_date=date(2026, 11, 15),
        unit="Months",
    )

    assert day_ticks == (
        (0.0, "Day 0"),
        (0.25, "Day 5"),
        (0.5, "Day 10"),
        (0.75, "Day 15"),
        (1.0, "Day 20"),
    )
    assert month_ticks[0] == (0.0, "15 Aug")
    assert month_ticks[-1] == (1.0, "15 Nov")
    assert (17 / 92, "Sep") in month_ticks
    assert (47 / 92, "Oct") in month_ticks


def test_plan_review_uses_goal_and_player_facing_landing_copy() -> None:
    summary = dict(plan_summary(open_payload()))

    assert summary["Plan"] == "Launch the field guide"
    assert summary["Now"] == "A draft exists but nobody has tested it."
    assert summary["Goal"] == "The prototype is publicly accessible."
    assert summary["Landing"] == "Open"
    assert summary["Time language"] == "Qualitative"
    assert "Duration" not in summary


def test_sketch_page_is_a_separate_registered_entrance() -> None:
    app_source = APP.read_text(encoding="utf-8")
    view_source = VIEW.read_text(encoding="utf-8")

    assert '"views/test_sketch_plan.py"' in app_source
    assert 'url_path="test-sketch-plan"' in app_source
    assert "Sketch a new plan" in view_source
    assert "Open the latest saved plan" in view_source
    assert "Import a trajectory YAML" in view_source
    assert "Try a benchmark" in view_source
    assert "There is no start date to configure" in view_source
    assert "Enter the trajectory field" in view_source
    assert '[data-testid="stSidebar"]' in view_source


def test_latest_saved_plan_uses_a_user_activated_plan_tab() -> None:
    view_source = VIEW.read_text(encoding="utf-8")

    assert 'target="_blank"' in view_source
    assert 'rel="noopener"' in view_source
    assert "window.parent.location.href" not in view_source


def test_guided_onboarding_reaches_a_semantic_trajectory_preview() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()

    button(app, "Sketch a new plan").click().run()
    app.text_input[0].set_value("Prepare a workshop").run()
    button(app, "Establish now →").click().run()
    app.text_area[0].set_value("We have a topic but no venue.").run()
    button(app, "Define the goal →").click().run()
    app.text_input[0].set_value("The workshop has taken place.").run()
    button(app, "Choose how to land →").click().run()
    button_group(app, "Landing mode").set_value("Open").run()
    button(app, "Choose the time language →").click().run()
    button_group(app, "Time language").set_value("Qualitative").run()
    button(app, "Generate the path →").click().run()

    assert not app.exception
    assert app.session_state["sketch_plan_stage"] == "confirm"
    rendered = "\n".join(markdown.value for markdown in app.markdown)
    assert "Your path now exists." in rendered
    assert "The curve is provisional" in rendered
    assert "Prepare a workshop" in rendered
    assert "The workshop has taken place." in rendered
    assert "Time language" in rendered


def test_new_plan_editor_preserves_the_complete_primitive_set() -> None:
    app = AppTest.from_file(str(GAME_VIEW), default_timeout=10)
    app.session_state["timeline_active_benchmark"] = open_payload()
    app.session_state["timeline_game_landing_mode"] = "Open"
    app.run()

    labels = {candidate.label for candidate in app.button}
    assert {
        "Release",
        "Event",
        "Action",
        "Update",
        "Milestone",
        "≈  Add local uncertainty",
    } <= labels
    assert {
        "Information gateway",
        "Merge",
        "Share resources",
        "Acquire resources",
        "Delegate",
        "Wait",
        "Prepare",
        "Get intelligence",
        "Synchronise",
        "Save locally",
        "Integrate trajectory",
    } <= labels
    assert {candidate.label for candidate in app.get("download_button")} == {
        "Export YAML"
    }
    rendered = "\n".join(markdown.value for markdown in app.markdown)
    assert "What should happen—not necessarily first" in rendered
    assert "Uncertainty" in rendered

    button(app, "Action").click().run()
    rendered = "\n".join(markdown.value for markdown in app.markdown)
    assert "Qualitative" in rendered
    assert "Horizon" in rendered
    assert "Date" not in rendered


def test_yaml_round_trip_preserves_editable_geometry_and_camera() -> None:
    plan = open_payload()
    document = build_trajectory_document(
        plan=plan,
        primitives=[
            {
                "id": "move-1",
                "type": "gateway",
                "title": "Share the briefing",
                "time_parameter": 0.4,
                "importance": "Lever",
                "node_mode": "kink",
                "energy_offset": None,
                "alignment_offset": None,
                "influence_width": None,
            }
        ],
        uncertainty=[
            {
                "id": "cloud-1",
                "start_parameter": 0.32,
                "end_parameter": 0.58,
                "strength": "Strong",
                "profile_mode": "expands",
                "radius": None,
                "opacity": None,
            }
        ],
        camera=DEFAULT_CAMERA,
    )

    restored = load_trajectory_yaml(trajectory_yaml(document))

    assert restored["schema_version"] == SCHEMA_VERSION
    assert restored["plan"]["initial_condition"] == plan["initial_condition"]
    assert restored["primitives"][0]["type"] == "gateway"
    assert restored["primitives"][0]["node_mode"] == "kink"
    assert restored["primitives"][0]["influence_scale"] == "Structural"
    assert restored["primitives"][0]["directional_mode"] == "abruptly"
    assert restored["primitives"][0]["topology_mode"] == "continuation"
    assert restored["primitives"][0]["visibility"] == "Private"
    assert restored["primitives"][0]["dependencies"] == []
    assert restored["primitives"][0]["branch_labels"] == []
    assert restored["primitives"][0]["modified_at"]
    assert restored["primitives"][0]["energy_offset"] > 0
    assert restored["uncertainty"][0]["profile_mode"] == "expands"
    assert restored["uncertainty"][0]["radius"] > 0
    assert restored["view"]["camera"] == DEFAULT_CAMERA


def test_legacy_yaml_without_a_version_migrates_bifurcation_and_empty_details() -> None:
    legacy = {
        "plan": open_payload(),
        "primitives": [
            {
                "id": "legacy-branch",
                "type": "event",
                "title": "Choose the route",
                "time_parameter": 0.48,
                "importance": "Threshold",
                "node_mode": "bifurcation",
                "dependencies": None,
                "collaborators": None,
                "tags": None,
            }
        ],
        "uncertainty": [],
    }

    restored = load_trajectory_yaml(trajectory_yaml(legacy))
    move = restored["primitives"][0]

    assert restored["schema_version"] == SCHEMA_VERSION
    assert move["influence_scale"] == "Dominant"
    assert move["directional_mode"] == "gradually"
    assert move["topology_mode"] == "branching"
    assert [branch["label"] for branch in move["branch_labels"]] == [
        "Option A",
        "Option B",
    ]
    assert all(branch["parent_id"] == move["id"] for branch in move["branch_labels"])
    assert move["dependencies"] == []
    assert move["collaborators"] == []
    assert move["tags"] == []
    assert move["description"] == ""
    assert move["visibility"] == "Private"


def test_move_can_name_a_binary_branch_and_store_optional_details() -> None:
    app = AppTest.from_file(str(GAME_VIEW), default_timeout=10).run()

    button(app, "Delegate").click().run()
    app.text_input[0].set_value("Hand over facilitation")
    button_group(app, "How much does this change the journey?").set_value(
        "Dominant"
    ).run()
    button_group(app, "How does this change the direction of the path?").set_value(
        "Abruptly"
    ).run()
    button_group(app, "Topology").set_value("Bifurcation").run()
    app.text_input[1].set_value("Continue")
    app.text_input[2].set_value("Change course")
    app.text_area[0].set_value("The host transfers authority to the working group.")
    button(app, "Place delegate").click().run()

    assert not app.exception
    move = app.session_state["timeline_game_events"][0]
    assert move["type"] == "delegate"
    assert move["influence_scale"] == "Dominant"
    assert move["directional_mode"] == "abruptly"
    assert move["topology_mode"] == "branching"
    assert [branch["label"] for branch in move["branch_labels"]] == [
        "Continue",
        "Change course",
    ]
    assert move["description"] == (
        "The host transfers authority to the working group."
    )
    assert move["modified_at"]


def test_rc0_document_contains_the_complete_move_contract() -> None:
    document = build_trajectory_document(
        plan=open_payload(),
        primitives=[
            {
                "id": "move-contract",
                "type": "acquire_resources",
                "title": "Secure the venue",
                "time_parameter": 0.35,
                "influence_scale": "Structural",
                "directional_mode": "gradually",
                "topology_mode": "continuation",
            }
        ],
        uncertainty=[],
    )
    move = document["primitives"][0]

    assert {
        "id",
        "type",
        "title",
        "time_parameter",
        "temporal_position",
        "date",
        "influence_scale",
        "directional_mode",
        "topology_mode",
        "branch_parent",
        "branch_labels",
        "energy_effect",
        "uncertainty_effect",
        "entropy_effect",
        "influence_radius",
        "description",
        "intention",
        "dependencies",
        "responsible_actors",
        "collaborators",
        "resources_needed",
        "completion_evidence",
        "visibility",
        "tags",
        "notes",
        "created_at",
        "modified_at",
    } <= set(move)
    for field in (
        "branch_labels",
        "dependencies",
        "responsible_actors",
        "collaborators",
        "resources_needed",
        "completion_evidence",
        "tags",
    ):
        assert move[field] == []


def test_landing_stage_tolerates_a_deselected_mode_and_blocks_continue() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10)
    app.session_state["sketch_plan_stage"] = "landing"
    app.session_state["sketch_plan_value_landing_mode"] = None

    app.run()

    assert not app.exception
    assert button(app, "Choose the time language →").disabled is True


def test_time_stage_tolerates_a_deselected_mode_and_blocks_generation() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10)
    app.session_state["sketch_plan_stage"] = "time"
    app.session_state["sketch_plan_value_temporal_mode"] = None

    app.run()

    assert not app.exception
    assert button(app, "Generate the path →").disabled is True


def test_branch_details_are_progressively_disclosed() -> None:
    app = AppTest.from_file(str(GAME_VIEW), default_timeout=10).run()
    button(app, "Action").click().run()

    labels = {item.label for item in app.text_input}
    assert "First branch name" not in labels
    assert "Second branch name" not in labels

    button_group(app, "Topology").set_value("Bifurcation").run()

    labels = {item.label for item in app.text_input}
    assert {"First branch name", "Second branch name"} <= labels
    assert any(item.label == "Number of branches" for item in app.number_input)


def test_rc01_typographic_scale_is_shared_by_planner_surfaces() -> None:
    onboarding = VIEW.read_text(encoding="utf-8")
    timeline = GAME_VIEW.read_text(encoding="utf-8")
    benchmark = (ROOT / "views" / "test_timeline_benchmarks.py").read_text(
        encoding="utf-8"
    )

    for source in (onboarding, timeline, benchmark):
        assert "--type-hero:clamp(42px,5.2vw,72px)" in source
        assert "--type-body:clamp(15px,1.1vw,17px)" in source
