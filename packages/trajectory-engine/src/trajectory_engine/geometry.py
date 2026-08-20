"""UI-independent piecewise-Hermite geometry for trajectory reasoning.

The engine retains its v2 coordinate order: x is normalised time, y is the
uncertainty state (formerly entropy/alignment), and z is energy. Presentation
maps this to (time, energy, uncertainty). Placed events are hard interpolation nodes. The user never supplies
an arbitrary 3D point; semantic inputs deterministically generate every node.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil, cos, exp, pi, sin
from typing import Mapping, Sequence


Point = tuple[float, float, float]
Slope = tuple[float, float]

START_POINT: Point = (0.0, 0.0, 0.08)
END_POINT: Point = (1.0, 0.0, 0.24)
START_TANGENT: Slope = (0.0, 0.75)
PLANNED_END_TANGENT: Slope = (0.0, 0.0)

EVENT_TYPES: dict[str, dict[str, str]] = {
    "release": {"label": "Release", "glyph": "★", "color": "#f6d365"},
    "event": {"label": "Event", "glyph": "●", "color": "#80d6c3"},
    "gateway": {
        "label": "Information gateway",
        "glyph": "◈",
        "color": "#d6a8ff",
        "description": "A moment when information is exchanged.",
    },
    "action": {"label": "Action", "glyph": "▲", "color": "#ff8b69"},
    "update": {"label": "Update", "glyph": "■", "color": "#9ca8ff"},
    "milestone": {"label": "Milestone", "glyph": "▼", "color": "#e8f27c"},
    "merge": {
        "label": "Merge",
        "glyph": "⋈",
        "color": "#f3a6c8",
        "description": "Bring two workstreams or trajectories together.",
    },
    "share_resources": {
        "label": "Share resources",
        "glyph": "⇄",
        "color": "#82c7ff",
        "description": "Exchange capacity, time, materials or access.",
    },
    "acquire_resources": {
        "label": "Acquire resources",
        "glyph": "⇣",
        "color": "#7bd6a6",
        "description": (
            "Bring missing money, people, tools, space, access or materials "
            "into the plan."
        ),
    },
    "delegate": {
        "label": "Delegate",
        "glyph": "↱",
        "color": "#f0a97a",
        "description": (
            "Transfer responsibility or authority to another person, team "
            "or agent."
        ),
    },
    "wait": {
        "label": "Wait",
        "glyph": "◷",
        "color": "#aab4bd",
        "description": "Hold position until conditions change.",
    },
    "prepare": {
        "label": "Prepare",
        "glyph": "◒",
        "color": "#ffbd78",
        "description": "Build readiness for a later move.",
    },
    "get_intelligence": {
        "label": "Get intelligence",
        "glyph": "⌾",
        "color": "#a8e6cf",
        "description": "Gather information before deciding what comes next.",
    },
    "synchronise": {
        "label": "Synchronise",
        "glyph": "⟳",
        "color": "#c8b6ff",
        "description": "Align timing or state across actors.",
    },
}

CORE_EVENT_TYPE_KEYS = (
    "release",
    "event",
    "gateway",
    "action",
    "update",
    "milestone",
)
PLANNING_PRIMITIVE_KEYS = (
    "merge",
    "share_resources",
    "acquire_resources",
    "delegate",
    "wait",
    "prepare",
    "get_intelligence",
    "synchronise",
)

INFLUENCE_SCALES: dict[str, dict[str, float]] = {
    "Local": {"energy_offset": 0.14, "influence_width": 0.08},
    "Structural": {"energy_offset": 0.28, "influence_width": 0.14},
    "Dominant": {"energy_offset": 0.44, "influence_width": 0.22},
}

# Read compatibility for pre-RC0 plans and callers. New documents use
# ``influence_scale`` and the Local/Structural/Dominant vocabulary.
LEGACY_INFLUENCE_SCALES = {
    "Signal": "Local",
    "Lever": "Structural",
    "Threshold": "Dominant",
}
IMPORTANCE_LEVELS = INFLUENCE_SCALES

UNCERTAINTY_STRENGTHS: dict[str, dict[str, float]] = {
    "Light": {"radius": 0.045, "opacity": 0.22},
    "Marked": {"radius": 0.090, "opacity": 0.16},
    "Strong": {"radius": 0.160, "opacity": 0.11},
}

DIRECTIONAL_MODES = ("gradually", "abruptly")
TOPOLOGY_MODES = ("continuation", "branching")
NODE_MODES = ("smooth", "kink", "jump", "bifurcation")
LANDING_MODES = ("open", "guided", "planned")


@dataclass(frozen=True)
class ControlNode:
    """One hard point in the piecewise spline."""

    point: Point
    directional_mode: str = "gradually"
    influence_width: float = 0.0
    event_id: str | None = None


def date_for_parameter(
    parameter: float,
    *,
    start_date: date,
    end_date: date,
) -> date:
    """Map s in [0, 1] to the roadmap interval."""

    if end_date <= start_date:
        raise ValueError("The roadmap end date must follow its start date.")
    bounded = min(1.0, max(0.0, float(parameter)))
    days = (end_date - start_date).days
    return start_date + timedelta(days=round(days * bounded))


def parameter_for_date(
    value: date,
    *,
    start_date: date,
    end_date: date,
) -> float:
    """Map an authoritative date to its normalised roadmap parameter."""

    if end_date <= start_date:
        raise ValueError("The roadmap end date must follow its start date.")
    return (value - start_date).days / (end_date - start_date).days


def relative_time_label(
    parameter: float,
    *,
    start_date: date,
    end_date: date,
) -> str:
    """Return adaptive participant language for one slider position."""

    span_days = (end_date - start_date).days
    if span_days <= 0:
        raise ValueError("The roadmap end date must follow its start date.")
    bounded = min(1.0, max(0.0, float(parameter)))
    elapsed_days = round(span_days * bounded)

    if bounded >= 0.98:
        return "Landing horizon"
    if bounded <= 0.08 or elapsed_days <= min(30, span_days * 0.12):
        return "Soon"
    if bounded <= 0.25:
        return "This season"
    if elapsed_days <= 365 or bounded <= 0.55:
        return "This year"
    year_number = max(2, ceil(elapsed_days / 365))
    return f"Year {year_number}"


def geometry_for_influence(influence_scale: str) -> dict[str, float]:
    """Return deformation amplitude and temporal radius for one scale."""

    canonical = LEGACY_INFLUENCE_SCALES.get(influence_scale, influence_scale)
    try:
        return dict(INFLUENCE_SCALES[canonical])
    except KeyError as exc:
        raise ValueError(f"Unknown influence scale: {influence_scale}") from exc


def geometry_for_importance(importance: str) -> dict[str, float]:
    """Compatibility alias for pre-RC0 callers."""

    return geometry_for_influence(importance)


def directional_mode(event: Mapping[str, object]) -> str:
    """Return the canonical regularity choice from current or legacy data."""

    authored = str(event.get("directional_mode") or "").strip().lower()
    if authored in DIRECTIONAL_MODES:
        return authored
    legacy = str(event.get("node_mode") or "smooth").strip().lower()
    return "abruptly" if legacy in {"kink", "jump"} else "gradually"


def topology_mode(event: Mapping[str, object]) -> str:
    """Return the canonical topology choice from current or legacy data."""

    authored = str(event.get("topology_mode") or "").strip().lower()
    if authored in TOPOLOGY_MODES:
        return authored
    return (
        "branching"
        if str(event.get("node_mode") or "").strip().lower()
        == "bifurcation"
        else "continuation"
    )


def primitive_plot_label(event: Mapping[str, object]) -> str:
    """Combine semantic glyph and authored title for direct plot reading."""

    event_type = str(event.get("type") or "event")
    definition = EVENT_TYPES.get(event_type, EVENT_TYPES["event"])
    title = str(event.get("title") or definition["label"]).strip()
    return f"{definition['glyph']} {title}"


def reconcile_event_dates(
    events: Sequence[Mapping[str, object]],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    """Reconcile dates without silently deleting out-of-interval events."""

    reconciled: list[dict[str, object]] = []
    for source in events:
        event = dict(source)
        basis = str(event.get("time_basis") or "date")
        if basis == "relative":
            parameter = float(event["time_parameter"])
            event["date_value"] = date_for_parameter(
                parameter,
                start_date=start_date,
                end_date=end_date,
            ).isoformat()
            event["interval_status"] = "active"
        else:
            raw_date = event.get("date_value")
            if not raw_date:
                raise ValueError("Date-authored events require date_value.")
            authored_date = date.fromisoformat(str(raw_date))
            interval_is_unchanged = (
                str(event.get("interval_start") or "") == start_date.isoformat()
                and str(event.get("interval_end") or "") == end_date.isoformat()
                and event.get("time_parameter") is not None
            )
            parameter = (
                float(event["time_parameter"])
                if interval_is_unchanged
                else parameter_for_date(
                    authored_date,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
            event["time_parameter"] = parameter
            event["interval_status"] = (
                "active" if 0.0 <= parameter <= 1.0 else "outside"
            )
        event["interval_start"] = start_date.isoformat()
        event["interval_end"] = end_date.isoformat()
        reconciled.append(event)
    return reconciled


def active_events(
    events: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Return active placed events in strict chronological order."""

    active = [
        dict(event)
        for event in events
        if str(event.get("interval_status") or "active") == "active"
    ]
    active.sort(key=lambda event: float(event["time_parameter"]))
    for previous, current in zip(active, active[1:]):
        if abs(
            float(current["time_parameter"])
            - float(previous["time_parameter"])
        ) < 1e-7:
            raise ValueError("Two events cannot occupy the same time parameter.")
    return active


def _baseline_energy(parameter: float) -> float:
    return START_POINT[2] + ((END_POINT[2] - START_POINT[2]) * parameter)


def control_nodes(
    events: Sequence[Mapping[str, object]],
) -> list[ControlNode]:
    """Build start, hard event, and landing nodes."""

    nodes = [ControlNode(point=START_POINT)]
    for event in active_events(events):
        event_type = str(event["type"])
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")
        direction = directional_mode(event)
        if direction not in DIRECTIONAL_MODES:
            raise ValueError(f"Unknown directional mode: {direction}")
        parameter = float(event["time_parameter"])
        if not 0.0 < parameter < 1.0:
            raise ValueError("Placed events must sit inside the roadmap interval.")
        nodes.append(
            ControlNode(
                point=(
                    parameter,
                    float(
                        event.get("uncertainty_effect")
                        if event.get("uncertainty_effect") is not None
                        else event.get("alignment_offset") or 0.0
                    ),
                    _baseline_energy(parameter)
                    + float(event["energy_offset"]),
                ),
                directional_mode=direction,
                influence_width=float(event["influence_width"]),
                event_id=str(event["id"]),
            )
        )
    nodes.append(ControlNode(point=END_POINT))
    return nodes


def _secant(left: ControlNode, right: ControlNode) -> Slope:
    span = right.point[0] - left.point[0]
    if span <= 0:
        raise ValueError("Spline nodes must be strictly ordered in time.")
    return (
        (right.point[1] - left.point[1]) / span,
        (right.point[2] - left.point[2]) / span,
    )


def node_tangents(
    nodes: Sequence[ControlNode],
    *,
    landing_mode: str = "open",
    planned_end_tangent: Slope = PLANNED_END_TANGENT,
) -> list[tuple[Slope, Slope]]:
    """Return separate incoming/outgoing slopes for every node."""

    if landing_mode not in LANDING_MODES:
        raise ValueError(f"Unknown landing mode: {landing_mode}")
    if len(nodes) < 2:
        raise ValueError("A spline requires start and end nodes.")

    secants = [_secant(left, right) for left, right in zip(nodes, nodes[1:])]
    tangents: list[tuple[Slope, Slope]] = []

    tangents.append((START_TANGENT, START_TANGENT))
    for index in range(1, len(nodes) - 1):
        previous_slope = secants[index - 1]
        next_slope = secants[index]
        node = nodes[index]
        if node.directional_mode == "abruptly":
            tangents.append((previous_slope, next_slope))
            continue

        left = nodes[index - 1].point
        right = nodes[index + 1].point
        span = right[0] - left[0]
        centred = (
            (right[1] - left[1]) / span,
            (right[2] - left[2]) / span,
        )
        # Broader, more important events flatten the tangent around their hard
        # node so their deformation reorganises more of the neighbouring path.
        tangent_scale = max(0.38, 1.0 - (2.7 * node.influence_width))
        smooth_tangent = (
            centred[0] * tangent_scale,
            centred[1] * tangent_scale,
        )
        tangents.append((smooth_tangent, smooth_tangent))

    if landing_mode == "open":
        end_tangent = secants[-1]
    elif landing_mode == "guided":
        # The pilot landing plane is level in uncertainty/energy. Direction
        # within the plane remains open while the arrival slope is flattened.
        end_tangent = (0.0, 0.0)
    else:
        end_tangent = planned_end_tangent
    tangents.append((end_tangent, end_tangent))
    return tangents


def _hermite_value(
    value_0: float,
    value_1: float,
    slope_0: float,
    slope_1: float,
    *,
    span: float,
    local_parameter: float,
) -> float:
    u = local_parameter
    h00 = (2 * u**3) - (3 * u**2) + 1
    h10 = u**3 - (2 * u**2) + u
    h01 = (-2 * u**3) + (3 * u**2)
    h11 = u**3 - u**2
    return (
        (h00 * value_0)
        + (h10 * span * slope_0)
        + (h01 * value_1)
        + (h11 * span * slope_1)
    )


def _segment_point(
    left: ControlNode,
    right: ControlNode,
    left_outgoing: Slope,
    right_incoming: Slope,
    local_parameter: float,
) -> Point:
    span = right.point[0] - left.point[0]
    x = left.point[0] + (span * local_parameter)
    y = _hermite_value(
        left.point[1],
        right.point[1],
        left_outgoing[0],
        right_incoming[0],
        span=span,
        local_parameter=local_parameter,
    )
    z = _hermite_value(
        left.point[2],
        right.point[2],
        left_outgoing[1],
        right_incoming[1],
        span=span,
        local_parameter=local_parameter,
    )
    return x, y, z


def trajectory_point(
    parameter: float,
    events: Sequence[Mapping[str, object]],
    *,
    landing_mode: str = "open",
) -> Point:
    """Evaluate the piecewise trajectory at one normalised time."""

    bounded = min(1.0, max(0.0, float(parameter)))
    nodes = control_nodes(events)
    tangents = node_tangents(nodes, landing_mode=landing_mode)
    for index, (left, right) in enumerate(zip(nodes, nodes[1:])):
        if bounded <= right.point[0] or index == len(nodes) - 2:
            span = right.point[0] - left.point[0]
            local = (bounded - left.point[0]) / span
            return _segment_point(
                left,
                right,
                tangents[index][1],
                tangents[index + 1][0],
                local,
            )
    return END_POINT


def sample_trajectory(
    events: Sequence[Mapping[str, object]],
    *,
    landing_mode: str = "open",
    samples_per_segment: int = 36,
) -> tuple[list[float], list[float], list[float]]:
    """Sample every Hermite segment without duplicating hard nodes."""

    if samples_per_segment < 3:
        raise ValueError("At least three samples per segment are required.")
    nodes = control_nodes(events)
    tangents = node_tangents(nodes, landing_mode=landing_mode)
    points: list[Point] = []
    for index, (left, right) in enumerate(zip(nodes, nodes[1:])):
        start_index = 0 if index == 0 else 1
        for sample_index in range(start_index, samples_per_segment):
            local = sample_index / (samples_per_segment - 1)
            points.append(
                _segment_point(
                    left,
                    right,
                    tangents[index][1],
                    tangents[index + 1][0],
                    local,
                )
            )
    return (
        [point[0] for point in points],
        [point[1] for point in points],
        [point[2] for point in points],
    )


def binary_branch_stems(
    events: Sequence[Mapping[str, object]],
    *,
    landing_mode: str = "open",
    samples: int = 52,
) -> tuple[dict[str, object], ...]:
    """Generate two visible futures from the first RC0 branch point.

    RC0 keeps post-branch primitives common to both visual stems. Assigning
    primitives to an individual branch is deliberately deferred, but the split
    is topological in the rendered plan: there is one incoming trajectory and
    two outgoing traces with stable branch identities.
    """

    if samples < 3:
        raise ValueError("A branch needs at least three samples.")
    branch_event = next(
        (
            event
            for event in active_events(events)
            if topology_mode(event) == "branching"
        ),
        None,
    )
    if branch_event is None:
        return ()

    start = float(branch_event["time_parameter"])
    span = 1.0 - start
    influence_radius = float(
        branch_event.get("influence_radius")
        or branch_event.get("influence_width")
        or 0.14
    )
    separation = max(0.09, influence_radius * 0.9)
    raw_labels = branch_event.get("branch_labels") or ()
    labels: list[tuple[str, str]] = []
    if isinstance(raw_labels, Sequence) and not isinstance(raw_labels, str):
        for index, item in enumerate(raw_labels[:2]):
            if isinstance(item, Mapping):
                labels.append(
                    (
                        str(item.get("id") or f"{branch_event['id']}:{index + 1}"),
                        str(item.get("label") or f"Option {chr(65 + index)}"),
                    )
                )
            else:
                labels.append(
                    (f"{branch_event['id']}:{index + 1}", str(item))
                )
    while len(labels) < 2:
        index = len(labels)
        labels.append(
            (f"{branch_event['id']}:{index + 1}", f"Option {chr(65 + index)}")
        )

    stems: list[dict[str, object]] = []
    for branch_index, sign in enumerate((-1.0, 1.0)):
        x_values: list[float] = []
        y_values: list[float] = []
        z_values: list[float] = []
        for sample_index in range(samples):
            progress = sample_index / (samples - 1)
            parameter = start + (span * progress)
            x_value, y_value, z_value = trajectory_point(
                parameter,
                events,
                landing_mode=landing_mode,
            )
            if directional_mode(branch_event) == "abruptly":
                divergence = progress
            else:
                divergence = progress**2 * (3.0 - (2.0 * progress))
            x_values.append(x_value)
            y_values.append(y_value + (sign * separation * divergence))
            z_values.append(z_value)
        branch_id, label = labels[branch_index]
        stems.append(
            {
                "id": branch_id,
                "parent_id": str(branch_event["id"]),
                "label": label,
                "x": x_values,
                "y": y_values,
                "z": z_values,
            }
        )
    return tuple(stems)


def event_points(
    events: Sequence[Mapping[str, object]],
) -> tuple[list[float], list[float], list[float]]:
    """Return hard-node coordinates; the curve passes through each exactly."""

    points = [node.point for node in control_nodes(events)[1:-1]]
    return (
        [point[0] for point in points],
        [point[1] for point in points],
        [point[2] for point in points],
    )


def uncertainty_geometry(strength: str) -> dict[str, float]:
    """Return deterministic radius and alpha for a semantic strength."""

    try:
        return dict(UNCERTAINTY_STRENGTHS[strength])
    except KeyError as error:
        raise ValueError(f"Unknown uncertainty strength: {strength}") from error


def uncertainty_profile(
    parameter: float,
    *,
    center: float,
    temporal_width: float,
    profile_mode: str = "balanced",
) -> float:
    """Evaluate the chosen local radius profile over one interval."""

    if not 0.0 < temporal_width < 1.0:
        raise ValueError("Uncertainty width must be between zero and one.")
    if profile_mode not in {"balanced", "expands", "contracts"}:
        raise ValueError(f"Unknown uncertainty profile: {profile_mode}")
    half_width = temporal_width / 2.0
    local = (float(parameter) - float(center)) / half_width
    if local < -1.0 or local > 1.0:
        return 0.0
    progress = (local + 1.0) / 2.0
    smooth_progress = progress**2 * (3.0 - (2.0 * progress))
    if profile_mode == "expands":
        return smooth_progress
    if profile_mode == "contracts":
        return 1.0 - smooth_progress
    if abs(local) >= 1.0:
        return 0.0
    return exp(1.0 - (1.0 / (1.0 - local**2)))


def uncertainty_radius(
    parameter: float,
    chunk: Mapping[str, object],
) -> float:
    """Return the local isotropic uncertainty radius for one chunk."""

    profile = uncertainty_profile(
        parameter,
        center=float(chunk["center_parameter"]),
        temporal_width=float(chunk["temporal_width"]),
        profile_mode=str(chunk.get("profile_mode") or "balanced"),
    )
    return float(chunk["radius"]) * profile


def uncertainty_envelope_points(
    x_values: Sequence[float],
    y_values: Sequence[float],
    z_values: Sequence[float],
    chunk: Mapping[str, object],
    *,
    radial_fraction: float,
    angle_fraction: float,
) -> tuple[
    list[float | None],
    list[float | None],
    list[float | None],
]:
    """Offset a local trace around the unchanged centreline."""

    if not (
        len(x_values) == len(y_values)
        and len(y_values) == len(z_values)
    ):
        raise ValueError("Trajectory coordinates must have equal lengths.")
    if not 0.0 <= radial_fraction <= 1.0:
        raise ValueError("Radial fraction must sit between zero and one.")

    angle = 2.0 * pi * float(angle_fraction)
    direction_y = cos(angle)
    direction_z = sin(angle)
    envelope_x: list[float | None] = []
    envelope_y: list[float | None] = []
    envelope_z: list[float | None] = []
    for x_value, y_value, z_value in zip(x_values, y_values, z_values):
        radius = uncertainty_radius(float(x_value), chunk)
        if radius <= 1e-7:
            envelope_x.append(None)
            envelope_y.append(None)
            envelope_z.append(None)
            continue
        offset = radius * radial_fraction
        envelope_x.append(float(x_value))
        envelope_y.append(float(y_value) + (offset * direction_y))
        envelope_z.append(float(z_value) + (offset * direction_z))
    return envelope_x, envelope_y, envelope_z


def uncertainty_tube_mesh(
    x_values: Sequence[float],
    y_values: Sequence[float],
    z_values: Sequence[float],
    chunk: Mapping[str, object],
    *,
    radial_fraction: float = 1.0,
    directions: int = 14,
) -> dict[str, list[float] | list[int]]:
    """Build an approximate 3D tube with smooth local entry and exit."""

    if directions < 6:
        raise ValueError("An uncertainty tube needs at least six directions.")
    if not 0.0 < radial_fraction <= 1.0:
        raise ValueError("Radial fraction must sit between zero and one.")
    if not (
        len(x_values) == len(y_values)
        and len(y_values) == len(z_values)
    ):
        raise ValueError("Trajectory coordinates must have equal lengths.")

    rings: list[tuple[float, float, float, float]] = []
    for x_value, y_value, z_value in zip(x_values, y_values, z_values):
        radius = uncertainty_radius(float(x_value), chunk) * radial_fraction
        if radius > 1e-7:
            rings.append(
                (
                    float(x_value),
                    float(y_value),
                    float(z_value),
                    radius,
                )
            )

    mesh_x: list[float] = []
    mesh_y: list[float] = []
    mesh_z: list[float] = []
    for x_value, y_value, z_value, radius in rings:
        for direction in range(directions):
            angle = 2.0 * pi * direction / directions
            mesh_x.append(x_value)
            mesh_y.append(y_value + (radius * cos(angle)))
            mesh_z.append(z_value + (radius * sin(angle)))

    face_i: list[int] = []
    face_j: list[int] = []
    face_k: list[int] = []
    for ring_index in range(max(0, len(rings) - 1)):
        current = ring_index * directions
        following = (ring_index + 1) * directions
        for direction in range(directions):
            next_direction = (direction + 1) % directions
            face_i.extend((current + direction, current + direction))
            face_j.extend((following + direction, following + next_direction))
            face_k.extend((following + next_direction, current + next_direction))

    return {
        "x": mesh_x,
        "y": mesh_y,
        "z": mesh_z,
        "i": face_i,
        "j": face_j,
        "k": face_k,
    }


def kink_indicators(
    events: Sequence[Mapping[str, object]],
    *,
    landing_mode: str = "open",
) -> list[tuple[Point, Point, Point]]:
    """Return restrained incoming/node/outgoing tangent indicators."""

    nodes = control_nodes(events)
    tangents = node_tangents(nodes, landing_mode=landing_mode)
    indicators: list[tuple[Point, Point, Point]] = []
    for index, node in enumerate(nodes[1:-1], start=1):
        if node.directional_mode != "abruptly":
            continue
        left_span = node.point[0] - nodes[index - 1].point[0]
        right_span = nodes[index + 1].point[0] - node.point[0]
        indicator_span = min(0.035, left_span * 0.22, right_span * 0.22)
        incoming, outgoing = tangents[index]
        before = (
            node.point[0] - indicator_span,
            node.point[1] - (incoming[0] * indicator_span),
            node.point[2] - (incoming[1] * indicator_span),
        )
        after = (
            node.point[0] + indicator_span,
            node.point[1] + (outgoing[0] * indicator_span),
            node.point[2] + (outgoing[1] * indicator_span),
        )
        indicators.append((before, node.point, after))
    return indicators


def expanded_bounds(
    current: Mapping[str, Sequence[float]],
    *,
    y_values: Sequence[float],
    z_values: Sequence[float],
    padding: float = 0.08,
) -> dict[str, list[float]]:
    """Expand stable session bounds when needed; never contract them."""

    y_range = list(current.get("y") or (-0.32, 0.32))
    z_range = list(current.get("z") or (0.0, 0.78))
    if y_values:
        y_range[0] = min(y_range[0], min(y_values) - padding)
        y_range[1] = max(y_range[1], max(y_values) + padding)
    if z_values:
        z_range[0] = min(z_range[0], min(z_values) - padding)
        z_range[1] = max(z_range[1], max(z_values) + padding)
    return {"y": y_range, "z": z_range}
