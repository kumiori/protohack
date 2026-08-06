"""A session-only, game-like timeline interaction study."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import html
import json
from math import cos, sin
from textwrap import dedent
from uuid import uuid4

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from protocol.timeline import (
    END_POINT,
    EVENT_TYPES,
    CORE_EVENT_TYPE_KEYS,
    INFLUENCE_SCALES,
    LEGACY_INFLUENCE_SCALES,
    PLANNING_PRIMITIVE_KEYS,
    UNCERTAINTY_STRENGTHS,
    active_events,
    binary_branch_stems,
    date_for_parameter,
    directional_mode,
    event_points,
    expanded_bounds,
    geometry_for_influence,
    kink_indicators,
    primitive_plot_label,
    reconcile_event_dates,
    relative_time_label,
    sample_trajectory,
    topology_mode,
    trajectory_point,
    uncertainty_geometry,
    uncertainty_tube_mesh,
)
from protocol.timeline_plan import (
    QUALITATIVE_TIME_ANCHORS,
    linear_time_ticks,
    qualitative_time_label,
)
from protocol.trajectory_schema import (
    DEFAULT_CAMERA,
    LOCAL_STORAGE_LATEST_KEY,
    LOCAL_STORAGE_PREFIX,
    build_trajectory_document,
    trajectory_yaml,
)


STATE_PREFIX = "timeline_game_"
MINIMUM_MOVES = 3
ACTIVE_BENCHMARK_KEY = "timeline_active_benchmark"
STYLE_LAB_ENABLED = bool(globals().get("TIMELINE_STYLE_LAB", False))
STYLE_LAB_VARIANTS = ("Instrument", "Playground", "Gallery")
STYLE_LAB_KEY = "timeline_style_lab_variant"
style_lab_variant = str(
    st.session_state.get(STYLE_LAB_KEY) or "Playground"
)
if style_lab_variant not in STYLE_LAB_VARIANTS:
    style_lab_variant = "Playground"
active_benchmark = st.session_state.get(ACTIVE_BENCHMARK_KEY)
if not isinstance(active_benchmark, dict):
    active_benchmark = {}
source_kind = str(active_benchmark.get("source_kind") or "benchmark")
is_new_plan = source_kind == "plan"
temporal_mode = str(active_benchmark.get("temporal_mode") or "linear")
axis_y_label = str(active_benchmark.get("axis_y_label") or "Alignment")
benchmark_title = str(active_benchmark.get("title") or "Open trajectory")
benchmark_horizon = str(
    active_benchmark.get("horizon_label") or "2-year experimental horizon"
)
benchmark_days = max(1, int(active_benchmark.get("horizon_days") or 730))
try:
    ROADMAP_START = date.fromisoformat(
        str(active_benchmark.get("start_date") or "")
    )
except ValueError:
    ROADMAP_START = date.today()
try:
    ROADMAP_END = date.fromisoformat(
        str(active_benchmark.get("end_date") or "")
    )
except ValueError:
    ROADMAP_END = ROADMAP_START + timedelta(days=benchmark_days)
if ROADMAP_END <= ROADMAP_START:
    ROADMAP_END = ROADMAP_START + timedelta(days=benchmark_days)
destination_label = str(
    active_benchmark.get("destination_label") or ""
).strip()
initial_landing_label = {
    "open": "Open",
    "guided": "Guided",
    "planned": "Planned",
}.get(str(active_benchmark.get("landing_mode") or "open"), "Open")
CAMERA_STORAGE_KEY = "protocol-hack:timeline-camera-v2"
INFLUENCE_COPY = {
    "Local": "Local effect",
    "Structural": "Structural effect",
    "Dominant": "Dominant effect",
}
INFLUENCE_HELP = {
    "Local": "Changes the path near this moment.",
    "Structural": "Changes the path at the scale of the whole plan.",
    "Dominant": "Reorganises what follows and may outweigh several moves.",
}
LANDING_COPY = {
    "Open": "Find the way",
    "Guided": "Arrive in a zone",
    "Planned": "Follow a plan",
}


def _state(name: str, default: object) -> object:
    return st.session_state.setdefault(f"{STATE_PREFIX}{name}", default)


def _event_label(event: dict[str, object]) -> str:
    definition = EVENT_TYPES[str(event["type"])]
    return f"{definition['glyph']} {event['title']}"


def _event_influence(event: dict[str, object]) -> str:
    authored = str(event.get("influence_scale") or "")
    return LEGACY_INFLUENCE_SCALES.get(authored, authored) or LEGACY_INFLUENCE_SCALES.get(
        str(event.get("importance") or ""),
        "Structural",
    )


def _branch_label_values(event: dict[str, object] | None) -> tuple[str, str]:
    values: list[str] = []
    if event:
        raw_labels = event.get("branch_labels") or ()
        if isinstance(raw_labels, (list, tuple)):
            for item in raw_labels[:2]:
                values.append(
                    str(item.get("label") or "")
                    if isinstance(item, dict)
                    else str(item)
                )
    return (
        values[0] if values else "Option A",
        values[1] if len(values) > 1 else "Option B",
    )


def _widget_key(name: str) -> str:
    return f"{STATE_PREFIX}{name}"


def _apply_pending_widget_reset() -> None:
    reset = st.session_state.pop(_widget_key("placement_reset"), None)
    if not isinstance(reset, dict):
        return
    for name, value in reset.items():
        st.session_state[_widget_key(name)] = value


def _request_placement(
    event_type: str,
    *,
    event: dict[str, object] | None = None,
    title: str = "",
) -> None:
    st.session_state[_widget_key("pending_type")] = event_type
    st.session_state[_widget_key("pending_uncertainty")] = False
    st.session_state[_widget_key("editing_id")] = (
        str(event["id"]) if event else None
    )
    branch_a, branch_b = _branch_label_values(event)
    st.session_state[_widget_key("placement_reset")] = {
        "time_slider": float(event["time_parameter"]) if event else 0.22,
        "form_title": str(event["title"]) if event else title,
        "influence_scale": _event_influence(event) if event else "Structural",
        "directional_mode": (
            directional_mode(event).title() if event else "Gradually"
        ),
        "topology_mode": (
            "Bifurcation"
            if event and topology_mode(event) == "branching"
            else "Continuation"
        ),
        "branch_label_a": branch_a,
        "branch_label_b": branch_b,
        "description": str(event.get("description") or "") if event else "",
    }
    st.session_state[_widget_key("integrated")] = False


def _render_journey_progress(move_count: int) -> None:
    if not active_benchmark.get("guided_setup"):
        return
    labels = (
        (
            "Plan",
            "Now",
            "Goal",
            "Landing",
            "Time",
            "Trajectory",
            "Shape",
            "Observe",
        )
        if is_new_plan
        else (
            "Benchmark",
            "Horizon",
            "Destination",
            "Trajectory",
            "Add a move",
            "Observe",
            "Continue",
            "Compare",
        )
    )
    if is_new_plan:
        current = 6 if move_count == 0 else 7
    elif move_count == 0:
        current = 4
    elif move_count == 1:
        current = 5
    elif move_count == 2:
        current = 6
    else:
        current = 7
    items: list[str] = []
    for index, label in enumerate(labels):
        if index < current:
            marker, state = "✓", "done"
        elif index == current:
            marker, state = "→", "current"
        else:
            marker, state = "○", "pending"
        items.append(
            f'<div class="timeline-journey-step {state}"><b>{marker}</b>'
            f"<span>{html.escape(label)}</span></div>"
        )
    st.markdown(
        f'<div class="timeline-journey-steps">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def _suggested_move_parts(suggestion: object) -> tuple[str, str] | None:
    text = str(suggestion)
    label, separator, title = text.partition(" · ")
    if not separator or not title.strip():
        return None
    for key, definition in EVENT_TYPES.items():
        if str(definition["label"]).casefold() == label.strip().casefold():
            return key, title.strip()
    return None


def _time_language_label(parameter: float) -> str:
    if temporal_mode == "qualitative":
        return qualitative_time_label(parameter)
    return relative_time_label(
        parameter,
        start_date=ROADMAP_START,
        end_date=ROADMAP_END,
    )


def _time_readout(
    parameter: float,
    value_date: date,
    current_landing_mode: str,
) -> str:
    if temporal_mode == "qualitative":
        return f"""
        <div class="timeline-time-readout">
          <div><small>Horizon</small><b>{html.escape(_time_language_label(parameter))}</b></div>
          <div><small>Language</small><b>Qualitative</b></div>
          <div><small>Landing</small><b>Goal</b></div>
        </div>
        """
    if current_landing_mode != "planned":
        return f"""
        <div class="timeline-time-readout">
          <div><small>Horizon</small><b>{html.escape(_time_language_label(parameter))}</b></div>
          <div><small>Unit</small><b>{html.escape(str(active_benchmark.get('time_unit') or 'Relative'))}</b></div>
          <div><small>Landing</small><b>{html.escape(benchmark_horizon)}</b></div>
        </div>
        """
    return f"""
    <div class="timeline-time-readout">
      <div><small>Position</small><b>s={parameter:.2f}</b></div>
      <div><small>Relative</small><b>{html.escape(_time_language_label(parameter))}</b></div>
      <div><small>Date</small><b>{value_date.strftime('%d %b %Y')}</b></div>
    </div>
    """


def _request_uncertainty() -> None:
    st.session_state[_widget_key("pending_type")] = None
    st.session_state[_widget_key("editing_id")] = None
    st.session_state[_widget_key("pending_uncertainty")] = True
    st.session_state[_widget_key("placement_reset")] = {
        "uncertainty_interval": (0.30, 0.54),
        "uncertainty_strength": "Marked",
        "uncertainty_profile_mode": "Balanced",
    }


def _render_move_row(
    event_type_keys: tuple[str, ...],
    pending_type: object,
) -> None:
    columns = st.columns(len(event_type_keys), gap="small")
    for column, event_type in zip(columns, event_type_keys):
        definition = EVENT_TYPES[event_type]
        with column:
            if st.button(
                str(definition["label"]),
                key=f"timeline_move_{event_type}",
                type=(
                    "primary"
                    if str(pending_type or "") == event_type
                    else "secondary"
                ),
                width="stretch",
            ):
                _request_placement(event_type)
                st.rerun()


def _render_camera_persistence_hook(revision: str) -> None:
    """Persist Plotly's camera locally across Streamlit chart rebuilds."""

    components.html(
        f"""
        <script>
        (() => {{
          const storageKey = {CAMERA_STORAGE_KEY!r};
          const chartRevision = {revision!r};
          let attempts = 0;

          const attach = () => {{
            attempts += 1;
            let host = window;
            try {{
              if (window.parent && window.parent.document) host = window.parent;
            }} catch (_error) {{
              host = window;
            }}

            const plot = host.document.querySelector(
              '[data-testid="stPlotlyChart"] .js-plotly-plot'
            );
            if ((!plot || typeof plot.on !== "function") && attempts < 40) {{
              window.setTimeout(attach, 100);
              return;
            }}
            if (!plot) return;
            if (plot.dataset.timelineCameraHook) return;
            plot.dataset.timelineCameraHook = "pending";

            const saved = host.sessionStorage.getItem(storageKey);
            plot.dataset.timelineCameraFound = saved ? "1" : "0";

            const restoreCamera = () => {{
              if (saved) {{
                try {{
                  const camera = JSON.parse(saved);
                  const scene = plot._fullLayout?.scene?._scene;
                  plot.dataset.timelineCameraScene = scene ? "1" : "0";
                  if (scene?.camera && typeof scene.camera.lookAt === "function") {{
                    plot.layout.scene.camera = camera;
                    plot._fullLayout.scene.camera = camera;
                    scene.fullSceneLayout.camera = camera;
                    scene.camera.lookAt(
                      [camera.eye.x, camera.eye.y, camera.eye.z],
                      [camera.center.x, camera.center.y, camera.center.z],
                      [camera.up.x, camera.up.y, camera.up.z]
                    );
                    scene.render();
                    plot.dataset.timelineCameraRestored = "1";
                  }}
                }} catch (_error) {{
                  host.sessionStorage.removeItem(storageKey);
                }}
              }}
            }};

            restoreCamera();
            window.setTimeout(restoreCamera, 700);
            plot.dataset.timelineCameraHook = "1";
            plot.on("plotly_relayout", (update) => {{
              const scene = plot._fullLayout?.scene?._scene;
              let camera = scene && typeof scene.getCamera === "function"
                ? scene.getCamera()
                : update && update["scene.camera"];
              if (camera) {{
                host.sessionStorage.setItem(storageKey, JSON.stringify(camera));
                plot.dataset.timelineCameraSaved = "1";
              }}
            }});
          }};

          window.setTimeout(attach, 0);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _filename_for_plan(plan: dict[str, object]) -> str:
    title = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(plan.get("title") or "trajectory-plan")
    )
    return f"{'-'.join(part for part in title.split('-') if part) or 'trajectory-plan'}.yaml"


def _mark_exported() -> None:
    st.session_state[_widget_key("save_status")] = "Exported"


def _render_local_autosave(document: dict[str, object]) -> None:
    """Keep the current editable draft on this device after every rerun."""

    document_json = json.dumps(document, ensure_ascii=False)
    plan_id = str(document["plan"].get("id") or "draft")
    components.html(
        f"""
        <script>
        (() => {{
          const document = {document_json};
          const cameraRaw = window.parent.sessionStorage.getItem(
            {CAMERA_STORAGE_KEY!r}
          );
          if (cameraRaw) {{
            try {{ document.view.camera = JSON.parse(cameraRaw); }}
            catch (_error) {{ /* keep the schema default */ }}
          }}
          document.saved_at = new Date().toISOString();
          const encoded = JSON.stringify(document);
          window.parent.localStorage.setItem(
            {LOCAL_STORAGE_PREFIX!r} + {plan_id!r}, encoded
          );
          window.parent.localStorage.setItem(
            {LOCAL_STORAGE_LATEST_KEY!r}, encoded
          );
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _restore_imported_camera(camera: dict[str, object]) -> None:
    components.html(
        f"""
        <script>
        window.parent.sessionStorage.setItem(
          {CAMERA_STORAGE_KEY!r}, {json.dumps(camera)!r}
        );
        </script>
        """,
        height=0,
        width=0,
    )


def _start_another_plan() -> None:
    for key in tuple(st.session_state):
        if str(key).startswith(STATE_PREFIX):
            del st.session_state[key]
    st.session_state.pop(ACTIVE_BENCHMARK_KEY, None)
    st.session_state["sketch_plan_stage"] = "entrance"
    st.switch_page("views/test_sketch_plan.py")


def _edit_plan_stage(stage: str) -> None:
    """Re-enter onboarding without discarding the trajectory vocabulary."""

    field_map = {
        "title": "title",
        "description": "description",
        "initial_condition": "initial_condition",
        "goal_statement": "goal_statement",
        "goal_conditions": "goal_conditions",
        "landing_mode": "landing_mode",
        "guided_horizon": "guided_horizon",
        "guided_value": "guided_value",
        "guided_unit": "guided_unit",
        "fixed_kind": "fixed_kind",
        "fixed_value": "fixed_value",
        "fixed_unit": "fixed_unit",
        "fixed_date": "fixed_date",
        "temporal_mode": "temporal_mode",
        "linear_unit": "linear_unit",
    }
    for source, target in field_map.items():
        value = active_benchmark.get(source)
        if value is not None:
            if source == "landing_mode":
                value = {
                    "open": "Open",
                    "guided": "Guided",
                    "planned": "Fixed",
                }.get(str(value).lower(), str(value).title())
            elif source == "temporal_mode":
                value = str(value).title()
            st.session_state[f"sketch_plan_value_{target}"] = value
    st.session_state["sketch_plan_created_at"] = str(
        active_benchmark.get("created_at") or ""
    )
    st.session_state["sketch_plan_plan_id"] = str(
        active_benchmark.get("id") or uuid4().hex
    )
    st.session_state["sketch_plan_stage"] = stage
    st.session_state["sketch_plan_preserve_trajectory"] = True
    st.switch_page("views/test_sketch_plan.py")


def _discard_local_plan(plan_id: str) -> None:
    components.html(
        f"""
        <a id="discard-plan" href="/test-sketch-plan" target="_blank" rel="noopener">Discard this draft ↗</a>
        <script>
        document.getElementById("discard-plan").addEventListener("click", () => {{
          window.parent.localStorage.removeItem({LOCAL_STORAGE_PREFIX!r} + {plan_id!r});
          window.parent.localStorage.removeItem({LOCAL_STORAGE_LATEST_KEY!r});
        }});
        </script>
        <style>
        html,body {{ margin:0; background:transparent; font-family:"IBM Plex Mono",monospace; }}
        a {{
          box-sizing:border-box; display:flex; align-items:center; justify-content:center;
          width:100%; min-height:42px; border-radius:999px; text-decoration:none;
          background:#211f16; color:#f0eee5; border:1px solid #4e4b38;
        }}
        a:hover {{ background:#2a2719; border-color:#89815a; }}
        a:active {{ transform:scale(.98); }}
        </style>
        """,
        height=46,
    )


@st.dialog("Start another plan?")
def _confirm_start_another(
    document: dict[str, object],
    yaml_text: str,
) -> None:
    st.write(
        "Your current trajectory is autosaved on this device. Choose what "
        "should happen before opening a blank plan."
    )
    if st.button("Save and continue", width="stretch", type="primary"):
        _start_another_plan()
    exported = st.download_button(
        "Export YAML and continue",
        data=yaml_text,
        file_name=_filename_for_plan(dict(document["plan"])),
        mime="application/yaml",
        width="stretch",
    )
    if exported:
        _start_another_plan()
    _discard_local_plan(str(document["plan"].get("id") or "draft"))
    if st.button("Cancel", width="stretch"):
        st.rerun()


def _add_uncertainty_chunk(
    figure: go.Figure,
    x: list[float],
    y: list[float],
    z: list[float],
    chunk: dict[str, object],
    *,
    preview: bool = False,
) -> None:
    """Render one local isotropic envelope beneath the crisp centreline."""

    color = "#dfe875" if preview else "#8fc9c0"
    base_opacity = float(chunk["opacity"])
    shells = (
        (0.38, base_opacity * 0.86),
        (0.70, base_opacity * 0.58),
        (1.00, base_opacity * 0.36),
    )
    for radius_fraction, opacity in shells:
        mesh = uncertainty_tube_mesh(
            x,
            y,
            z,
            chunk,
            radial_fraction=radius_fraction,
            directions=14,
        )
        if mesh["x"]:
            figure.add_trace(
                go.Mesh3d(
                    x=mesh["x"],
                    y=mesh["y"],
                    z=mesh["z"],
                    i=mesh["i"],
                    j=mesh["j"],
                    k=mesh["k"],
                    color=color,
                    opacity=opacity,
                    hoverinfo="skip",
                    showlegend=False,
                    flatshading=False,
                )
            )

    center = float(chunk["center_parameter"])
    center_point = trajectory_point(
        center,
        chunk.get("_events", []),
        landing_mode=str(chunk.get("_landing_mode") or "open"),
    )
    if preview:
        figure.add_trace(
            go.Scatter3d(
                x=[center_point[0]],
                y=[center_point[1]],
                z=[center_point[2]],
                mode="markers+text",
                marker={
                    "size": 9,
                    "symbol": "circle-open",
                    "color": color,
                    "line": {"color": color, "width": 2},
                },
                text=["UNCERTAINTY PREVIEW"],
                textposition="top center",
                textfont={"color": color, "size": 9},
                hoverinfo="skip",
                showlegend=False,
            )
        )


def _build_figure(
    events: list[dict[str, object]],
    uncertainties: list[dict[str, object]],
    *,
    show_collective: bool,
    landing_mode: str,
    preview_parameter: float | None,
    preview_type: str | None,
    uncertainty_preview: dict[str, object] | None,
    bounds: dict[str, list[float]],
) -> go.Figure:
    placed = active_events(events)
    x, y, z = sample_trajectory(
        events,
        landing_mode=landing_mode,
        samples_per_segment=72,
    )
    branch_stems = binary_branch_stems(
        events,
        landing_mode=landing_mode,
    )
    figure = go.Figure()

    if show_collective:
        ghost_styles = (
            (0.085, -0.020, "#538d88"),
            (-0.070, 0.030, "#705f8f"),
            (0.135, 0.050, "#7d7450"),
            (-0.115, -0.040, "#4d687c"),
        )
        for index, (lateral, vertical, color) in enumerate(ghost_styles):
            phase = (index + 1) * 0.42
            ghost_y = [
                value + lateral + (0.024 * sin(6 * point + phase))
                for point, value in zip(x, y)
            ]
            ghost_z = [
                value + vertical + (0.014 * cos(5 * point + phase))
                for point, value in zip(x, z)
            ]
            figure.add_trace(
                go.Scatter3d(
                    x=x,
                    y=ghost_y,
                    z=ghost_z,
                    mode="lines",
                    line={"color": color, "width": 3},
                    opacity=0.28,
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    for chunk in uncertainties:
        render_chunk = {
            **chunk,
            "_events": events,
            "_landing_mode": landing_mode,
        }
        _add_uncertainty_chunk(
            figure,
            x,
            y,
            z,
            render_chunk,
        )

    if uncertainty_preview is not None:
        render_preview = {
            **uncertainty_preview,
            "_events": events,
            "_landing_mode": landing_mode,
        }
        _add_uncertainty_chunk(
            figure,
            x,
            y,
            z,
            render_preview,
            preview=True,
        )

    centreline_x, centreline_y, centreline_z = x, y, z
    if branch_stems:
        branch_start = float(branch_stems[0]["x"][0])
        incoming = [
            index
            for index, parameter in enumerate(x)
            if float(parameter) <= branch_start + 1e-9
        ]
        centreline_x = [x[index] for index in incoming]
        centreline_y = [y[index] for index in incoming]
        centreline_z = [z[index] for index in incoming]

    figure.add_trace(
        go.Scatter3d(
            x=centreline_x,
            y=centreline_y,
            z=centreline_z,
            mode="lines",
            line={"color": "#ecf7ef", "width": 8},
            hoverinfo="skip",
            showlegend=False,
            name="Personal trajectory",
        )
    )

    for index, stem in enumerate(branch_stems):
        branch_color = ("#80d6c3", "#d6a8ff")[index]
        figure.add_trace(
            go.Scatter3d(
                x=stem["x"],
                y=stem["y"],
                z=stem["z"],
                mode="lines+text",
                line={"color": branch_color, "width": 7},
                text=[""] * (len(stem["x"]) - 1) + [str(stem["label"])],
                textposition="top center",
                textfont={"color": branch_color, "size": 11},
                hovertemplate=(
                    f"<b>{html.escape(str(stem['label']))}</b>"
                    "<br>Branch future<extra></extra>"
                ),
                showlegend=False,
                name=str(stem["label"]),
            )
        )

    now_point = trajectory_point(0.0, events, landing_mode=landing_mode)
    figure.add_trace(
        go.Scatter3d(
            x=[now_point[0]],
            y=[now_point[1]],
            z=[now_point[2]],
            mode="markers+text",
            marker={
                "size": 7,
                "color": "#ecf7ef",
                "line": {"color": "#07100f", "width": 2},
            },
            text=["NOW"],
            textposition="bottom center",
            textfont={"color": "#b8c7c2", "size": 11},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    landing_labels = {
        "open": "OPEN LANDING",
        "guided": "GUIDED LANDING",
        "planned": "PLANNED LANDING",
    }
    landing_text = (
        destination_label.upper()
        if destination_label
        else landing_labels[landing_mode]
    )
    figure.add_trace(
        go.Scatter3d(
            x=[END_POINT[0]],
            y=[END_POINT[1]],
            z=[END_POINT[2]],
            mode="markers+text",
            marker={
                "size": 8,
                "symbol": "diamond-open",
                "color": "#8fa39c",
                "line": {"color": "#8fa39c", "width": 2},
            },
            text=[landing_text],
            textposition="top center",
            textfont={"color": "#71827d", "size": 10},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    if placed:
        event_x, event_y, event_z = event_points(events)
        figure.add_trace(
            go.Scatter3d(
                x=event_x,
                y=event_y,
                z=event_z,
                mode="markers+text",
                marker={
                    "size": [
                        9
                        if directional_mode(event) == "abruptly"
                        or topology_mode(event) == "branching"
                        else 6
                        for event in placed
                    ],
                    "color": [
                        EVENT_TYPES[str(event["type"])]["color"]
                        for event in placed
                    ],
                    "opacity": 0.72,
                },
                text=[primitive_plot_label(event) for event in placed],
                textposition=[
                    "top center" if index % 2 == 0 else "bottom center"
                    for index, _ in enumerate(placed)
                ],
                textfont={
                    "color": [
                        EVENT_TYPES[str(event["type"])]["color"]
                        for event in placed
                    ],
                    "size": 13,
                },
                customdata=[
                    [
                        html.escape(str(event["title"])),
                        EVENT_TYPES[str(event["type"])]["label"],
                        f"{float(event['time_parameter']):.2f}",
                        date.fromisoformat(str(event["date_value"])).strftime(
                            "%d %b %Y"
                        ),
                        INFLUENCE_COPY[_event_influence(event)],
                        directional_mode(event).title(),
                        topology_mode(event).title(),
                    ]
                    for event in placed
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]} · s=%{customdata[2]} / %{customdata[3]}"
                    "<br>Journey effect: %{customdata[4]}"
                    "<br>Direction: %{customdata[5]}"
                    "<br>Topology: %{customdata[6]}<extra></extra>"
                ),
                showlegend=False,
                name="Placed events",
            )
        )

    for before, node, after in kink_indicators(
        events,
        landing_mode=landing_mode,
    ):
        figure.add_trace(
            go.Scatter3d(
                x=[before[0], node[0], after[0]],
                y=[before[1], node[1], after[1]],
                z=[before[2], node[2], after[2]],
                mode="lines",
                line={"color": "#ffb37b", "width": 5},
                opacity=0.92,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    if preview_parameter is not None and preview_type is not None:
        preview = trajectory_point(
            preview_parameter,
            events,
            landing_mode=landing_mode,
        )
        preview_definition = EVENT_TYPES[preview_type]
        preview_date = date_for_parameter(
            preview_parameter,
            start_date=ROADMAP_START,
            end_date=ROADMAP_END,
        )
        figure.add_trace(
            go.Scatter3d(
                x=[preview[0]],
                y=[preview[1]],
                z=[preview[2]],
                mode="markers+text",
                marker={
                    "size": 11,
                    "symbol": "circle-open",
                    "color": preview_definition["color"],
                    "line": {
                        "color": preview_definition["color"],
                        "width": 3,
                    },
                },
                text=["PREVIEW"],
                textposition="top center",
                textfont={
                    "color": preview_definition["color"],
                    "size": 10,
                },
                customdata=[
                    [
                        preview_definition["label"],
                        f"{preview_parameter:.2f}",
                        preview_date.strftime("%d %b %Y"),
                    ]
                ],
                hovertemplate=(
                    "<b>Preview · %{customdata[0]}</b><br>"
                    "s=%{customdata[1]} / %{customdata[2]}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    if temporal_mode == "qualitative":
        tick_values = [value for _, value in QUALITATIVE_TIME_ANCHORS]
        tick_text = [
            label.upper() for label, _ in QUALITATIVE_TIME_ANCHORS
        ]
    else:
        linear_ticks = linear_time_ticks(
            start_date=ROADMAP_START,
            end_date=ROADMAP_END,
            unit=str(active_benchmark.get("time_unit") or "Days"),
        )
        tick_values = [position for position, _ in linear_ticks]
        tick_text = [label for _, label in linear_ticks]
    figure.update_layout(
        height=620,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        paper_bgcolor="#020707",
        plot_bgcolor="#020707",
        hoverlabel={
            "bgcolor": "#081210",
            "bordercolor": "#607b73",
            "font": {"color": "#f3f1e5", "family": "IBM Plex Mono"},
        },
        transition={"duration": 360, "easing": "cubic-in-out"},
        scene={
            "bgcolor": "#020707",
            "camera": DEFAULT_CAMERA,
            "uirevision": "timeline-camera-v2",
            "aspectmode": "manual",
            "aspectratio": {"x": 2.35, "y": 0.66, "z": 1.0},
            "xaxis": {
                "title": {
                    "text": (
                        "HORIZON"
                        if temporal_mode == "qualitative"
                        else "TIME"
                    ),
                    "font": {"color": "#c2d0cb", "size": 14},
                },
                "range": [0, 1],
                "tickvals": tick_values,
                "ticktext": tick_text,
                "gridcolor": "#13201d",
                "linecolor": "#43534e",
                "zerolinecolor": "#43534e",
                "tickfont": {"color": "#9aaca5", "size": 12},
                "showbackground": False,
                "showspikes": False,
            },
            "yaxis": {
                "title": {
                    "text": axis_y_label.upper(),
                    "font": {"color": "#c2d0cb", "size": 14},
                },
                "range": bounds["y"],
                "nticks": 4,
                "gridcolor": "#13201d",
                "linecolor": "#43534e",
                "zerolinecolor": "#43534e",
                "showticklabels": False,
                "showbackground": False,
                "showspikes": False,
            },
            "zaxis": {
                "title": {
                    "text": "ENERGY",
                    "font": {"color": "#c2d0cb", "size": 14},
                },
                "range": bounds["z"],
                "nticks": 4,
                "gridcolor": "#13201d",
                "linecolor": "#43534e",
                "zerolinecolor": "#43534e",
                "showticklabels": False,
                "showbackground": False,
                "showspikes": False,
            },
        },
        uirevision="timeline-camera-v2",
    )
    return figure


def _apply_style_lab_figure(
    figure: go.Figure,
    variant: str,
) -> go.Figure:
    """Change only the presentation of the shared trajectory figure."""

    presets: dict[str, dict[str, object]] = {
        "Instrument": {
            "height": 660,
            "background": "#020807",
            "grid": "#182722",
            "line": "#41534d",
            "axis": "#a9b9b3",
            "ticks": "#667b74",
            "trajectory_width": 9,
            "show_grid": True,
        },
        "Playground": {
            "height": 700,
            "background": "#06100e",
            "grid": "#14241f",
            "line": "#263b34",
            "axis": "#9cafa8",
            "ticks": "#63766f",
            "trajectory_width": 12,
            "show_grid": True,
        },
        "Gallery": {
            "height": 735,
            "background": "#040706",
            "grid": "rgba(255,255,255,0)",
            "line": "rgba(255,255,255,0.06)",
            "axis": "#75847f",
            "ticks": "#53615c",
            "trajectory_width": 11,
            "show_grid": False,
        },
    }
    preset = presets[variant]
    background = str(preset["background"])
    grid = str(preset["grid"])
    line = str(preset["line"])
    axis = str(preset["axis"])
    ticks = str(preset["ticks"])
    show_grid = bool(preset["show_grid"])

    for trace in figure.data:
        if getattr(trace, "name", None) == "Personal trajectory":
            trace.line.width = int(preset["trajectory_width"])

    figure.update_layout(
        height=int(preset["height"]),
        paper_bgcolor=background,
        plot_bgcolor=background,
        hoverlabel={
            "bgcolor": "#101a17",
            "bordercolor": "#526b62",
            "font": {"color": "#f6f7ef", "family": "IBM Plex Mono"},
        },
    )
    figure.update_scenes(
        bgcolor=background,
        xaxis={
            "gridcolor": grid,
            "linecolor": line,
            "zerolinecolor": line,
            "showgrid": show_grid,
            "title": {
                "text": (
                    "HORIZON"
                    if temporal_mode == "qualitative"
                    else "TIME"
                ),
                "font": {"color": axis},
            },
            "tickfont": {"color": ticks, "size": 10},
        },
        yaxis={
            "gridcolor": grid,
            "linecolor": line,
            "zerolinecolor": line,
            "showgrid": show_grid,
            "title": {"text": axis_y_label.upper(), "font": {"color": axis}},
        },
        zaxis={
            "gridcolor": grid,
            "linecolor": line,
            "zerolinecolor": line,
            "showgrid": show_grid,
            "title": {"text": "ENERGY", "font": {"color": axis}},
        },
    )
    return figure


def _apply_timeline_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        :root {
          --type-hero:clamp(42px,5.2vw,72px);
          --type-page-title:clamp(32px,3.5vw,48px);
          --type-section:clamp(24px,2.2vw,32px);
          --type-control:20px;
          --type-button:17px;
          --type-body:clamp(15px,1.1vw,17px);
          --type-helper:14px;
          --type-option:13px;
          --type-meta:12px;
          --timeline-action:#c7d66d;
          --timeline-action-hover:#d4e47b;
          --timeline-action-text:#11160e;
          --timeline-control:#07110f;
          --timeline-control-hover:#0d1a16;
        }
        .stApp {
          background:
            radial-gradient(circle at 70% 0%, rgba(77,127,116,.10), transparent 30rem),
            #020707;
          color:#e8eee9;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none; }
        .block-container { max-width:1500px; padding:1.2rem 1.6rem 3rem; }
        html, body, [class*="st-"], button, input, textarea {
          font-family:"IBM Plex Mono", monospace !important;
        }
        h1, h2, h3, p, label, .stCaption { color:#e8eee9 !important; }
        [data-testid="stSidebar"] {
          background:#030807; border-right:1px solid #21302c;
        }
        [data-testid="stIconMaterial"] {
          font-family:"Material Symbols Rounded" !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
          padding-bottom:2rem;
        }
        .timeline-hud {
          display:grid; grid-template-columns:minmax(16rem, 1fr) repeat(4, auto);
          gap:1.5rem; align-items:end; padding:.35rem 0 1rem;
          border-bottom:1px solid #273632;
        }
        .timeline-hud small, .timeline-readout small {
          display:block; color:#71827d; font-size:.68rem; letter-spacing:.12em;
          text-transform:uppercase; margin-bottom:.32rem;
        }
        .timeline-hud strong { font-size:1rem; letter-spacing:.02em; }
        .timeline-hud b { color:#dfe875; font-size:.85rem; font-weight:500; }
        .timeline-readout { min-width:8rem; text-align:right; }
        .timeline-plan-mode {
          min-height:3.3rem; display:flex; flex-direction:column;
          justify-content:center; align-items:flex-end; padding:.45rem .7rem;
          border:1px solid #30443d; background:#06100e;
        }
        .timeline-plan-mode small {
          color:#71827d; font-size:.58rem; letter-spacing:.12em;
          text-transform:uppercase;
        }
        .timeline-plan-mode b {
          color:#dfe875; font-size:.72rem; font-weight:500;
          letter-spacing:.06em;
        }
        .timeline-field-note {
          display:flex; justify-content:space-between; gap:1rem; color:#71827d;
          font-size:.68rem; letter-spacing:.08em; text-transform:uppercase;
          margin:.6rem 0 -.25rem;
        }
        .timeline-journey-steps {
          display:grid; grid-template-columns:repeat(8,1fr); gap:.32rem;
          margin:.8rem 0 .55rem;
        }
        .timeline-journey-step {
          display:flex; align-items:center; gap:.42rem; min-width:0;
          padding:.48rem .5rem; border-bottom:2px solid #263732;
          color:#60716b; font-size:.58rem; letter-spacing:.025em;
        }
        .timeline-journey-step b { font-size:.72rem; font-weight:500; }
        .timeline-journey-step.done { color:#8ea39b; border-color:#45655a; }
        .timeline-journey-step.done b { color:#78d6a7; }
        .timeline-journey-step.current {
          color:#edf2ed; border-color:#dfe875; background:#07110f;
        }
        .timeline-journey-step.current b { color:#dfe875; }
        .timeline-first-instruction {
          display:flex; align-items:center; justify-content:space-between;
          gap:1rem; margin:.7rem 0 .35rem; padding:.72rem .85rem;
          border-left:2px solid #dfe875; background:#07110f;
        }
        .timeline-first-instruction b {
          color:#edf2ed; font-size:.76rem; font-weight:500;
        }
        .timeline-first-instruction span { color:#82958e; font-size:.65rem; }
        [data-testid="stPlotlyChart"] {
          border:1px solid #1d2b27; border-radius:8px; overflow:hidden;
          box-shadow:0 0 60px rgba(80,138,124,.07);
        }
        .timeline-dock-label, .timeline-sidebar-kicker {
          color:#71827d; font-size:.68rem; letter-spacing:.12em;
          text-transform:uppercase; margin:.7rem 0 .55rem;
        }
        .timeline-sidebar-head {
          border-top:1px solid #293a35; margin-top:.35rem; padding-top:1rem;
        }
        .timeline-experimental-badge {
          display:inline-block; color:#10150f; background:#dfe875;
          padding:.2rem .4rem; font-size:.62rem; letter-spacing:.08em;
          text-transform:uppercase; margin-bottom:.65rem;
        }
        .timeline-sidebar-head h3 {
          font-size:1rem !important; margin:0 0 .35rem !important;
          letter-spacing:0 !important;
        }
        .timeline-sidebar-head p {
          color:#84958f !important; font-size:.72rem; line-height:1.55;
        }
        .timeline-time-readout {
          display:grid; grid-template-columns:repeat(3,1fr); gap:.35rem;
          margin:.15rem 0 .75rem;
        }
        .timeline-time-readout div {
          border:1px solid #283934; background:#06100e; padding:.45rem;
          min-width:0;
        }
        .timeline-time-readout small {
          display:block; color:#687a74; font-size:.56rem; letter-spacing:.08em;
          text-transform:uppercase; margin-bottom:.2rem;
        }
        .timeline-time-readout b {
          color:#dce7e1; display:block; font-size:.67rem; font-weight:500;
          overflow-wrap:anywhere;
        }
        .timeline-save-state, .timeline-integration-card {
          display:flex; flex-direction:column; gap:.28rem;
          border:1px solid #3c574e; background:#07110f;
          padding:.8rem .9rem; border-radius:8px;
        }
        .timeline-save-state b, .timeline-integration-card b {
          color:#8ee0b3; font-size:.78rem; font-weight:500;
        }
        .timeline-save-state span, .timeline-integration-card span {
          color:#a0b0aa; font-size:.72rem; line-height:1.5;
        }
        .timeline-integration-card { margin:.85rem 0; border-color:#60766f; }
        .timeline-integration-card b { color:#dfe875; font-size:.9rem; }
        .st-key-timeline_rail {
          min-height:0; background:transparent; border-top:1px solid #2d403a;
          border-radius:0; padding:1rem .15rem 2rem;
        }
        .st-key-timeline_rail [data-testid="stVerticalBlock"] { gap:.8rem; }
        .timeline-confirmation {
          position:fixed; top:5.4rem; right:2rem; z-index:1000;
          background:#07110f; border:1px solid #60766f; border-radius:6px;
          padding:.7rem .85rem; min-width:15rem;
          box-shadow:0 12px 34px rgba(0,0,0,.35);
          animation:timeline-confirmation-out 3s ease forwards;
        }
        .timeline-confirmation b {
          display:block; color:#edf3ef; font-size:.75rem; margin-bottom:.18rem;
        }
        .timeline-confirmation span { color:#8fa19a; font-size:.66rem; }
        @keyframes timeline-confirmation-out {
          0%,72% { opacity:1; transform:translateY(0); }
          100% { opacity:0; transform:translateY(-7px); visibility:hidden; }
        }
        [class*="st-key-timeline_move_"] button {
          min-height:4.4rem !important; border:1px solid #3a4d47 !important;
          border-radius:8px !important; background:#06100e !important;
          color:#eef2e8 !important; box-shadow:none !important; font-size:.85rem !important;
          letter-spacing:.02em; text-transform:none;
        }
        [class*="st-key-timeline_move_"] button:hover {
          border-color:#dfe875 !important; color:#dfe875 !important;
          transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,.25) !important;
        }
        [class*="st-key-timeline_move_"] button:active {
          transform:translateY(1px) scale(.97) !important;
          transition-duration:70ms !important;
        }
        [class*="st-key-timeline_move_"] button[data-testid="stBaseButton-primary"] {
          border-color:#dfe875 !important; color:#f5f7c8 !important;
          background:#101b16 !important;
          box-shadow:
            0 0 0 2px rgba(223,232,117,.22),
            0 10px 28px rgba(0,0,0,.28) !important;
        }
        .stButton button,
        [data-testid="stDownloadButton"] button {
          min-height:52px;
          font-size:var(--type-button) !important;
          background:var(--timeline-control) !important;
          color:#dce7e1 !important;
          border:1px solid #40554d !important;
          box-shadow:none !important;
        }
        .stButton button:not(:disabled):hover,
        [data-testid="stDownloadButton"] button:not(:disabled):hover {
          background:var(--timeline-control-hover) !important;
          border-color:#82978f !important;
          color:#f1f5ef !important;
        }
        .stButton button[data-testid="stBaseButton-primary"] {
          background:var(--timeline-action) !important;
          color:var(--timeline-action-text) !important;
          border-color:var(--timeline-action) !important;
        }
        .stButton button[data-testid="stBaseButton-primary"]:hover {
          background:var(--timeline-action-hover) !important;
          color:var(--timeline-action-text) !important;
        }
        .stButton button:disabled,
        [data-testid="stDownloadButton"] button:disabled {
          opacity:1 !important;
          background:#141a17 !important;
          color:#77837d !important;
          border:1px dashed #4e5a54 !important;
          cursor:not-allowed !important;
        }
        button p,
        [data-testid="stDownloadButton"] button p,
        .stButton button[data-testid="stBaseButton-primary"] p {
          color:inherit !important;
        }
        .stButton button[data-testid="stBaseButton-primary"] p,
        .st-key-timeline_anchor_uncertainty button p,
        button[data-testid="stBaseButton-pillsActive"] p,
        button[data-testid="stBaseButton-segmented_controlActive"] p,
        [data-testid="stFormSubmitButton"] button p {
          color:var(--timeline-action-text) !important;
          -webkit-text-fill-color:var(--timeline-action-text) !important;
          text-shadow:none !important;
        }
        .st-key-timeline_add_uncertainty button {
          min-height:3rem !important; border:1px dashed #668178 !important;
          border-radius:7px !important; background:#06100e !important;
          color:#a8c8bf !important; box-shadow:none !important;
        }
        .st-key-timeline_add_uncertainty button:hover {
          border-color:#dfe875 !important; color:#dfe875 !important;
        }
        .st-key-timeline_anchor_uncertainty button {
          min-height:3rem !important; border:0 !important;
          border-radius:6px !important; background:var(--timeline-action) !important;
          color:var(--timeline-action-text) !important; box-shadow:none !important;
        }
        .st-key-timeline_anchor_uncertainty button p {
          color:var(--timeline-action-text) !important;
          -webkit-text-fill-color:var(--timeline-action-text) !important;
        }
        .st-key-timeline_choose_benchmark button,
        [class*="st-key-timeline_suggested_move_"] button {
          min-height:2.7rem !important; border:1px solid #30423d !important;
          border-radius:6px !important; background:#06100e !important;
          color:#a8b9b3 !important; box-shadow:none !important;
          transition:transform 100ms ease, border-color 140ms ease,
            color 140ms ease !important;
        }
        .st-key-timeline_choose_benchmark button:hover,
        [class*="st-key-timeline_suggested_move_"] button:hover {
          border-color:#82978f !important; color:#edf2ed !important;
          transform:translateY(-1px);
        }
        .st-key-timeline_choose_benchmark button:active,
        [class*="st-key-timeline_suggested_move_"] button:active {
          transform:scale(.97) !important; transition-duration:70ms !important;
        }
        .st-key-timeline_cancel_uncertainty button,
        .st-key-timeline_remove_uncertainty button {
          min-height:2.6rem !important; border:1px solid #30423d !important;
          border-radius:6px !important; background:transparent !important;
          color:#91a39d !important; box-shadow:none !important;
        }
        [class*="st-key-timeline_utility_"] button {
          min-height:2.6rem !important; border:1px solid #30423d !important;
          border-radius:6px !important; background:transparent !important;
          color:#91a39d !important; box-shadow:none !important;
        }
        [class*="st-key-timeline_move_"] button:not(:disabled) {
          cursor:pointer !important;
        }
        [class*="st-key-timeline_utility_"] button:disabled,
        .st-key-timeline_remove_uncertainty button:disabled {
          opacity:1 !important; cursor:not-allowed !important;
          color:#727d77 !important; background:#141a17 !important;
          border:1px dashed #4e5a54 !important; filter:saturate(.25);
        }
        [class*="st-key-timeline_utility_"] button:not(:disabled):hover {
          color:#eef2e8 !important; background:#0a1512 !important;
          transform:translateY(-1px);
        }
        [class*="st-key-timeline_utility_"] button:not(:disabled):active,
        .st-key-timeline_add_uncertainty button:active,
        .st-key-timeline_anchor_uncertainty button:active,
        [data-testid="stFormSubmitButton"] button:active {
          transform:scale(.97) !important; transition-duration:70ms !important;
        }
        [class*="st-key-timeline_utility_integrate"] button:not(:disabled) {
          border-color:#dfe875 !important; color:#dfe875 !important;
        }
        .timeline-progress {
          color:#92a29c; font-size:.72rem; text-align:right; margin-top:.35rem;
        }
        .timeline-progress b { color:#aebdb7; font-weight:500; }
        [data-testid="stWidgetLabel"] p {
          color:#aebdb7 !important; font-size:var(--type-control) !important;
          line-height:1.3; font-weight:600; letter-spacing:0;
          text-transform:none;
        }
        [data-testid="stCaptionContainer"] p, .stCaption {
          font-size:var(--type-helper) !important; line-height:1.45 !important;
          color:#91a39d !important;
        }
        [data-testid="stExpander"] {
          border-color:#344740 !important; background:#040b09 !important;
          border-radius:10px !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary svg {
          background:#040b09 !important; color:#dce7e1 !important;
          -webkit-text-fill-color:#dce7e1 !important;
        }
        [data-testid="stExpander"] summary:hover {
          background:#0a1512 !important;
        }
        div[data-baseweb="input"] > div, [data-baseweb="select"] > div,
        textarea {
          background:#020807 !important; border-color:#344640 !important;
          color:#edf1e8 !important;
        }
        input, textarea { color:#edf1e8 !important; caret-color:#dfe875 !important; }
        input, textarea, [data-baseweb="select"] { font-size:16px !important; }
        input::placeholder, textarea::placeholder {
          color:#667770 !important; opacity:1;
        }
        [data-testid="stButtonGroup"] button {
          min-height:52px;
          font-size:var(--type-button) !important;
          background:#020807 !important; border-color:#344640 !important;
          color:#aab8b3 !important; border-radius:4px !important;
          transition:background 140ms ease, border-color 140ms ease,
            color 140ms ease, transform 100ms ease !important;
        }
        [data-testid="stButtonGroup"] button:hover {
          background:#0a1512 !important; border-color:#8da099 !important;
          color:#edf2ed !important; transform:translateY(-1px);
        }
        [data-testid="stButtonGroup"] button:active {
          transform:scale(.96) !important; transition-duration:70ms !important;
        }
        button[data-testid="stBaseButton-pillsActive"],
        button[data-testid="stBaseButton-segmented_controlActive"] {
          background:var(--timeline-action) !important;
          color:var(--timeline-action-text) !important;
          border-color:var(--timeline-action) !important;
          box-shadow:inset 0 -3px 0 rgba(17,22,14,.18),
            0 0 0 2px rgba(223,232,117,.12) !important;
        }
        button[data-testid="stBaseButton-pillsActive"] p,
        button[data-testid="stBaseButton-segmented_controlActive"] p {
          color:var(--timeline-action-text) !important;
          -webkit-text-fill-color:var(--timeline-action-text) !important;
        }
        [data-testid="stSlider"] [role="slider"] {
          background:#dfe875 !important; border-color:#dfe875 !important;
        }
        [data-testid="stFormSubmitButton"] button,
        .st-key-timeline_place_move button {
          min-height:3rem; width:100%; background:var(--timeline-action) !important;
          color:var(--timeline-action-text) !important; border:0 !important; border-radius:5px !important;
          box-shadow:none !important; text-transform:uppercase; letter-spacing:.08em;
          transition:transform 100ms ease, filter 140ms ease !important;
        }
        [data-testid="stFormSubmitButton"] button:hover,
        .st-key-timeline_place_move button:hover {
          filter:brightness(1.08); transform:translateY(-1px);
        }
        [data-testid="stFormSubmitButton"] button p,
        .st-key-timeline_place_move button p {
          color:var(--timeline-action-text) !important;
          -webkit-text-fill-color:var(--timeline-action-text) !important;
        }
        .timeline-inspector {
          border-left:2px solid #dfe875; padding:.15rem 0 .15rem 1rem;
          color:#95a69f; font-size:.76rem; line-height:1.7;
        }
        .timeline-inspector b { color:#edf1e8; }
        [data-testid="stAlert"] {
          background:#07110f; border:1px solid #425b54; color:#e8eee9;
        }
        @media(max-width:900px) {
          :root { --type-hero:48px; --type-body:clamp(15px,2vw,17px); }
          .block-container { padding:.8rem .8rem 2rem; }
          .timeline-hud { grid-template-columns:1fr 1fr; }
          .timeline-readout { text-align:left; min-width:0; }
          .timeline-confirmation { left:1rem; right:1rem; top:4rem; }
          [data-testid="stPlotlyChart"] { min-height:470px; }
          .timeline-journey-steps { grid-template-columns:repeat(4,1fr); }
          [data-testid="stWidgetLabel"] p { font-size:16px !important; }
          [data-testid="stCaptionContainer"] p, .stCaption { font-size:13px !important; }
          .stButton button, [data-testid="stDownloadButton"] button,
          [data-testid="stButtonGroup"] button { min-height:52px; font-size:16px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_main_graphic_move_theme() -> None:
    """Promote semantic move choices into large, tactile objects."""

    st.markdown(
        """
        <style>
        :root {
          --main-object-size:4.2rem;
          --main-object-label-size:.76rem;
        }
        [class*="st-key-timeline_move_"] button {
          min-height:7.3rem !important;
          border:0 !important;
          border-radius:30px !important;
          color:#f5f7ef !important;
          box-shadow:0 16px 0 rgba(0,0,0,.12),
            0 24px 52px rgba(0,0,0,.25) !important;
          transition:transform 150ms ease, box-shadow 150ms ease,
            filter 150ms ease, outline-color 150ms ease !important;
        }
        body .stApp [class*="st-key-timeline_move_"] button p {
          display:flex !important;
          flex-direction:column;
          align-items:center;
          justify-content:center;
          gap:.55rem;
          color:#e8eee9 !important;
          font-size:var(--main-object-label-size) !important;
          line-height:1.15 !important;
          letter-spacing:.06em;
          -webkit-text-fill-color:#e8eee9;
        }
        [class*="st-key-timeline_move_"] button p::before {
          display:block;
          font-size:var(--main-object-size);
          line-height:1;
          -webkit-text-fill-color:currentColor !important;
          filter:drop-shadow(0 7px 10px rgba(0,0,0,.16));
          transition:transform 150ms ease, filter 150ms ease;
        }
        [class*="st-key-timeline_move_"] button p::after {
          display:none !important;
          content:none !important;
        }
        [class*="st-key-timeline_move_"] button:hover {
          transform:translateY(-7px) scale(1.018);
          box-shadow:0 18px 0 rgba(0,0,0,.10),
            0 30px 64px rgba(0,0,0,.32) !important;
          filter:brightness(1.08);
        }
        [class*="st-key-timeline_move_"] button:hover p::before {
          filter:brightness(1.18)
            drop-shadow(0 0 18px color-mix(in srgb, currentColor 48%, transparent));
        }
        [class*="st-key-timeline_move_"] button:active {
          transform:translateY(2px) scale(.965) !important;
          transition-duration:70ms !important;
        }
        [class*="st-key-timeline_move_"] button[data-testid="stBaseButton-primary"] {
          outline:3px solid rgba(199,214,109,.75) !important;
          outline-offset:3px;
          filter:brightness(1.12);
        }

        body .stApp .st-key-timeline_move_release button {
          --main-object-background:linear-gradient(155deg,rgba(246,211,101,.23),#0c1612 70%);
          --main-object-accent:#f6d365;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_event button {
          --main-object-background:linear-gradient(155deg,rgba(128,214,195,.21),#0b1512 70%);
          --main-object-accent:#80d6c3;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_gateway button {
          --main-object-background:linear-gradient(155deg,rgba(214,168,255,.22),#111017 70%);
          --main-object-accent:#d6a8ff;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_action button {
          --main-object-background:linear-gradient(155deg,rgba(255,139,105,.22),#121411 70%);
          --main-object-accent:#ff8b69;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_update button {
          --main-object-background:linear-gradient(155deg,rgba(156,168,255,.22),#0e1315 70%);
          --main-object-accent:#9ca8ff;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_milestone button {
          --main-object-background:linear-gradient(155deg,rgba(232,242,124,.22),#101510 70%);
          --main-object-accent:#e8f27c;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_merge button {
          --main-object-background:linear-gradient(155deg,rgba(243,166,200,.22),#161015 70%);
          --main-object-accent:#f3a6c8;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_share_resources button {
          --main-object-background:linear-gradient(155deg,rgba(130,199,255,.22),#0c1419 70%);
          --main-object-accent:#82c7ff;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_acquire_resources button {
          --main-object-background:linear-gradient(155deg,rgba(123,214,166,.22),#0b1611 70%);
          --main-object-accent:#7bd6a6;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_delegate button {
          --main-object-background:linear-gradient(155deg,rgba(240,169,122,.22),#17120e 70%);
          --main-object-accent:#f0a97a;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_wait button {
          --main-object-background:linear-gradient(155deg,rgba(170,180,189,.18),#101414 70%);
          --main-object-accent:#aab4bd;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_prepare button {
          --main-object-background:linear-gradient(155deg,rgba(255,189,120,.22),#17130e 70%);
          --main-object-accent:#ffbd78;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_get_intelligence button {
          --main-object-background:linear-gradient(155deg,rgba(168,230,207,.22),#0d1613 70%);
          --main-object-accent:#a8e6cf;
          background:var(--main-object-background) !important;
        }
        body .stApp .st-key-timeline_move_synchronise button {
          --main-object-background:linear-gradient(155deg,rgba(200,182,255,.22),#121017 70%);
          --main-object-accent:#c8b6ff;
          background:var(--main-object-background) !important;
        }

        html body .stApp div[class*="st-key-timeline_move_"] .stButton
        button[data-testid="stBaseButton-primary"] {
          background:var(--main-object-background) !important;
          color:#e8eee9 !important;
        }
        html body .stApp div[class*="st-key-timeline_move_"] .stButton
        button[data-testid="stBaseButton-primary"] p {
          color:#e8eee9 !important;
          -webkit-text-fill-color:#e8eee9 !important;
        }
        html body .stApp div[class*="st-key-timeline_move_"] .stButton
        button[data-testid="stBaseButton-primary"] p::before {
          color:var(--main-object-accent) !important;
          -webkit-text-fill-color:var(--main-object-accent) !important;
        }

        body .stApp .st-key-timeline_move_release button p::before { content:"★" / ""; color:#f6d365; }
        body .stApp .st-key-timeline_move_event button p::before { content:"●" / ""; color:#80d6c3; }
        body .stApp .st-key-timeline_move_gateway button p::before { content:"◈" / ""; color:#d6a8ff; }
        body .stApp .st-key-timeline_move_action button p::before { content:"▲" / ""; color:#ff8b69; }
        body .stApp .st-key-timeline_move_update button p::before { content:"■" / ""; color:#9ca8ff; }
        body .stApp .st-key-timeline_move_milestone button p::before { content:"▼" / ""; color:#e8f27c; }
        body .stApp .st-key-timeline_move_merge button p::before { content:"⋈" / ""; color:#f3a6c8; }
        body .stApp .st-key-timeline_move_share_resources button p::before { content:"⇄" / ""; color:#82c7ff; }
        body .stApp .st-key-timeline_move_acquire_resources button p::before { content:"⇣" / ""; color:#7bd6a6; }
        body .stApp .st-key-timeline_move_delegate button p::before { content:"↱" / ""; color:#f0a97a; }
        body .stApp .st-key-timeline_move_wait button p::before { content:"◷" / ""; color:#aab4bd; }
        body .stApp .st-key-timeline_move_prepare button p::before { content:"◒" / ""; color:#ffbd78; }
        body .stApp .st-key-timeline_move_get_intelligence button p::before { content:"⌾" / ""; color:#a8e6cf; }
        body .stApp .st-key-timeline_move_synchronise button p::before { content:"⟳" / ""; color:#c8b6ff; }

        @keyframes main-release-pulse {
          0%,100% { transform:scale(1); }
          50% { transform:scale(1.1); }
        }
        .st-key-timeline_move_release button:hover p::before {
          animation:main-release-pulse 900ms ease-in-out infinite;
        }
        .st-key-timeline_move_event button:hover p::before { transform:scale(1.12); }
        .st-key-timeline_move_gateway button:hover p::before { transform:scale(1.12) rotate(45deg); }
        .st-key-timeline_move_action button:hover p::before { transform:translateY(-4px); }
        .st-key-timeline_move_update button:hover p::before { transform:rotate(6deg); }
        .st-key-timeline_move_milestone button:hover p::before { transform:rotate(-8deg); }
        .st-key-timeline_move_merge button:hover p::before { transform:scaleX(.78) scaleY(1.1); }
        .st-key-timeline_move_share_resources button:hover p::before { transform:scale(1.14); }
        .st-key-timeline_move_acquire_resources button:hover p::before { transform:translateY(4px) scale(1.12); }
        .st-key-timeline_move_delegate button:hover p::before { transform:translate(4px,-3px); }
        .st-key-timeline_move_wait button:hover p::before { transform:rotate(-18deg); }
        .st-key-timeline_move_prepare button:hover p::before { transform:rotate(18deg); }
        .st-key-timeline_move_get_intelligence button:hover p::before { transform:scale(1.14); }
        .st-key-timeline_move_synchronise button:hover p::before { transform:rotate(28deg); }

        @media(max-width:1000px) {
          :root { --main-object-size:3.1rem; --main-object-label-size:.66rem; }
          [class*="st-key-timeline_move_"] button {
            min-height:6rem !important;
            border-radius:22px !important;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_style_lab_theme(variant: str) -> None:
    """Layer one visual prototype over the unchanged timeline interaction."""

    common = """
    <style>
    [data-testid="stSidebar"] {
      border-right-color:rgba(191,218,208,.08) !important;
    }
    [data-testid="stSidebarNav"] { display:none !important; }
    .style-lab-nav {
      display:grid; gap:.38rem; padding:.35rem 0 1rem;
      border-bottom:1px solid rgba(191,218,208,.10);
    }
    .style-lab-nav a {
      display:flex; align-items:center; gap:.9rem; min-height:3rem;
      padding:.45rem .7rem; border-radius:16px; color:#98aaa3 !important;
      text-decoration:none !important; font-size:.76rem; letter-spacing:.02em;
      transition:background 150ms ease, color 150ms ease, transform 150ms ease;
    }
    .style-lab-nav a:hover {
      background:rgba(222,240,232,.06); color:#eef4ef !important;
      transform:translateX(3px);
    }
    .style-lab-nav a b {
      display:grid; place-items:center; min-width:2rem; color:#dfe875;
      font-size:1.6rem; line-height:1; font-weight:400;
    }
    .style-lab-head {
      padding:.8rem 0 1rem; margin-bottom:.45rem;
      border-bottom:1px solid rgba(191,218,208,.10);
    }
    .style-lab-head small {
      color:#dfe875; font-size:.6rem; letter-spacing:.16em;
      text-transform:uppercase;
    }
    .style-lab-head h2 {
      margin:.45rem 0 .25rem !important; font-size:1.25rem !important;
      letter-spacing:-.025em !important;
    }
    .style-lab-head p {
      color:#7f918a !important; font-size:.67rem; line-height:1.5;
      margin:0 !important;
    }
    .st-key-timeline_style_lab_selector [data-testid="stButtonGroup"] button {
      min-height:2.75rem !important; border-radius:999px !important;
      font-size:.66rem !important; letter-spacing:.02em !important;
      text-transform:none !important;
    }
    .timeline-hud { border-bottom-color:rgba(190,220,208,.10) !important; }
    .timeline-hud small, .timeline-readout small, .timeline-field-note,
    .timeline-dock-label {
      color:#62746d !important;
    }
    [data-testid="stPlotlyChart"] {
      position:relative; z-index:1; border-color:transparent !important;
      overflow:hidden; transition:border-radius 180ms ease, box-shadow 180ms ease;
    }
    .timeline-dock-label {
      position:relative; z-index:5; pointer-events:none;
    }
    .timeline-dock-label.timeline-planning-label {
      margin-top:1rem !important; height:auto; overflow:visible; opacity:1;
      padding-left:.2rem;
    }
    [class*="st-key-timeline_move_"] {
      position:relative; z-index:6;
    }
    [class*="st-key-timeline_move_"] button {
      transition:
        transform 150ms ease,
        background 150ms ease,
        box-shadow 150ms ease,
        border-color 150ms ease !important;
    }
    [class*="st-key-timeline_move_"] button p {
      display:flex !important; flex-direction:column; align-items:center;
      justify-content:center; gap:.48rem; font-size:0 !important;
      line-height:1 !important;
    }
    [class*="st-key-timeline_move_"] button p::before {
      display:block; line-height:1; font-size:var(--object-size);
      transition:transform 150ms ease, filter 150ms ease;
      filter:drop-shadow(0 7px 10px rgba(0,0,0,.16));
    }
    [class*="st-key-timeline_move_"] button p::after {
      display:block; font-size:var(--object-label-size); line-height:1;
      letter-spacing:.06em; color:var(--object-label);
      transition:opacity 150ms ease, transform 150ms ease;
    }
    [class*="st-key-timeline_move_"] button:hover p::before {
      filter:
        brightness(1.18)
        drop-shadow(0 0 18px color-mix(in srgb, currentColor 48%, transparent));
    }
    [class*="st-key-timeline_move_"] button:active {
      transform:translateY(1px) scale(.965) !important;
      transition-duration:70ms !important;
    }
    [class*="st-key-timeline_move_"] button[data-testid="stBaseButton-primary"] {
      outline:3px solid rgba(223,232,117,.42) !important;
      outline-offset:3px;
    }
    [class*="st-key-timeline_move_"] button[data-testid="stBaseButton-primary"] p::before {
      filter:
        brightness(1.22)
        drop-shadow(0 0 20px color-mix(in srgb, currentColor 55%, transparent));
    }
    [class*="st-key-timeline_move_"] button[data-testid="stBaseButton-primary"] p::after {
      opacity:1 !important; transform:translateY(0) !important;
      color:#f5f7ef !important;
    }
    .st-key-timeline_move_release button p::before {
      content:"★"; color:#f6d365;
    }
    .st-key-timeline_move_release button p::after { content:"Release"; }
    .st-key-timeline_move_event button p::before {
      content:"●"; color:#80d6c3;
    }
    .st-key-timeline_move_event button p::after { content:"Event"; }
    .st-key-timeline_move_gateway button p::before {
      content:"◈"; color:#d6a8ff;
    }
    .st-key-timeline_move_gateway button p::after { content:"Gateway"; }
    .st-key-timeline_move_action button p::before {
      content:"▲"; color:#ff8b69;
    }
    .st-key-timeline_move_action button p::after { content:"Action"; }
    .st-key-timeline_move_update button p::before {
      content:"■"; color:#9ca8ff;
    }
    .st-key-timeline_move_update button p::after { content:"Update"; }
    .st-key-timeline_move_milestone button p::before {
      content:"▼"; color:#e8f27c;
    }
    .st-key-timeline_move_milestone button p::after { content:"Milestone"; }
    .st-key-timeline_move_merge button p::before {
      content:"⋈"; color:#f3a6c8;
    }
    .st-key-timeline_move_merge button p::after { content:"Merge"; }
    .st-key-timeline_move_share_resources button p::before {
      content:"⇄"; color:#82c7ff;
    }
    .st-key-timeline_move_share_resources button p::after {
      content:"Share resources";
    }
    .st-key-timeline_move_acquire_resources button p::before {
      content:"⇣"; color:#7bd6a6;
    }
    .st-key-timeline_move_acquire_resources button p::after {
      content:"Acquire resources";
    }
    .st-key-timeline_move_delegate button p::before {
      content:"↱"; color:#f0a97a;
    }
    .st-key-timeline_move_delegate button p::after { content:"Delegate"; }
    .st-key-timeline_move_wait button p::before {
      content:"◷"; color:#aab4bd;
    }
    .st-key-timeline_move_wait button p::after { content:"Wait"; }
    .st-key-timeline_move_prepare button p::before {
      content:"◒"; color:#ffbd78;
    }
    .st-key-timeline_move_prepare button p::after { content:"Prepare"; }
    .st-key-timeline_move_get_intelligence button p::before {
      content:"⌾"; color:#a8e6cf;
    }
    .st-key-timeline_move_get_intelligence button p::after {
      content:"Get intelligence";
    }
    .st-key-timeline_move_synchronise button p::before {
      content:"⟳"; color:#c8b6ff;
    }
    .st-key-timeline_move_synchronise button p::after {
      content:"Synchronise";
    }
    @keyframes timeline-star-pulse {
      0%,100% { transform:scale(1); }
      50% { transform:scale(1.1); }
    }
    .st-key-timeline_move_release button:hover p::before {
      animation:timeline-star-pulse 900ms ease-in-out infinite;
    }
    .st-key-timeline_move_event button:hover p::before {
      transform:scale(1.12);
    }
    .st-key-timeline_move_gateway button:hover p::before {
      transform:scale(1.12) rotate(45deg);
    }
    .st-key-timeline_move_action button:hover p::before {
      transform:translateY(-4px);
    }
    .st-key-timeline_move_update button:hover p::before {
      transform:rotate(6deg);
    }
    .st-key-timeline_move_milestone button:hover p::before {
      transform:rotate(-8deg);
    }
    .st-key-timeline_move_merge button:hover p::before {
      transform:scaleX(.78) scaleY(1.1);
    }
    .st-key-timeline_move_share_resources button:hover p::before {
      transform:scale(1.14);
    }
    .st-key-timeline_move_acquire_resources button:hover p::before {
      transform:translateY(4px) scale(1.12);
    }
    .st-key-timeline_move_delegate button:hover p::before {
      transform:translate(4px,-3px);
    }
    .st-key-timeline_move_wait button:hover p::before {
      transform:rotate(-18deg);
    }
    .st-key-timeline_move_prepare button:hover p::before {
      transform:rotate(18deg);
    }
    .st-key-timeline_move_get_intelligence button:hover p::before {
      transform:scale(1.14);
    }
    .st-key-timeline_move_synchronise button:hover p::before {
      transform:rotate(28deg);
    }
    .st-key-timeline_add_uncertainty button,
    [class*="st-key-timeline_utility_"] button {
      transition:background 150ms ease, color 150ms ease, opacity 150ms ease !important;
    }
    @media(max-width:900px) {
      [class*="st-key-timeline_move_"] button {
        min-height:5.2rem !important;
      }
    }
    </style>
    """
    variants = {
        "Instrument": """
        <style>
        :root {
          --object-size:2.65rem;
          --object-label-size:.62rem;
          --object-label:#8fa29b;
        }
        .stApp {
          background:
            radial-gradient(circle at 72% 4%, rgba(69,133,117,.10), transparent 34rem),
            #020706 !important;
        }
        .block-container { max-width:1560px; padding:1.25rem 1.6rem 3rem; }
        [data-testid="stPlotlyChart"] {
          border-radius:20px !important;
          box-shadow:0 24px 80px rgba(0,0,0,.22) !important;
        }
        .timeline-dock-label { margin-top:-3.7rem !important; }
        [class*="st-key-timeline_move_"] button {
          min-height:5.5rem !important; border-radius:20px !important;
          border-color:rgba(167,197,187,.14) !important;
          background:rgba(5,17,14,.88) !important;
          box-shadow:0 10px 28px rgba(0,0,0,.18) !important;
        }
        .st-key-timeline_core_moves [class*="st-key-timeline_move_"] {
          margin-top:-4.2rem; margin-bottom:4.2rem;
        }
        [class*="st-key-timeline_move_"] button:hover {
          border-color:rgba(223,232,117,.45) !important;
          transform:translateY(-3px);
        }
        .st-key-timeline_add_uncertainty button,
        [class*="st-key-timeline_utility_"] button {
          border-radius:18px !important;
          border-color:rgba(167,197,187,.12) !important;
        }
        </style>
        """,
        "Playground": """
        <style>
        :root {
          --object-size:4.2rem;
          --object-label-size:.72rem;
          --object-label:#dbe6df;
        }
        .stApp {
          background:
            radial-gradient(circle at 75% -5%, rgba(110,155,142,.22), transparent 34rem),
            radial-gradient(circle at 28% 105%, rgba(156,168,255,.10), transparent 30rem),
            #030806 !important;
        }
        .block-container { max-width:1600px; padding:1rem 1.5rem 3rem; }
        [data-testid="stPlotlyChart"] {
          border-radius:34px !important;
          box-shadow:0 34px 100px rgba(0,0,0,.30) !important;
        }
        .timeline-hud {
          padding:.5rem .65rem 1rem !important; border-bottom:0 !important;
        }
        .timeline-dock-label { margin-top:-5.1rem !important; padding-left:1.25rem; }
        [class*="st-key-timeline_move_"] button {
          min-height:7.3rem !important; border:0 !important;
          border-radius:30px !important; color:#f5f7ef !important;
          box-shadow:
            0 16px 0 rgba(0,0,0,.12),
            0 24px 52px rgba(0,0,0,.25) !important;
        }
        .st-key-timeline_core_moves [class*="st-key-timeline_move_"] {
          margin-top:-5.2rem; margin-bottom:5.2rem;
        }
        .st-key-timeline_move_release button {
          background:linear-gradient(155deg,rgba(246,211,101,.22),#0c1612 70%) !important;
        }
        .st-key-timeline_move_event button {
          background:linear-gradient(155deg,rgba(128,214,195,.20),#0b1512 70%) !important;
        }
        .st-key-timeline_move_gateway button {
          background:linear-gradient(155deg,rgba(214,168,255,.20),#111017 70%) !important;
        }
        .st-key-timeline_move_action button {
          background:linear-gradient(155deg,rgba(255,139,105,.20),#121411 70%) !important;
        }
        .st-key-timeline_move_update button {
          background:linear-gradient(155deg,rgba(156,168,255,.20),#0e1315 70%) !important;
        }
        .st-key-timeline_move_milestone button {
          background:linear-gradient(155deg,rgba(232,242,124,.20),#101510 70%) !important;
        }
        .st-key-timeline_move_merge button {
          background:linear-gradient(155deg,rgba(243,166,200,.20),#161015 70%) !important;
        }
        .st-key-timeline_move_share_resources button {
          background:linear-gradient(155deg,rgba(130,199,255,.20),#0c1419 70%) !important;
        }
        .st-key-timeline_move_acquire_resources button {
          background:linear-gradient(155deg,rgba(123,214,166,.20),#0b1611 70%) !important;
        }
        .st-key-timeline_move_delegate button {
          background:linear-gradient(155deg,rgba(240,169,122,.20),#17120e 70%) !important;
        }
        .st-key-timeline_move_wait button {
          background:linear-gradient(155deg,rgba(170,180,189,.16),#101414 70%) !important;
        }
        .st-key-timeline_move_prepare button {
          background:linear-gradient(155deg,rgba(255,189,120,.20),#17130e 70%) !important;
        }
        .st-key-timeline_move_get_intelligence button {
          background:linear-gradient(155deg,rgba(168,230,207,.20),#0d1613 70%) !important;
        }
        .st-key-timeline_move_synchronise button {
          background:linear-gradient(155deg,rgba(200,182,255,.20),#121017 70%) !important;
        }
        [class*="st-key-timeline_move_"] button:hover {
          transform:translateY(-7px) scale(1.018);
          box-shadow:
            0 18px 0 rgba(0,0,0,.10),
            0 30px 64px rgba(0,0,0,.32) !important;
        }
        .st-key-timeline_add_uncertainty button {
          min-height:3.8rem !important; border:0 !important;
          border-radius:999px !important;
          background:rgba(128,214,195,.10) !important;
        }
        [class*="st-key-timeline_utility_"] button {
          border:0 !important; border-radius:999px !important;
          background:rgba(255,255,255,.035) !important;
        }
        </style>
        """,
        "Gallery": """
        <style>
        :root {
          --object-size:4rem;
          --object-label-size:.68rem;
          --object-label:#e8eee9;
        }
        .stApp { background:#040706 !important; }
        .block-container { max-width:1640px; padding:.7rem 1.25rem 2.5rem; }
        [data-testid="stPlotlyChart"] {
          border-radius:0 !important; box-shadow:none !important;
        }
        .timeline-hud {
          opacity:.58; border-bottom:0 !important; padding-bottom:.25rem !important;
        }
        .timeline-field-note { opacity:.42; }
        .timeline-dock-label {
          height:0; overflow:hidden; margin-top:-6.1rem !important;
          opacity:0;
        }
        [class*="st-key-timeline_move_"] button {
          min-height:6.2rem !important; border:0 !important;
          border-radius:999px !important; background:transparent !important;
          box-shadow:none !important;
        }
        .st-key-timeline_core_moves [class*="st-key-timeline_move_"] {
          margin-top:-5.5rem; margin-bottom:5.5rem;
        }
        [class*="st-key-timeline_move_"] button p::after {
          opacity:0; transform:translateY(-4px);
        }
        [class*="st-key-timeline_move_"] button:hover {
          background:rgba(235,243,238,.065) !important;
          transform:translateY(-3px);
        }
        [class*="st-key-timeline_move_"] button:hover p::after {
          opacity:1; transform:translateY(0);
        }
        .st-key-timeline_add_uncertainty button,
        [class*="st-key-timeline_utility_"] button {
          border:0 !important; border-radius:999px !important;
          background:transparent !important; opacity:.52;
        }
        .st-key-timeline_add_uncertainty button:hover,
        [class*="st-key-timeline_utility_"] button:not(:disabled):hover {
          background:rgba(235,243,238,.05) !important; opacity:1;
        }
        </style>
        """,
    }
    st.markdown(
        dedent(common) + dedent(variants[variant]),
        unsafe_allow_html=True,
    )


_apply_timeline_theme()
if STYLE_LAB_ENABLED:
    _apply_style_lab_theme(style_lab_variant)
else:
    _apply_main_graphic_move_theme()
_apply_pending_widget_reset()

events = _state("events", [])
assert isinstance(events, list)
events[:] = reconcile_event_dates(
    events,
    start_date=ROADMAP_START,
    end_date=ROADMAP_END,
)
uncertainties = _state("uncertainties", [])
assert isinstance(uncertainties, list)
pending_type = _state("pending_type", None)
pending_uncertainty = bool(_state("pending_uncertainty", False))
editing_id = _state("editing_id", None)
show_inspector = bool(_state("show_inspector", False))
integrated = bool(_state("integrated", False))
save_status = str(_state("save_status", "Saved on this device"))
default_bounds = (
    {"y": [-0.16, 0.16], "z": [-0.02, 0.48]}
    if is_new_plan
    else {"y": [-0.32, 0.32], "z": [-0.24, 0.90]}
)
bounds = _state("bounds", default_bounds)
assert isinstance(bounds, dict)

imported_camera = st.session_state.pop(
    _widget_key("imported_camera"),
    None,
)
if isinstance(imported_camera, dict):
    _restore_imported_camera(imported_camera)

outside_count = sum(
    str(event.get("interval_status")) == "outside" for event in events
)
placed_events = active_events(events)
top_left, top_toggle = st.columns([3, 1], vertical_alignment="bottom")
with top_toggle:
    if is_new_plan:
        st.markdown(
            f'<div class="timeline-plan-mode"><small>{html.escape(save_status)}</small><b>PERSONAL PLAN</b></div>',
            unsafe_allow_html=True,
        )
        layer = "Personal"
    else:
        layer = st.segmented_control(
            "Field layer",
            options=("Personal", "Convergence · simulated"),
            default="Personal",
            key=_widget_key("layer"),
            label_visibility="collapsed",
            width="stretch",
        )
show_collective = not is_new_plan and layer == "Convergence · simulated"

with top_left:
    st.markdown(
        f"""
        <div class="timeline-hud">
          <div><small>Protocol test 02 · {html.escape(benchmark_horizon)}</small><strong>{html.escape(benchmark_title)}</strong></div>
          <div class="timeline-readout"><small>Phase</small><b>PATH BUILDING</b></div>
          <div class="timeline-readout"><small>Moves</small><b>{len(placed_events):02d}</b></div>
          <div class="timeline-readout"><small>Uncertainty</small><b>{len(uncertainties):02d}</b></div>
          <div class="timeline-readout"><small>{html.escape(axis_y_label)}</small><b>{'BASELINE' if is_new_plan else ('TEST LAYER' if show_collective else 'NEUTRAL')}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

_render_journey_progress(len(placed_events))

confirmation = st.session_state.pop(_widget_key("confirmation"), None)
if isinstance(confirmation, dict):
    st.markdown(
        f"""
        <style>
        @keyframes timeline-settle {{
          0% {{ transform:translateX(0); filter:none; }}
          22% {{ transform:translateX(-2px); filter:brightness(1.08); }}
          44% {{ transform:translateX(2px); }}
          68% {{ transform:translateX(-1px); }}
          100% {{ transform:translateX(0); filter:none; }}
        }}
        [data-testid="stPlotlyChart"] {{
          animation:timeline-settle 520ms cubic-bezier(.2,.8,.2,1);
        }}
        </style>
        <div class="timeline-confirmation">
          <b>{html.escape(str(confirmation['title']))}</b>
          <span>{html.escape(str(confirmation['detail']))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

preview_parameter: float | None = None
uncertainty_preview: dict[str, object] | None = None
with st.sidebar:
    if STYLE_LAB_ENABLED:
        st.markdown(
            """
            <nav class="style-lab-nav" aria-label="Style Lab navigation">
              <a href="./commons" target="_self"><b>◎</b><span>Commons</span></a>
              <a href="./capacity" target="_self"><b>⬢</b><span>Tracks</span></a>
              <a href="./commons-host" target="_self"><b>◉</b><span>Operations</span></a>
              <a href="./test-timeline-benchmarks" target="_self"><b>◌</b><span>Experiments</span></a>
            </nav>
            <div class="style-lab-head">
              <small>Experiment · visual system only</small>
              <h2>Trajectory Style Lab</h2>
              <p>Same geometry and interaction. Three different ways for the trajectory to command the room.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="timeline_style_lab_selector"):
            selected_style_lab_variant = st.segmented_control(
                "Visual direction",
                options=STYLE_LAB_VARIANTS,
                default="Playground",
                key=STYLE_LAB_KEY,
                width="stretch",
                label_visibility="collapsed",
            )
            if selected_style_lab_variant in STYLE_LAB_VARIANTS:
                style_lab_variant = str(selected_style_lab_variant)
            else:
                style_lab_variant = "Playground"
        st.caption(
            {
                "Instrument": "Soft terminal · precise, spacious, quietly technical.",
                "Playground": "Big toy · oversized objects with physical feedback.",
                "Gallery": "Minimal museum · the controls almost disappear.",
            }[style_lab_variant]
        )
    if active_benchmark:
        st.markdown(
            f"""
            <div class="timeline-sidebar-head">
              <span class="timeline-experimental-badge">{'Plan' if is_new_plan else 'Experiment'}</span>
              <h3>{html.escape(benchmark_title)}</h3>
              <p>{html.escape(str(active_benchmark.get('prompt') or 'Draw the trajectory you imagine.'))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "← My plans" if is_new_plan else "← Choose another benchmark",
            key="timeline_choose_benchmark",
            icon="✨" if is_new_plan else "🧭",
            width="stretch",
        ):
            if is_new_plan:
                st.session_state["sketch_plan_stage"] = "entrance"
                st.switch_page("views/test_sketch_plan.py")
            else:
                st.switch_page("views/test_timeline_benchmarks.py")
    with st.container(key="timeline_rail"):
        with st.expander("Trajectory", expanded=False):
            if is_new_plan and str(active_benchmark.get("landing_mode")) != "planned":
                st.caption(
                    f"Now → {html.escape(destination_label or 'Goal')} · "
                    f"{html.escape(benchmark_horizon)}"
                )
            else:
                st.caption(
                    f"{ROADMAP_START.strftime('%d %b %Y')} → "
                    f"{ROADMAP_END.strftime('%d %b %Y')}"
                )
            landing_label = st.segmented_control(
                "How should the path arrive?",
                options=("Open", "Guided", "Planned"),
                default=initial_landing_label,
                key=_widget_key("landing_mode"),
                format_func=lambda value: (
                    "Fixed"
                    if is_new_plan and str(value) == "Planned"
                    else LANDING_COPY[str(value)]
                ),
                width="stretch",
            )
            st.caption(
                {
                    "Open": "We know the destination, but not yet how to arrive.",
                    "Guided": "Arrival can settle within a broad landing condition.",
                    "Planned": "The destination and arrival direction are defined.",
                }[str(landing_label)]
            )
        landing_mode = str(landing_label).lower()

        if is_new_plan:
            trajectory_document = build_trajectory_document(
                plan={**active_benchmark, "landing_mode": landing_mode},
                primitives=events,
                uncertainty=uncertainties,
            )
            trajectory_yaml_text = trajectory_yaml(trajectory_document)
            _render_local_autosave(trajectory_document)
            with st.expander("Active plan", expanded=False):
                st.markdown(
                    f'<div class="timeline-save-state"><b>{html.escape(save_status)}</b><span>Autosave is active</span></div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Now · Goal → {destination_label or 'Open goal'}"
                )
                edit_goal, edit_time = st.columns(2)
                with edit_goal:
                    if st.button(
                        "Edit goal",
                        key="timeline_plan_edit_goal",
                        width="stretch",
                    ):
                        _edit_plan_stage("goal")
                with edit_time:
                    if st.button(
                        "Edit time",
                        key="timeline_plan_edit_time",
                        width="stretch",
                    ):
                        _edit_plan_stage("time")
                if st.button(
                    "Save locally",
                    key="timeline_plan_save",
                    width="stretch",
                ):
                    st.session_state[_widget_key("save_status")] = (
                        "Saved on this device"
                    )
                    st.session_state[_widget_key("confirmation")] = {
                        "title": "Saved on this device",
                        "detail": "Your editable trajectory is up to date",
                    }
                    st.rerun()
                st.download_button(
                    "Export YAML",
                    data=trajectory_yaml_text,
                    file_name=_filename_for_plan(active_benchmark),
                    mime="application/yaml",
                    key="timeline_plan_export",
                    on_click=_mark_exported,
                    width="stretch",
                )
                if st.button(
                    "Duplicate plan",
                    key="timeline_plan_duplicate",
                    width="stretch",
                ):
                    duplicate = {
                        **active_benchmark,
                        "id": uuid4().hex,
                        "title": f"{benchmark_title} · copy",
                    }
                    st.session_state[ACTIVE_BENCHMARK_KEY] = duplicate
                    st.session_state[_widget_key("integrated")] = False
                    st.session_state[_widget_key("confirmation")] = {
                        "title": "Plan duplicated",
                        "detail": "The copy has its own local identity",
                    }
                    st.rerun()
                if st.button(
                    "Start another plan",
                    key="timeline_plan_start_another",
                    width="stretch",
                ):
                    _confirm_start_another(
                        trajectory_document,
                        trajectory_yaml_text,
                    )
                if st.button(
                    "Return to my plans",
                    key="timeline_plan_return",
                    width="stretch",
                ):
                    st.session_state["sketch_plan_stage"] = "entrance"
                    st.switch_page("views/test_sketch_plan.py")

        rail_title = (
            "Thicken an uncertain stretch"
            if pending_uncertainty
            else "Shape the journey"
        )
        rail_description = (
            "Thicken a local interval without moving the current best estimate."
            if pending_uncertainty
            else "Choose an object below, then decide when and how strongly it changes the path."
        )
        st.markdown(
            f"""
            <div class="timeline-sidebar-head">
              <span class="timeline-experimental-badge">Moves</span>
              <h3>{rail_title}</h3>
              <p>{rail_description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if pending_uncertainty:
            uncertainty_interval = st.slider(
                "Uncertain interval",
                min_value=0.02,
                max_value=0.98,
                step=0.01,
                key=_widget_key("uncertainty_interval"),
            )
            uncertainty_start = float(uncertainty_interval[0])
            uncertainty_end = float(uncertainty_interval[1])
            uncertainty_center = (
                uncertainty_start + uncertainty_end
            ) / 2.0
            uncertainty_width = uncertainty_end - uncertainty_start
            uncertainty_date = date_for_parameter(
                uncertainty_center,
                start_date=ROADMAP_START,
                end_date=ROADMAP_END,
            )
            st.markdown(
                _time_readout(
                    uncertainty_center,
                    uncertainty_date,
                    landing_mode,
                ),
                unsafe_allow_html=True,
            )
            uncertainty_strength = st.segmented_control(
                "How thick is the uncertainty?",
                options=tuple(UNCERTAINTY_STRENGTHS),
                key=_widget_key("uncertainty_strength"),
                width="stretch",
            )
            uncertainty_profile_label = st.segmented_control(
                "How does the uncertainty change?",
                options=("Balanced", "Expands", "Contracts"),
                key=_widget_key("uncertainty_profile_mode"),
                width="stretch",
            )
            st.caption(
                f"Local interval · {_time_language_label(uncertainty_start)} → "
                f"{_time_language_label(uncertainty_end)}"
            )
            uncertainty_style = uncertainty_geometry(
                str(uncertainty_strength)
            )
            uncertainty_preview = {
                "center_parameter": uncertainty_center,
                "temporal_width": uncertainty_width,
                "strength": str(uncertainty_strength),
                "profile_mode": str(uncertainty_profile_label).lower(),
                **uncertainty_style,
            }

            if st.button(
                "Anchor uncertainty",
                key="timeline_anchor_uncertainty",
                type="primary",
                width="stretch",
            ):
                uncertainties.append(
                    {
                        "id": uuid4().hex,
                        "center_parameter": uncertainty_center,
                        "center_date": uncertainty_date.isoformat(),
                        "start_parameter": uncertainty_start,
                        "end_parameter": uncertainty_end,
                        "start_date": date_for_parameter(
                            uncertainty_start,
                            start_date=ROADMAP_START,
                            end_date=ROADMAP_END,
                        ).isoformat(),
                        "end_date": date_for_parameter(
                            uncertainty_end,
                            start_date=ROADMAP_START,
                            end_date=ROADMAP_END,
                        ).isoformat(),
                        "strength": str(uncertainty_strength),
                        "temporal_width": uncertainty_width,
                        "profile_mode": str(
                            uncertainty_profile_label
                        ).lower(),
                        **uncertainty_style,
                        "created_at": date.today().isoformat(),
                    }
                )
                st.session_state[_widget_key("pending_uncertainty")] = False
                st.session_state[_widget_key("confirmation")] = {
                    "title": "Uncertainty updated",
                    "detail": (
                        f"{uncertainty_strength} chunk anchored at "
                        f"s={uncertainty_center:.2f}"
                    ),
                }
                st.rerun()

            if st.button(
                "Cancel modifier",
                key="timeline_cancel_uncertainty",
                width="stretch",
            ):
                st.session_state[_widget_key("pending_uncertainty")] = False
                st.rerun()

        elif pending_type is None:
            st.caption(
                "Choose a move object below, or thicken one uncertain stretch."
            )
            suggestions = tuple(active_benchmark.get("suggested_moves") or ())
            parsed_suggestions = tuple(
                parsed
                for suggestion in suggestions
                if (parsed := _suggested_move_parts(suggestion)) is not None
            )
            if parsed_suggestions:
                with st.expander("Try a possible move", expanded=True):
                    st.caption(
                        "Choose one to open it on the trajectory. You can rename it."
                    )
                    for index, (suggested_type, suggested_title) in enumerate(
                        parsed_suggestions
                    ):
                        suggested_definition = EVENT_TYPES[suggested_type]
                        if st.button(
                            f"{suggested_definition['glyph']}  {suggested_title}",
                            key=f"timeline_suggested_move_{index}",
                            width="stretch",
                        ):
                            _request_placement(
                                suggested_type,
                                title=suggested_title,
                            )
                            st.rerun()
        else:
            definition = EVENT_TYPES[str(pending_type)]
            if definition.get("description"):
                st.caption(str(definition["description"]))
            preview_parameter = st.slider(
                "When",
                min_value=0.02,
                max_value=0.98,
                step=0.01,
                key=_widget_key("time_slider"),
            )
            preview_date = date_for_parameter(
                preview_parameter,
                start_date=ROADMAP_START,
                end_date=ROADMAP_END,
            )
            st.markdown(
                _time_readout(
                    preview_parameter,
                    preview_date,
                    landing_mode,
                ),
                unsafe_allow_html=True,
            )

            action_verb = "Update" if editing_id else "Place"
            with st.container(key=_widget_key("placement_editor")):
                title = st.text_input(
                    "Title",
                    placeholder="Name the move",
                    max_chars=48,
                    key=_widget_key("form_title"),
                )
                influence_scale = st.segmented_control(
                    "How much does this change the journey?",
                    options=tuple(INFLUENCE_SCALES),
                    key=_widget_key("influence_scale"),
                    format_func=lambda value: INFLUENCE_COPY[str(value)],
                    width="stretch",
                )
                st.caption(INFLUENCE_HELP[str(influence_scale)])
                directional_mode_label = st.segmented_control(
                    "How does this change the direction of the path?",
                    options=("Gradually", "Abruptly"),
                    key=_widget_key("directional_mode"),
                    width="stretch",
                )
                topology_mode_label = st.segmented_control(
                    "Topology",
                    options=("Continuation", "Bifurcation"),
                    key=_widget_key("topology_mode"),
                    width="stretch",
                )
                branch_label_a = "Option A"
                branch_label_b = "Option B"
                if topology_mode_label == "Bifurcation":
                    with st.container(border=True):
                        st.number_input(
                            "Number of branches",
                            min_value=2,
                            max_value=2,
                            value=2,
                            disabled=True,
                            help="RC0.1 supports a binary bifurcation.",
                        )
                        branch_left, branch_right = st.columns(2)
                        with branch_left:
                            branch_label_a = st.text_input(
                                "First branch name",
                                max_chars=48,
                                key=_widget_key("branch_label_a"),
                            )
                        with branch_right:
                            branch_label_b = st.text_input(
                                "Second branch name",
                                max_chars=48,
                                key=_widget_key("branch_label_b"),
                            )
                with st.expander("Details · optional", expanded=False):
                    description = st.text_area(
                        "Description",
                        placeholder="Add context that should travel with this move.",
                        key=_widget_key("description"),
                    )
                submitted = st.button(
                    f"{action_verb} {definition['label'].lower()}",
                    key=_widget_key("place_move"),
                    type="primary",
                    width="stretch",
                )

            if st.button(
                "Cancel placement",
                key="timeline_utility_cancel",
                width="stretch",
            ):
                st.session_state[_widget_key("pending_type")] = None
                st.session_state[_widget_key("editing_id")] = None
                st.rerun()

            if submitted:
                clean_title = title.strip()
                duplicate = any(
                    abs(
                        float(event["time_parameter"]) - preview_parameter
                    ) < 0.005
                    and str(event["id"]) != str(editing_id or "")
                    for event in active_events(events)
                )
                if not clean_title:
                    st.error("Give this move a short title.")
                elif duplicate:
                    st.error(
                        "Another event is already anchored here. "
                        "Move the time slider."
                    )
                else:
                    geometry = geometry_for_influence(str(influence_scale))
                    existing = next(
                        (
                            event
                            for event in events
                            if str(event["id"]) == str(editing_id)
                        ),
                        None,
                    )
                    move_id = str(existing["id"]) if existing else uuid4().hex
                    now = datetime.now().astimezone().isoformat()
                    topology = (
                        "branching"
                        if topology_mode_label == "Bifurcation"
                        else "continuation"
                    )
                    branch_labels = (
                        [
                            {
                                "id": f"{move_id}:1",
                                "parent_id": move_id,
                                "label": branch_label_a.strip() or "Option A",
                            },
                            {
                                "id": f"{move_id}:2",
                                "parent_id": move_id,
                                "label": branch_label_b.strip() or "Option B",
                            },
                        ]
                        if topology == "branching"
                        else []
                    )
                    event_record: dict[str, object] = {
                        "id": (
                            move_id
                        ),
                        "type": str(pending_type),
                        "title": clean_title,
                        "time_parameter": preview_parameter,
                        "temporal_position": preview_parameter,
                        "date_value": preview_date.isoformat(),
                        "date": preview_date.isoformat(),
                        "time_basis": (
                            "date"
                            if landing_mode == "planned"
                            and temporal_mode == "linear"
                            else "relative"
                        ),
                        "interval_start": ROADMAP_START.isoformat(),
                        "interval_end": ROADMAP_END.isoformat(),
                        "influence_scale": str(influence_scale),
                        "directional_mode": str(
                            directional_mode_label
                        ).lower(),
                        "topology_mode": topology,
                        "branch_parent": (
                            existing.get("branch_parent") if existing else None
                        ),
                        "branch_labels": branch_labels,
                        "energy_effect": geometry["energy_offset"],
                        "entropy_effect": 0.0,
                        "influence_radius": geometry["influence_width"],
                        "energy_offset": geometry["energy_offset"],
                        "alignment_offset": 0.0,
                        "influence_width": geometry["influence_width"],
                        "interval_status": "active",
                        "description": description.strip(),
                        "intention": str(existing.get("intention") or "") if existing else "",
                        "dependencies": list(existing.get("dependencies") or []) if existing else [],
                        "responsible_actors": list(existing.get("responsible_actors") or []) if existing else [],
                        "collaborators": list(existing.get("collaborators") or []) if existing else [],
                        "resources_needed": list(existing.get("resources_needed") or []) if existing else [],
                        "completion_evidence": list(existing.get("completion_evidence") or []) if existing else [],
                        "visibility": str(existing.get("visibility") or "Private") if existing else "Private",
                        "tags": list(existing.get("tags") or []) if existing else [],
                        "notes": str(existing.get("notes") or "") if existing else "",
                        "created_at": (
                            str(existing["created_at"])
                            if existing
                            else now
                        ),
                        "modified_at": now,
                    }
                    if existing:
                        index = events.index(existing)
                        events[index] = event_record
                    else:
                        events.append(event_record)
                    st.session_state[_widget_key("pending_type")] = None
                    st.session_state[_widget_key("editing_id")] = None
                    st.session_state[_widget_key("integrated")] = False
                    st.session_state[_widget_key("confirmation")] = {
                        "title": "Future reshaped",
                        "detail": (
                            f"{definition['label']} settled into the path at "
                            f"s={preview_parameter:.2f}"
                        ),
                    }
                    st.rerun()

        if outside_count:
            st.warning(
                f"{outside_count} event(s) fall outside this roadmap interval. "
                "They remain stored and have not been deleted."
            )

with st.container(key="timeline_stage"):
    if not placed_events:
        st.markdown(
            f"""
            <div class="timeline-first-instruction">
              <b>{'What should happen—not necessarily first, but off the top of your head?' if is_new_plan else 'Your path exists. Now shape it.'}</b>
              <span>{'Choose any move that comes to mind.' if is_new_plan else 'Try rotating the view, then choose your first move below.'}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif len(placed_events) == 1:
        st.markdown(
            """
            <div class="timeline-first-instruction">
              <b>You changed the future.</b>
              <span>Notice how the path settled, then choose what happens next.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f"""
        <div class="timeline-field-note">
          <span>Drag to orbit · scroll to zoom</span>
          <span>{'entropy baseline' if is_new_plan else ('simulated collective traces' if show_collective else 'personal alignment neutral')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    curve_x, curve_y, curve_z = sample_trajectory(
        events,
        landing_mode=landing_mode,
        samples_per_segment=72,
    )
    uncertainty_radii = [
        float(chunk["radius"]) for chunk in uncertainties
    ]
    if uncertainty_preview is not None:
        uncertainty_radii.append(float(uncertainty_preview["radius"]))
    maximum_uncertainty = max(uncertainty_radii, default=0.0)
    expanded = expanded_bounds(
        bounds,
        y_values=[
            *curve_y,
            min(curve_y) - maximum_uncertainty,
            max(curve_y) + maximum_uncertainty,
        ],
        z_values=[
            *curve_z,
            min(curve_z) - maximum_uncertainty,
            max(curve_z) + maximum_uncertainty,
        ],
    )
    if expanded != bounds:
        st.session_state[_widget_key("bounds")] = expanded
        bounds = expanded

    trajectory_figure = _build_figure(
        events,
        uncertainties,
        show_collective=show_collective,
        landing_mode=landing_mode,
        preview_parameter=preview_parameter,
        preview_type=str(pending_type) if pending_type else None,
        uncertainty_preview=uncertainty_preview,
        bounds=bounds,
    )
    if STYLE_LAB_ENABLED:
        trajectory_figure = _apply_style_lab_figure(
            trajectory_figure,
            style_lab_variant,
        )

    st.plotly_chart(
        trajectory_figure,
        width="stretch",
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "modeBarButtonsToRemove": ["lasso3d", "select2d"],
        },
        key=_widget_key("field"),
    )
    _render_camera_persistence_hook(
        (
            f"{len(events)}:{len(uncertainties)}:{pending_type}:"
            f"{pending_uncertainty}:{preview_parameter}:"
            f"{uncertainty_preview}"
        )
    )

    st.markdown(
        '<div class="timeline-dock-label">Choose what happens next</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="timeline_core_moves"):
        _render_move_row(
            CORE_EVENT_TYPE_KEYS,
            pending_type,
        )

    st.markdown(
        (
            '<div class="timeline-dock-label timeline-planning-label">'
            "Planning primitives</div>"
        ),
        unsafe_allow_html=True,
    )
    with st.container(key="timeline_planning_moves"):
        _render_move_row(PLANNING_PRIMITIVE_KEYS, pending_type)

    uncertainty_column, remove_uncertainty_column = st.columns([2.3, 1])
    with uncertainty_column:
        if st.button(
            "≈  Add local uncertainty",
            key="timeline_add_uncertainty",
            width="stretch",
        ):
            _request_uncertainty()
            st.rerun()
    with remove_uncertainty_column:
        if st.button(
            "Remove latest",
            key="timeline_remove_uncertainty",
            disabled=not uncertainties,
            width="stretch",
        ):
            uncertainties.pop()
            st.session_state[_widget_key("confirmation")] = {
                "title": "Uncertainty updated",
                "detail": "Latest local chunk removed",
            }
            st.rerun()

    if is_new_plan:
        save_column, export_column = st.columns(2)
        with save_column:
            if st.button(
                "Save locally",
                key="timeline_utility_save",
                width="stretch",
            ):
                st.session_state[_widget_key("save_status")] = (
                    "Saved on this device"
                )
                st.session_state[_widget_key("confirmation")] = {
                    "title": "Saved on this device",
                    "detail": "Your editable trajectory is up to date",
                }
                st.rerun()
        with export_column:
            st.download_button(
                "Export YAML",
                data=trajectory_yaml_text,
                file_name=_filename_for_plan(active_benchmark),
                mime="application/yaml",
                key="timeline_utility_export",
                on_click=_mark_exported,
                width="stretch",
            )

    undo_column, inspect_column, integrate_column = st.columns(
        [1, 1, 1.5]
    )
    with undo_column:
        if st.button(
            "↶ Undo last",
            key="timeline_utility_undo",
            disabled=not placed_events,
            width="stretch",
        ):
            latest_id = str(placed_events[-1]["id"])
            events[:] = [
                event for event in events if str(event["id"]) != latest_id
            ]
            st.session_state[_widget_key("integrated")] = False
            st.rerun()
    with inspect_column:
        if st.button(
            "⌖ Inspect",
            key="timeline_utility_inspect",
            disabled=not placed_events,
            width="stretch",
        ):
            show_inspector = not show_inspector
            st.session_state[_widget_key("show_inspector")] = show_inspector
    with integrate_column:
        if st.button(
            "Integrate trajectory",
            key="timeline_utility_integrate",
            disabled=len(placed_events) < MINIMUM_MOVES,
            width="stretch",
        ):
            st.session_state[_widget_key("integrated")] = True
            integrated = True
            st.balloons()
        st.markdown(
            f"""
            <div class="timeline-progress">
              Place {MINIMUM_MOVES} moves to integrate this test trajectory.
              <b>{min(len(placed_events), MINIMUM_MOVES)} of {MINIMUM_MOVES} placed.</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if integrated:
        integration_detail = (
            "Your path is becoming clearer. It is saved on this device, "
            "but has not yet been exported."
            if is_new_plan
            else "Your path is becoming clearer. It has not yet been saved "
            "on this device or exported."
        )
        st.markdown(
            f"""
            <div class="timeline-integration-card">
              <b>Trajectory integrated</b>
              <span>{html.escape(integration_detail)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if is_new_plan:
            saved_column, export_after_column, continue_column = st.columns(3)
            with saved_column:
                st.button(
                    "Saved locally ✓",
                    key="timeline_integrated_saved",
                    disabled=True,
                    width="stretch",
                )
            with export_after_column:
                st.download_button(
                    "Export YAML",
                    data=trajectory_yaml_text,
                    file_name=_filename_for_plan(active_benchmark),
                    mime="application/yaml",
                    key="timeline_integrated_export",
                    on_click=_mark_exported,
                    width="stretch",
                )
            with continue_column:
                if st.button(
                    "Continue editing",
                    key="timeline_integrated_continue",
                    width="stretch",
                ):
                    st.session_state[_widget_key("integrated")] = False
                    st.rerun()

    if show_inspector and placed_events:
        with st.sidebar:
            st.divider()
            st.markdown(
                '<div class="timeline-sidebar-kicker">Observations</div>',
                unsafe_allow_html=True,
            )
            selected_id = st.selectbox(
                "Inspect a move",
                options=[str(event["id"]) for event in placed_events],
                format_func=lambda event_id: _event_label(
                    next(
                        event
                        for event in placed_events
                        if str(event["id"]) == event_id
                    )
                ),
                key=_widget_key("selected_event"),
            )
            selected_event = next(
                event
                for event in placed_events
                if str(event["id"]) == str(selected_id)
            )
            selected_definition = EVENT_TYPES[str(selected_event["type"])]
            st.markdown(
                f"""
                <div class="timeline-inspector">
                  <b>{html.escape(selected_definition['glyph'])} {html.escape(str(selected_event['title']))}</b><br>
                  {html.escape(selected_definition['label'])} ·
                  s={float(selected_event['time_parameter']):.2f} ·
                  {date.fromisoformat(str(selected_event['date_value'])).strftime('%d %b %Y')} ·
                  {html.escape(INFLUENCE_COPY[_event_influence(selected_event)])} ·
                  {html.escape(directional_mode(selected_event).title())} ·
                  {html.escape(topology_mode(selected_event).title())}
                </div>
                """,
                unsafe_allow_html=True,
            )
            edit_column, remove_column = st.columns(2)
            with edit_column:
                if st.button(
                    "Edit selected move",
                    key="timeline_utility_edit",
                    width="stretch",
                ):
                    _request_placement(
                        str(selected_event["type"]),
                        event=selected_event,
                    )
                    st.rerun()
            with remove_column:
                if st.button(
                    "Remove selected move",
                    key="timeline_utility_remove",
                    width="stretch",
                ):
                    events[:] = [
                        event
                        for event in events
                        if str(event["id"]) != str(selected_event["id"])
                    ]
                    st.session_state[_widget_key("integrated")] = False
                    st.rerun()
