"""A session-only, game-like timeline interaction study."""

from __future__ import annotations

from datetime import date, timedelta
import html
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
    IMPORTANCE_LEVELS,
    PLANNING_PRIMITIVE_KEYS,
    UNCERTAINTY_STRENGTHS,
    active_events,
    date_for_parameter,
    event_points,
    expanded_bounds,
    geometry_for_importance,
    kink_indicators,
    reconcile_event_dates,
    relative_time_label,
    sample_trajectory,
    trajectory_point,
    uncertainty_envelope_points,
    uncertainty_geometry,
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
benchmark_title = str(active_benchmark.get("title") or "Open trajectory")
benchmark_horizon = str(
    active_benchmark.get("horizon_label") or "2-year experimental horizon"
)
benchmark_days = max(1, int(active_benchmark.get("horizon_days") or 730))
ROADMAP_START = date.today()
ROADMAP_END = ROADMAP_START + timedelta(days=benchmark_days)
CAMERA_STORAGE_KEY = "protocol-hack:timeline-camera-v2"


def _state(name: str, default: object) -> object:
    return st.session_state.setdefault(f"{STATE_PREFIX}{name}", default)


def _event_label(event: dict[str, object]) -> str:
    definition = EVENT_TYPES[str(event["type"])]
    return f"{definition['glyph']} {event['title']}"


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
) -> None:
    st.session_state[_widget_key("pending_type")] = event_type
    st.session_state[_widget_key("pending_uncertainty")] = False
    st.session_state[_widget_key("editing_id")] = (
        str(event["id"]) if event else None
    )
    st.session_state[_widget_key("placement_reset")] = {
        "time_slider": float(event["time_parameter"]) if event else 0.22,
        "form_title": str(event["title"]) if event else "",
        "importance": str(event["importance"]) if event else "Signal",
        "node_mode": (
            str(event["node_mode"]).title() if event else "Smooth"
        ),
    }
    st.session_state[_widget_key("integrated")] = False


def _request_uncertainty() -> None:
    st.session_state[_widget_key("pending_type")] = None
    st.session_state[_widget_key("editing_id")] = None
    st.session_state[_widget_key("pending_uncertainty")] = True
    st.session_state[_widget_key("placement_reset")] = {
        "uncertainty_center": 0.42,
        "uncertainty_strength": "Marked",
        "uncertainty_width": 0.18,
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
                f"{definition['glyph']}  {definition['label']}",
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
        (0.30, 8, base_opacity),
        (0.62, 6, base_opacity * 0.72),
        (1.00, 4, base_opacity * 0.42),
    )
    directions_per_shell = 4
    for shell_index, (radius_fraction, line_width, opacity) in enumerate(
        shells
    ):
        for direction in range(directions_per_shell):
            angle_fraction = (
                direction / directions_per_shell
                + (shell_index * 0.125)
            )
            trace_x, trace_y, trace_z = uncertainty_envelope_points(
                x,
                y,
                z,
                chunk,
                radial_fraction=radius_fraction,
                angle_fraction=angle_fraction,
            )
            figure.add_trace(
                go.Scatter3d(
                    x=trace_x,
                    y=trace_y,
                    z=trace_z,
                    mode="lines",
                    line={"color": color, "width": line_width},
                    opacity=opacity,
                    hoverinfo="skip",
                    showlegend=False,
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

    figure.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="lines",
            line={"color": "#ecf7ef", "width": 8},
            hoverinfo="skip",
            showlegend=False,
            name="Personal trajectory",
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
            text=[landing_labels[landing_mode]],
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
                        9 if str(event["node_mode"]) == "kink" else 6
                        for event in placed
                    ],
                    "color": [
                        EVENT_TYPES[str(event["type"])]["color"]
                        for event in placed
                    ],
                    "opacity": 0.72,
                },
                text=[
                    EVENT_TYPES[str(event["type"])]["glyph"]
                    for event in placed
                ],
                textposition="middle center",
                textfont={
                    "color": [
                        EVENT_TYPES[str(event["type"])]["color"]
                        for event in placed
                    ],
                    "size": [
                        28 if str(event["node_mode"]) == "kink" else 24
                        for event in placed
                    ],
                },
                customdata=[
                    [
                        html.escape(str(event["title"])),
                        EVENT_TYPES[str(event["type"])]["label"],
                        f"{float(event['time_parameter']):.2f}",
                        date.fromisoformat(str(event["date_value"])).strftime(
                            "%d %b %Y"
                        ),
                        str(event["importance"]),
                        str(event["node_mode"]).title(),
                    ]
                    for event in placed
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]} · s=%{customdata[2]} / %{customdata[3]}"
                    "<br>Importance: %{customdata[4]}"
                    "<br>Geometry: %{customdata[5]}<extra></extra>"
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

    tick_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    tick_text = [
        relative_time_label(
            value,
            start_date=ROADMAP_START,
            end_date=ROADMAP_END,
        ).upper()
        for value in tick_values
    ]
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
            "camera": {"eye": {"x": 1.55, "y": -1.45, "z": 1.05}},
            "uirevision": "timeline-camera-v2",
            "aspectmode": "manual",
            "aspectratio": {"x": 1.75, "y": 1.0, "z": 1.0},
            "xaxis": {
                "title": {"text": "TIME", "font": {"color": "#c2d0cb"}},
                "range": [0, 1],
                "tickvals": tick_values,
                "ticktext": tick_text,
                "gridcolor": "#13201d",
                "linecolor": "#43534e",
                "zerolinecolor": "#43534e",
                "tickfont": {"color": "#7f918b", "size": 10},
                "showbackground": False,
                "showspikes": False,
            },
            "yaxis": {
                "title": {
                    "text": "ALIGNMENT",
                    "font": {"color": "#c2d0cb"},
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
                "title": {"text": "ENERGY", "font": {"color": "#c2d0cb"}},
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
            "title": {"text": "TIME", "font": {"color": axis}},
            "tickfont": {"color": ticks, "size": 10},
        },
        yaxis={
            "gridcolor": grid,
            "linecolor": line,
            "zerolinecolor": line,
            "showgrid": show_grid,
            "title": {"text": "ALIGNMENT", "font": {"color": axis}},
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
          min-width:23rem !important; width:23rem !important;
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
        .timeline-field-note {
          display:flex; justify-content:space-between; gap:1rem; color:#71827d;
          font-size:.68rem; letter-spacing:.08em; text-transform:uppercase;
          margin:.6rem 0 -.25rem;
        }
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
        button p { color:inherit !important; }
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
          border-radius:6px !important; background:#dfe875 !important;
          color:#11160e !important; box-shadow:none !important;
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
          opacity:.28 !important; cursor:not-allowed !important;
          border-style:dashed !important; filter:saturate(.25);
        }
        [class*="st-key-timeline_utility_"] button:not(:disabled):hover {
          color:#eef2e8 !important;
        }
        [class*="st-key-timeline_utility_integrate"] button:not(:disabled) {
          border-color:#dfe875 !important; color:#dfe875 !important;
        }
        .timeline-progress {
          color:#71827d; font-size:.66rem; text-align:right; margin-top:.35rem;
        }
        .timeline-progress b { color:#aebdb7; font-weight:500; }
        [data-testid="stWidgetLabel"] p {
          color:#91a39d !important; font-size:.68rem !important;
          letter-spacing:.07em; text-transform:uppercase;
        }
        div[data-baseweb="input"] > div, [data-baseweb="select"] > div,
        textarea {
          background:#020807 !important; border-color:#344640 !important;
          color:#edf1e8 !important;
        }
        input, textarea { color:#edf1e8 !important; caret-color:#dfe875 !important; }
        input::placeholder, textarea::placeholder {
          color:#667770 !important; opacity:1;
        }
        [data-testid="stButtonGroup"] button {
          background:#020807 !important; border-color:#344640 !important;
          color:#aab8b3 !important; border-radius:4px !important;
        }
        button[data-testid="stBaseButton-pillsActive"] {
          background:#dfe875 !important; color:#11160e !important;
          border-color:#dfe875 !important;
        }
        [data-testid="stSlider"] [role="slider"] {
          background:#dfe875 !important; border-color:#dfe875 !important;
        }
        [data-testid="stFormSubmitButton"] button {
          min-height:3rem; width:100%; background:#dfe875 !important;
          color:#11160e !important; border:0 !important; border-radius:5px !important;
          box-shadow:none !important; text-transform:uppercase; letter-spacing:.08em;
        }
        [data-testid="stFormSubmitButton"] button p {
          color:#11160e !important;
        }
        .timeline-inspector {
          border-left:2px solid #dfe875; padding:.15rem 0 .15rem 1rem;
          color:#95a69f; font-size:.76rem; line-height:1.7;
        }
        .timeline-inspector b { color:#edf1e8; }
        [data-testid="stAlert"] {
          background:#07110f; border:1px solid #425b54; color:#e8eee9;
        }
        @media(max-width:760px) {
          .block-container { padding:.8rem .8rem 2rem; }
          .timeline-hud { grid-template-columns:1fr 1fr; }
          .timeline-readout { text-align:left; min-width:0; }
          .timeline-confirmation { left:1rem; right:1rem; top:4rem; }
          [data-testid="stPlotlyChart"] { min-height:470px; }
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
      min-width:22rem !important; width:22rem !important;
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
      [data-testid="stSidebar"] {
        min-width:19rem !important; width:19rem !important;
      }
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
bounds = _state("bounds", {"y": [-0.32, 0.32], "z": [-0.24, 0.90]})
assert isinstance(bounds, dict)

outside_count = sum(
    str(event.get("interval_status")) == "outside" for event in events
)
placed_events = active_events(events)
top_left, top_toggle = st.columns([3, 1], vertical_alignment="bottom")
with top_toggle:
    layer = st.segmented_control(
        "Field layer",
        options=("Personal", "Convergence · simulated"),
        default="Personal",
        key=_widget_key("layer"),
        label_visibility="collapsed",
        width="stretch",
    )
show_collective = layer == "Convergence · simulated"

with top_left:
    st.markdown(
        f"""
        <div class="timeline-hud">
          <div><small>Protocol test 02 · {html.escape(benchmark_horizon)}</small><strong>{html.escape(benchmark_title)}</strong></div>
          <div class="timeline-readout"><small>Phase</small><b>PATH BUILDING</b></div>
          <div class="timeline-readout"><small>Moves</small><b>{len(placed_events):02d}</b></div>
          <div class="timeline-readout"><small>Uncertainty</small><b>{len(uncertainties):02d}</b></div>
          <div class="timeline-readout"><small>Alignment</small><b>{'TEST LAYER' if show_collective else 'NEUTRAL'}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

confirmation = st.session_state.pop(_widget_key("confirmation"), None)
if isinstance(confirmation, dict):
    st.markdown(
        f"""
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
              <span class="timeline-experimental-badge">Active benchmark</span>
              <h3>{html.escape(benchmark_title)}</h3>
              <p>{html.escape(str(active_benchmark.get('prompt') or 'Draw the trajectory you imagine.'))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "← Choose another benchmark",
            key="timeline_choose_benchmark",
            icon="🧭",
            width="stretch",
        ):
            st.switch_page("views/test_timeline_benchmarks.py")
    with st.container(key="timeline_rail"):
        with st.expander("Roadmap geometry", expanded=False):
            st.caption(
                f"{ROADMAP_START.strftime('%d %b %Y')} → "
                f"{ROADMAP_END.strftime('%d %b %Y')}"
            )
            landing_label = st.segmented_control(
                "Landing plan",
                options=("Open", "Guided", "Planned"),
                default="Open",
                key=_widget_key("landing_mode"),
                width="stretch",
            )
            st.caption(
                {
                    "Open": "Destination fixed; arrival direction inferred.",
                    "Guided": (
                        "Destination fixed; arrival flattens into a landing plane."
                    ),
                    "Planned": "Destination and final orientation fixed.",
                }[str(landing_label)]
            )
        landing_mode = str(landing_label).lower()

        rail_title = (
            "Uncertainty modifier"
            if pending_uncertainty
            else "Event placement"
        )
        rail_description = (
            "Thicken a local interval without moving the current best estimate."
            if pending_uncertainty
            else "Time is authored here. Alignment and energy are generated from the event semantics."
        )
        st.markdown(
            f"""
            <div class="timeline-sidebar-head">
              <span class="timeline-experimental-badge">Experimental</span>
              <h3>{rail_title}</h3>
              <p>{rail_description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if pending_uncertainty:
            uncertainty_center = st.slider(
                "Centre time",
                min_value=0.04,
                max_value=0.96,
                step=0.01,
                key=_widget_key("uncertainty_center"),
            )
            uncertainty_date = date_for_parameter(
                uncertainty_center,
                start_date=ROADMAP_START,
                end_date=ROADMAP_END,
            )
            uncertainty_relative = relative_time_label(
                uncertainty_center,
                start_date=ROADMAP_START,
                end_date=ROADMAP_END,
            )
            st.markdown(
                f"""
                <div class="timeline-time-readout">
                  <div><small>Centre</small><b>s={uncertainty_center:.2f}</b></div>
                  <div><small>Relative</small><b>{html.escape(uncertainty_relative)}</b></div>
                  <div><small>Date</small><b>{uncertainty_date.strftime("%d %b %Y")}</b></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            uncertainty_strength = st.segmented_control(
                "Uncertainty strength",
                options=tuple(UNCERTAINTY_STRENGTHS),
                key=_widget_key("uncertainty_strength"),
                width="stretch",
            )
            uncertainty_width = st.slider(
                "Temporal width",
                min_value=0.06,
                max_value=0.42,
                step=0.01,
                key=_widget_key("uncertainty_width"),
                help="Fraction of the roadmap affected by this local chunk.",
            )
            uncertainty_start = max(
                0.0,
                uncertainty_center - (uncertainty_width / 2.0),
            )
            uncertainty_end = min(
                1.0,
                uncertainty_center + (uncertainty_width / 2.0),
            )
            st.caption(
                f"Local interval · s={uncertainty_start:.2f}–{uncertainty_end:.2f}"
            )
            uncertainty_style = uncertainty_geometry(
                str(uncertainty_strength)
            )
            uncertainty_preview = {
                "center_parameter": uncertainty_center,
                "temporal_width": uncertainty_width,
                "strength": str(uncertainty_strength),
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
                "Select a move type, or add a local uncertainty modifier."
            )
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
            relative_label = relative_time_label(
                preview_parameter,
                start_date=ROADMAP_START,
                end_date=ROADMAP_END,
            )
            st.markdown(
                f"""
                <div class="timeline-time-readout">
                  <div><small>Position</small><b>s={preview_parameter:.2f}</b></div>
                  <div><small>Relative</small><b>{html.escape(relative_label)}</b></div>
                  <div><small>Date</small><b>{preview_date.strftime("%d %b %Y")}</b></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            action_verb = "Update" if editing_id else "Place"
            with st.form(_widget_key("placement_form"), clear_on_submit=False):
                title = st.text_input(
                    "Title",
                    placeholder="Name the move",
                    max_chars=48,
                    key=_widget_key("form_title"),
                )
                importance = st.segmented_control(
                    "Importance",
                    options=tuple(IMPORTANCE_LEVELS),
                    key=_widget_key("importance"),
                    width="stretch",
                )
                node_mode_label = st.segmented_control(
                    "Geometry",
                    options=("Smooth", "Kink"),
                    key=_widget_key("node_mode"),
                    width="stretch",
                )
                with st.expander("Details · optional", expanded=False):
                    st.caption(
                        "Descriptions, dependencies, collaborators, evidence, "
                        "visibility and tags remain outside this first geometry test."
                    )
                submitted = st.form_submit_button(
                    f"{action_verb} {definition['label'].lower()}",
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
                    geometry = geometry_for_importance(str(importance))
                    existing = next(
                        (
                            event
                            for event in events
                            if str(event["id"]) == str(editing_id)
                        ),
                        None,
                    )
                    event_record: dict[str, object] = {
                        "id": (
                            str(existing["id"]) if existing else uuid4().hex
                        ),
                        "type": str(pending_type),
                        "title": clean_title,
                        "time_parameter": preview_parameter,
                        "date_value": preview_date.isoformat(),
                        "time_basis": "date",
                        "interval_start": ROADMAP_START.isoformat(),
                        "interval_end": ROADMAP_END.isoformat(),
                        "importance": str(importance),
                        "node_mode": str(node_mode_label).lower(),
                        "energy_offset": geometry["energy_offset"],
                        "alignment_offset": 0.0,
                        "influence_width": geometry["influence_width"],
                        "interval_status": "active",
                        "created_at": (
                            str(existing["created_at"])
                            if existing
                            else date.today().isoformat()
                        ),
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
                        "title": "Trajectory updated",
                        "detail": (
                            f"{definition['label']} anchored at "
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
    st.markdown(
        f"""
        <div class="timeline-field-note">
          <span>Build your path · drag to orbit · scroll to zoom</span>
          <span>{'simulated collective traces' if show_collective else 'personal alignment neutral'}</span>
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
        '<div class="timeline-dock-label">Place a move</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="timeline_core_moves"):
        _render_move_row(CORE_EVENT_TYPE_KEYS, pending_type)

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
        st.success(
            "Trajectory integrated for this session. No record has been saved.",
            icon="✅",
        )

    if show_inspector and placed_events:
        with st.sidebar:
            st.divider()
            selected_id = st.selectbox(
                "Inspect move",
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
                  {html.escape(str(selected_event['importance']))} ·
                  {html.escape(str(selected_event['node_mode']).title())}
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
