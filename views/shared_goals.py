"""Public shared-goal index and coordination surface."""

from __future__ import annotations

from datetime import datetime
import html
from uuid import uuid4

import plotly.graph_objects as go
import streamlit as st
import yaml

from protocol.shared_goals import (
    AGENT_COLOURS,
    AGENT_TYPES,
    build_goal_trajectory,
    build_shared_goal,
    new_goal_id,
)
from protocol.timeline import sample_trajectory
from protocol.trajectory_schema import build_trajectory_document, load_trajectory_yaml
from storage import get_repository, repository_mode


ACTIVE_PLAN_KEY = "timeline_active_benchmark"
SHARED_CONTEXT_KEY = "shared_goal_context"


def _active_document() -> dict[str, object] | None:
    plan = st.session_state.get(ACTIVE_PLAN_KEY)
    if not isinstance(plan, dict):
        return None
    return build_trajectory_document(
        plan=plan,
        primitives=st.session_state.get("timeline_game_events", []),
        uncertainty=st.session_state.get("timeline_game_uncertainties", []),
    )


def _trajectory_payload(contribution: dict[str, object]) -> dict[str, object]:
    payload = contribution.get("trajectory_payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _temporal_summary(contribution: dict[str, object]) -> tuple[str, str]:
    plan = _trajectory_payload(contribution).get("plan") or {}
    return (
        str(plan.get("temporal_mode") or "unspecified").title(),
        str(plan.get("landing_mode") or "unspecified").title(),
    )


def _comparison_figure(
    trajectories: list[dict[str, object]],
    *,
    overlay: bool,
) -> go.Figure:
    figure = go.Figure()
    total = len(trajectories)
    for index, contribution in enumerate(trajectories):
        payload = _trajectory_payload(contribution)
        primitives = payload.get("primitives") or []
        x, uncertainty, energy = sample_trajectory(primitives, samples_per_segment=90)
        row = 0 if overlay else total - index - 1
        vertical = [row + value * (1.0 if overlay else 0.48) for value in energy]
        temporal, landing = _temporal_summary(contribution)
        colour = str(contribution.get("colour") or AGENT_COLOURS[index % len(AGENT_COLOURS)])
        figure.add_trace(go.Scatter(
            x=x,
            y=vertical,
            customdata=list(zip(uncertainty, energy)),
            mode="lines",
            name=str(contribution["agent_display_name"]),
            line={"color": colour, "width": 4},
            hovertemplate=(
                f"{html.escape(str(contribution['agent_display_name']))}<br>"
                f"{html.escape(temporal)} time · {html.escape(landing)} landing<br>"
                "normalized horizon %{x:.0%}<br>uncertainty %{customdata[0]:.3f}"
                "<br>energy %{customdata[1]:.3f}<extra></extra>"
            ),
        ))
    yaxis: dict[str, object] = {"gridcolor": "#243832", "zeroline": False}
    if overlay:
        yaxis.update({"title": "ENERGY", "tickformat": ".2f"})
    else:
        yaxis.update({
            "tickvals": list(range(total)),
            "ticktext": [str(item["agent_display_name"]) for item in reversed(trajectories)],
        })
    figure.update_layout(
        height=max(360, 180 + (1 if overlay else total) * 105),
        margin={"l": 12, "r": 12, "t": 28, "b": 30},
        paper_bgcolor="#020707",
        plot_bgcolor="#020707",
        font={"color": "#dce7e1"},
        xaxis={
            "range": [0, 1],
            "title": "NORMALIZED NOW → LANDING",
            "tickformat": ".0%",
            "gridcolor": "#1c2d27",
        },
        yaxis=yaxis,
        legend={"orientation": "h", "y": 1.1},
    )
    return figure


def _begin_goal_plan(goal: dict[str, object]) -> None:
    for key in tuple(st.session_state):
        if str(key).startswith("sketch_plan_"):
            del st.session_state[key]
    st.session_state[SHARED_CONTEXT_KEY] = {"goal_id": str(goal["goal_id"])}
    st.session_state["sketch_plan_created_at"] = datetime.now().astimezone().isoformat()
    st.session_state["sketch_plan_plan_id"] = uuid4().hex
    st.session_state["sketch_plan_stage"] = "identity"
    st.switch_page("views/test_sketch_plan.py")


def _open_in_planner(contribution: dict[str, object]) -> None:
    payload = _trajectory_payload(contribution)
    plan = dict(payload["plan"])
    for key in tuple(st.session_state):
        if str(key).startswith("timeline_game_"):
            del st.session_state[key]
    st.session_state[ACTIVE_PLAN_KEY] = plan
    st.session_state["timeline_game_events"] = list(payload.get("primitives") or [])
    st.session_state["timeline_game_uncertainties"] = list(payload.get("uncertainty") or [])
    st.session_state["timeline_game_landing_mode"] = {
        "open": "Open", "guided": "Guided", "planned": "Planned"
    }.get(str(plan.get("landing_mode") or "open"), "Open")
    st.session_state[SHARED_CONTEXT_KEY] = {
        "goal_id": str(contribution["goal_id"]),
        "trajectory_id": str(contribution["trajectory_id"]),
        "agent_id": str(contribution["agent_id"]),
        "agent_display_name": str(contribution["agent_display_name"]),
        "agent_type": str(contribution.get("agent_type") or "person"),
        "colour": str(contribution.get("colour") or AGENT_COLOURS[0]),
    }
    st.switch_page("views/test_timeline_game.py")


st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
.stApp { background:#020707; color:#edf2ed; }
.block-container { max-width:1180px; padding:2.2rem 2rem 4rem; }
h1,h2,h3,p,label { color:#edf2ed !important; }
.shared-kicker { color:#dfe875; text-transform:uppercase; letter-spacing:.15em; font-size:.75rem; }
.shared-card { border:1px solid #2a4038; background:#06100d; padding:1rem; margin:.6rem 0; }
.shared-card small { color:#8ba097; }
</style>
""", unsafe_allow_html=True)

repository = get_repository()
goal_id = str(st.query_params.get("goal_id") or "").strip()
try:
    goal = repository.get_shared_goal(goal_id) if goal_id else None
except (KeyError, RuntimeError):
    st.error(
        "Shared persistence is not provisioned in the configured Notion "
        "workspace yet. Run the v3 ProtocolHack database bootstrap first."
    )
    st.stop()

if goal_id and not goal:
    st.error("This shared goal could not be found.")
    if st.button("← All shared goals"):
        st.query_params.clear()
        st.rerun()
    st.stop()

if not goal:
    st.markdown('<div class="shared-kicker">Collaborative trajectories · public playground</div>', unsafe_allow_html=True)
    st.title("Shared goals")
    st.caption("One agreed objective, independently authored trajectories, one observable field.")

    with st.expander("Create shared goal", expanded=False):
        with st.form("create_shared_goal"):
            title = st.text_input("Goal title", placeholder="AI Summit 2027 Panel / Intervention")
            objective = st.text_area("Shared objective", placeholder="How can we organise a panel on protocols and collaborative planning?")
            creator = st.text_input("Your agent ID", placeholder="andres")
            generated_id = st.text_input("Goal ID", value=new_goal_id())
            if st.form_submit_button("Create public shared goal", type="primary"):
                if not title.strip():
                    st.error("Enter a goal title before creating the shared goal.")
                    st.stop()
                try:
                    created = repository.create_shared_goal(build_shared_goal(
                        goal_id=generated_id,
                        title=title,
                        objective=objective,
                        created_by_agent_id=creator,
                    ))
                except (KeyError, RuntimeError) as exc:
                    st.error(f"Shared persistence is unavailable: {exc}")
                else:
                    st.query_params["goal_id"] = str(created["goal_id"])
                    st.rerun()

    try:
        goals = repository.list_shared_goals()
    except (KeyError, RuntimeError):
        st.error(
            "Shared persistence is not provisioned in the configured Notion "
            "workspace yet. Run the v3 ProtocolHack database bootstrap first."
        )
        st.stop()
    if not goals:
        st.info("No open shared goals yet.")
    for index, listed_goal in enumerate(goals):
        contributions = repository.list_goal_trajectories(str(listed_goal["goal_id"]))
        st.markdown(
            f'<div class="shared-card"><h3>{html.escape(str(listed_goal["title"]))}</h3>'
            f'<p>{html.escape(str(listed_goal.get("objective") or ""))}</p>'
            f'<small>{len(contributions)} trajectories · Created by '
            f'{html.escape(str(listed_goal.get("created_by_agent_id") or "unspecified agent"))}</small></div>',
            unsafe_allow_html=True,
        )
        open_column, sketch_column = st.columns(2)
        with open_column:
            if st.button("Open goal", key=f"open_goal_{index}", width="stretch"):
                st.query_params["goal_id"] = str(listed_goal["goal_id"])
                st.rerun()
        with sketch_column:
            if st.button("Sketch my trajectory", key=f"sketch_goal_{index}", width="stretch"):
                _begin_goal_plan(listed_goal)
    st.caption(f"Shared persistence · {repository_mode()}")
    st.stop()

trajectories = repository.list_goal_trajectories(str(goal["goal_id"]))
if st.button("← All shared goals"):
    st.query_params.clear()
    st.rerun()
st.markdown('<div class="shared-kicker">Shared coordination surface</div>', unsafe_allow_html=True)
st.title(str(goal["title"]))
st.write(str(goal.get("objective") or ""))
st.code(str(goal["goal_id"]), language=None)
st.caption(f"{len(trajectories)} independent trajectories · Public experimental goal")

action_one, action_two = st.columns(2)
with action_one:
    if st.button("Sketch my trajectory", type="primary", width="stretch"):
        _begin_goal_plan(goal)
with action_two:
    show_share = st.toggle("Share existing trajectory", value=False)

if show_share:
    source_choice = st.radio(
        "Choose the trajectory to share",
        ("Current local trajectory", "Trajectory YAML"),
        horizontal=True,
    )
    document = _active_document() if source_choice == "Current local trajectory" else None
    if source_choice == "Current local trajectory" and document is None:
        st.warning("No local trajectory is currently open in this session.")
    if source_choice == "Trajectory YAML":
        selected_file = st.file_uploader("Choose trajectory YAML", type=("yaml", "yml"))
        if selected_file is not None:
            try:
                document = load_trajectory_yaml(selected_file.getvalue())
            except (ValueError, yaml.YAMLError) as exc:
                st.error(f"This trajectory cannot be opened: {exc}")
    with st.form("share_existing_trajectory"):
        display_name = st.text_input("Agent display name")
        agent_id = st.text_input("Agent ID")
        agent_type = st.selectbox("Agent type", AGENT_TYPES)
        colour = st.selectbox("Trajectory colour", AGENT_COLOURS)
        share = st.form_submit_button(
            "Share trajectory with this goal",
            type="primary",
            disabled=document is None or not display_name.strip() or not agent_id.strip(),
        )
    if share and document is not None:
        try:
            repository.record_goal_trajectory(build_goal_trajectory(
                document,
                goal_id=str(goal["goal_id"]),
                agent_id=agent_id,
                agent_display_name=display_name,
                agent_type=agent_type,
                colour=colour,
                source="imported_existing_plan",
            ))
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Trajectory shared. Your local copy remains separate.")
            st.rerun()

trajectory_tab, history_tab, compare_tab, overlay_tab = st.tabs(("Trajectories", "Shared history", "Compare", "Overlay"))
with trajectory_tab:
    if not trajectories:
        st.info("No trajectories have been shared with this goal yet.")
    for index, contribution in enumerate(trajectories):
        temporal, landing = _temporal_summary(contribution)
        st.markdown(
            f'<div class="shared-card"><h3>{html.escape(str(contribution["agent_display_name"]))}</h3>'
            f'<p>{html.escape(str(contribution["title"]))}</p>'
            f'<small>{html.escape(temporal)} time · {html.escape(landing)} landing · '
            f'revision {int(contribution.get("revision") or 1)} · updated '
            f'{html.escape(str(contribution.get("updated_at") or ""))}</small></div>',
            unsafe_allow_html=True,
        )
        with st.expander("Inspect", expanded=False):
            payload = _trajectory_payload(contribution)
            st.write(str((payload.get("plan") or {}).get("goal_statement") or ""))
            st.caption(
                f"{len(payload.get('primitives') or [])} moves · "
                f"{len(payload.get('uncertainty') or [])} uncertainty regions"
            )
            if st.button("Open in the individual planner", key=f"edit_contribution_{index}"):
                _open_in_planner(contribution)

with history_tab:
    shared_history: list[tuple[str, dict[str, object], dict[str, object]]] = []
    for contribution in trajectories:
        for primitive in _trajectory_payload(contribution).get("primitives") or []:
            if str(primitive.get("status") or "Planned") != "Planned":
                shared_history.append((str(primitive.get("actual_timestamp") or ""), contribution, primitive))
    shared_history.sort(key=lambda item: item[0], reverse=True)
    if not shared_history:
        st.info("No realised moves have been shared yet.")
    for _, contribution, primitive in shared_history:
        glyph = {"Done": "✓", "Changed": "~", "Skipped": "⊘", "Cancelled": "×"}.get(str(primitive.get("status")), "○")
        st.markdown(
            f'<div class="shared-card"><small>{html.escape(str(contribution["agent_display_name"]))} · '
            f'{html.escape(str(contribution["title"]))}</small><h3>{glyph} '
            f'{html.escape(str(primitive.get("title") or "Untitled move"))}</h3><p>'
            f'{html.escape(str(primitive.get("status") or ""))} · '
            f'{html.escape(str(primitive.get("actual_timestamp") or "No actual time"))}</p></div>',
            unsafe_allow_html=True,
        )

with compare_tab:
    if trajectories:
        st.caption("Each row preserves one trajectory. Horizontal position is normalized from Now (0) to Landing (1).")
        st.plotly_chart(_comparison_figure(trajectories, overlay=False), width="stretch", key="shared_compare")
    else:
        st.info("Share at least one trajectory to compare paths.")

with overlay_tab:
    if trajectories:
        st.caption("First look only: no consensus score, averaging, or synthesis is applied.")
        st.plotly_chart(_comparison_figure(trajectories, overlay=True), width="stretch", key="shared_overlay")
    else:
        st.info("Share at least one trajectory to overlay paths.")
