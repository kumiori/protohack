from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from protocol.timeline import (
    CORE_EVENT_TYPE_KEYS,
    EVENT_TYPES,
    IMPORTANCE_LEVELS,
    PLANNING_PRIMITIVE_KEYS,
    UNCERTAINTY_STRENGTHS,
    active_events,
    control_nodes,
    date_for_parameter,
    event_points,
    expanded_bounds,
    geometry_for_importance,
    kink_indicators,
    node_tangents,
    parameter_for_date,
    reconcile_event_dates,
    relative_time_label,
    sample_trajectory,
    trajectory_point,
    uncertainty_envelope_points,
    uncertainty_geometry,
    uncertainty_profile,
    uncertainty_radius,
)


ROOT = Path(__file__).parent.parent
VIEW = ROOT / "views" / "test_timeline_game.py"
APP = ROOT / "app.py"
START = date(2026, 7, 29)
END = START + timedelta(days=730)


def event(
    *,
    event_id: str = "event-1",
    event_type: str = "event",
    parameter: float = 0.34,
    importance: str = "Lever",
    node_mode: str = "smooth",
) -> dict[str, object]:
    geometry = geometry_for_importance(importance)
    return {
        "id": event_id,
        "type": event_type,
        "title": "First field signal",
        "time_parameter": parameter,
        "date_value": date_for_parameter(
            parameter,
            start_date=START,
            end_date=END,
        ).isoformat(),
        "time_basis": "date",
        "interval_start": START.isoformat(),
        "interval_end": END.isoformat(),
        "importance": importance,
        "node_mode": node_mode,
        "energy_offset": geometry["energy_offset"],
        "alignment_offset": 0.0,
        "influence_width": geometry["influence_width"],
        "interval_status": "active",
        "created_at": "2026-07-29",
    }


def uncertainty(
    *,
    center: float = 0.5,
    width: float = 0.2,
    strength: str = "Marked",
) -> dict[str, object]:
    return {
        "id": "uncertainty-1",
        "center_parameter": center,
        "temporal_width": width,
        "strength": strength,
        **uncertainty_geometry(strength),
    }


def button(app: AppTest, label: str):
    matches = [candidate for candidate in app.button if candidate.label == label]
    assert len(matches) == 1
    return matches[0]


def test_placed_events_are_hard_hermite_nodes() -> None:
    placed = event(parameter=0.37)
    x, y, z = event_points([placed])
    evaluated = trajectory_point(0.37, [placed])

    assert (x[0], y[0], z[0]) == pytest.approx(evaluated)
    assert x[0] == pytest.approx(0.37)
    assert y[0] == pytest.approx(0.0)


def test_smooth_node_has_one_continuous_tangent() -> None:
    nodes = control_nodes([event(node_mode="smooth")])
    tangents = node_tangents(nodes)

    incoming, outgoing = tangents[1]
    assert incoming == pytest.approx(outgoing)


def test_kink_preserves_position_but_splits_the_tangent() -> None:
    placed = event(parameter=0.42, node_mode="kink")
    nodes = control_nodes([placed])
    incoming, outgoing = node_tangents(nodes)[1]
    at_node = trajectory_point(0.42, [placed])

    assert incoming != pytest.approx(outgoing)
    assert trajectory_point(0.42 - 1e-7, [placed]) == pytest.approx(
        at_node,
        abs=1e-5,
    )
    assert trajectory_point(0.42 + 1e-7, [placed]) == pytest.approx(
        at_node,
        abs=1e-5,
    )
    assert len(kink_indicators([placed])) == 1


def test_importance_controls_amplitude_and_influence_width() -> None:
    signal = geometry_for_importance("Signal")
    threshold = geometry_for_importance("Threshold")

    assert threshold["energy_offset"] > signal["energy_offset"]
    assert threshold["influence_width"] > signal["influence_width"]

    signal_z = event_points([event(importance="Signal")])[2][0]
    threshold_z = event_points([event(importance="Threshold")])[2][0]
    assert threshold_z > signal_z


def test_uncertainty_is_local_and_never_changes_the_centreline() -> None:
    events = [event(parameter=0.42, importance="Threshold")]
    centreline_before = sample_trajectory(events)
    chunk = uncertainty(center=0.62, width=0.18)

    assert uncertainty_profile(
        0.62,
        center=0.62,
        temporal_width=0.18,
    ) == pytest.approx(1.0)
    assert uncertainty_profile(
        0.30,
        center=0.62,
        temporal_width=0.18,
    ) == 0.0
    assert uncertainty_radius(0.62, chunk) == pytest.approx(chunk["radius"])
    assert sample_trajectory(events) == centreline_before
    assert len(control_nodes(events)) == 3


def test_uncertainty_strength_widens_and_lowers_alpha() -> None:
    light = uncertainty_geometry("Light")
    strong = uncertainty_geometry("Strong")

    assert strong["radius"] > light["radius"]
    assert strong["opacity"] < light["opacity"]
    assert tuple(UNCERTAINTY_STRENGTHS) == ("Light", "Marked", "Strong")


def test_uncertainty_envelope_collapses_outside_its_interval() -> None:
    x = [0.2, 0.4, 0.5, 0.6, 0.8]
    y = [0.0] * len(x)
    z = [0.2] * len(x)
    envelope_x, envelope_y, envelope_z = uncertainty_envelope_points(
        x,
        y,
        z,
        uncertainty(center=0.5, width=0.2),
        radial_fraction=1.0,
        angle_fraction=0.0,
    )

    assert envelope_x == [None, None, 0.5, None, None]
    assert envelope_y[2] > y[2]
    assert envelope_z[2] == pytest.approx(z[2])


def test_personal_alignment_remains_neutral() -> None:
    events = [
        event(event_id="release", event_type="release", parameter=0.2),
        event(event_id="action", event_type="action", parameter=0.7),
    ]
    _, event_y, _ = event_points(events)

    assert event_y == [0.0, 0.0]
    assert "synthetic_alignment" not in VIEW.read_text(encoding="utf-8")


def test_date_is_authoritative_when_the_interval_changes() -> None:
    placed = event(parameter=0.5)
    authored_date = date.fromisoformat(str(placed["date_value"]))
    reconciled = reconcile_event_dates(
        [placed],
        start_date=START,
        end_date=date(2029, 7, 29),
    )[0]

    assert reconciled["date_value"] == authored_date.isoformat()
    assert float(reconciled["time_parameter"]) == pytest.approx(
        parameter_for_date(
            authored_date,
            start_date=START,
            end_date=date(2029, 7, 29),
        )
    )


def test_outside_events_are_flagged_not_deleted() -> None:
    placed = event()
    placed["date_value"] = "2030-01-01"
    placed.pop("interval_start")
    placed.pop("interval_end")

    reconciled = reconcile_event_dates(
        [placed],
        start_date=START,
        end_date=END,
    )

    assert len(reconciled) == 1
    assert reconciled[0]["interval_status"] == "outside"
    assert active_events(reconciled) == []


def test_adaptive_slider_readings_include_position_language_and_date() -> None:
    assert date_for_parameter(
        0.5,
        start_date=START,
        end_date=END,
    ) == date(2027, 7, 29)
    assert relative_time_label(
        0.04,
        start_date=START,
        end_date=END,
    ) == "Soon"
    assert relative_time_label(
        0.75,
        start_date=START,
        end_date=END,
    ) == "Year 2"


def test_session_bounds_expand_but_never_contract() -> None:
    initial = {"y": [-0.32, 0.32], "z": [0.0, 0.78]}
    expanded = expanded_bounds(
        initial,
        y_values=[-0.6, 0.1],
        z_values=[0.2, 1.0],
    )
    repeated = expanded_bounds(
        expanded,
        y_values=[-0.1, 0.1],
        z_values=[0.2, 0.4],
    )

    assert expanded["y"][0] < -0.6
    assert expanded["z"][1] > 1.0
    assert repeated == expanded


def test_geometry_is_deterministic_and_landing_modes_change_arrival() -> None:
    events = [event(parameter=0.62, importance="Threshold")]

    assert sample_trajectory(events) == sample_trajectory(events)
    open_tangent = node_tangents(control_nodes(events), landing_mode="open")[-1]
    guided_tangent = node_tangents(
        control_nodes(events),
        landing_mode="guided",
    )[-1]
    assert open_tangent != guided_tangent


def test_shapes_carry_the_event_vocabulary() -> None:
    assert {
        event_type: definition["glyph"]
        for event_type, definition in EVENT_TYPES.items()
    } == {
        "release": "★",
        "event": "●",
        "gateway": "◈",
        "action": "▲",
        "update": "■",
        "milestone": "▼",
        "merge": "⋈",
        "share_resources": "⇄",
        "wait": "◷",
        "prepare": "◒",
        "get_intelligence": "⌾",
        "synchronise": "⟳",
    }
    assert CORE_EVENT_TYPE_KEYS == (
        "release",
        "event",
        "gateway",
        "action",
        "update",
        "milestone",
    )
    assert PLANNING_PRIMITIVE_KEYS == (
        "merge",
        "share_resources",
        "wait",
        "prepare",
        "get_intelligence",
        "synchronise",
    )
    assert tuple(IMPORTANCE_LEVELS) == ("Signal", "Lever", "Threshold")


def test_timeline_is_an_isolated_registered_test_surface() -> None:
    view_source = VIEW.read_text(encoding="utf-8")
    app_source = APP.read_text(encoding="utf-8")

    assert '"views/test_timeline_game.py"' in app_source
    assert 'url_path="test-timeline-game"' in app_source
    assert "st.plotly_chart(" in view_source
    assert '"uirevision": "timeline-camera-v2"' in view_source
    assert "plotly_relayout" in view_source
    assert "sessionStorage" in view_source
    assert "scene.getCamera()" in view_source
    assert "scene.camera.lookAt(" in view_source
    assert "uncertainty_envelope_points(" in view_source
    assert "Add local uncertainty" in view_source
    assert "UNCERTAINTY PREVIEW" in view_source
    assert "st.slider(" in view_source
    assert "st.toast(" not in view_source
    assert "Place {MINIMUM_MOVES} moves to integrate this test trajectory." in (
        view_source
    )
    assert "No record has been saved." in view_source
    assert "How much does this change the journey?" in view_source
    assert "Does this bend the path…" in view_source
    assert '"Signal": "Small influence"' in view_source
    assert '"Kink": "Bifurcation"' in view_source
    assert "Try rotating the view" in view_source


def test_guided_benchmark_dates_and_destination_drive_the_scene() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10)
    app.session_state["timeline_active_benchmark"] = {
        "title": "Cook dinner for friends",
        "horizon_label": "2 hours",
        "horizon_days": 1,
        "start_date": "2026-08-02",
        "end_date": "2026-08-03",
        "destination_label": "Dinner served",
        "guided_setup": True,
        "suggested_moves": ("Action · buy ingredients",),
    }
    app.run()

    assert not app.exception
    rendered = "\n".join(markdown.value for markdown in app.markdown)
    captions = "\n".join(caption.value for caption in app.caption)
    assert "02 Aug 2026 → 03 Aug 2026" in captions
    assert "Add a move" in rendered
    assert "Your path exists. Now shape it." in rendered
    assert button(app, "▲  buy ingredients")


def test_first_move_appears_without_a_second_click() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()
    button(app, "★  Release").click().run()
    app.slider[0].set_value(0.32).run()
    app.text_input[0].set_value("Open the field")
    button(app, "Place release").click().run()

    assert not app.exception
    placed = app.session_state["timeline_game_events"][0]
    assert placed["title"] == "Open the field"
    assert placed["time_parameter"] == pytest.approx(0.32)
    assert placed["date_value"] == date_for_parameter(
        0.32,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=730),
    ).isoformat()
    assert placed["node_mode"] == "smooth"
    assert placed["alignment_offset"] == 0.0
    assert button(app, "↶ Undo last").disabled is False


def test_three_moves_unlock_session_only_integration() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10)
    app.session_state["timeline_game_events"] = [
        event(event_id="release", event_type="release", parameter=0.2),
        event(event_id="action", event_type="action", parameter=0.55),
        event(event_id="milestone", event_type="milestone", parameter=0.82),
    ]
    app.run()

    integrate = button(app, "Integrate trajectory")
    assert integrate.disabled is False
    integrate.click().run()

    assert not app.exception
    assert [message.value for message in app.success] == [
        "Trajectory integrated for this session. No record has been saved."
    ]


def test_uncertainty_modifier_is_stored_without_adding_a_move() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()
    button(app, "≈  Add local uncertainty").click().run()
    app.slider[0].set_value(0.58).run()
    app.slider[1].set_value(0.24).run()
    button(app, "Anchor uncertainty").click().run()

    assert not app.exception
    assert app.session_state["timeline_game_events"] == []
    chunks = app.session_state["timeline_game_uncertainties"]
    assert len(chunks) == 1
    assert chunks[0]["center_parameter"] == pytest.approx(0.58)
    assert chunks[0]["temporal_width"] == pytest.approx(0.24)
    assert chunks[0]["strength"] == "Marked"
    assert button(app, "Integrate trajectory").disabled is True
