"""Semantic plan and realisation operations for trajectories."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Mapping


QUALITATIVE_TIME_ANCHORS: tuple[tuple[str, float], ...] = (
    ("Now", 0.0),
    ("Soon", 0.12),
    ("Later", 0.35),
    ("Sometime", 0.58),
    ("Eventually", 0.80),
    ("Landing", 1.0),
)

GUIDED_HORIZONS: dict[str, tuple[str, int]] = {
    "A few weeks": ("Within a few weeks", 42),
    "This season": ("This season", 90),
    "The coming year": ("During the coming year", 365),
    "Before a summit": ("Before the next summit", 180),
}

TIME_UNITS_IN_DAYS: dict[str, float] = {
    "Hours": 1 / 24,
    "Days": 1,
    "Weeks": 7,
    "Months": 30,
    "Years": 365,
}

REALIZATION_STATUSES: tuple[str, ...] = (
    "Planned", "Done", "Changed", "Skipped", "Cancelled"
)
REALIZED_STATUSES = frozenset(REALIZATION_STATUSES[1:])


def resolve_actual_timestamp(
    *,
    now: datetime,
    exact: datetime | None = None,
    ago_value: int | None = None,
    ago_unit: str | None = None,
) -> tuple[str, str]:
    """Resolve an authored realisation time while retaining its expression."""

    if exact is not None:
        return exact.astimezone().isoformat(), "exact"
    if ago_value is not None and ago_unit:
        days = duration_in_days(ago_value, ago_unit)
        return (now - timedelta(days=days)).isoformat(), duration_label(ago_value, ago_unit) + " ago"
    return now.astimezone().isoformat(), "now"


def now_parameter(
    plan: Mapping[str, object],
    primitives: list[Mapping[str, object]],
    *,
    today: date,
) -> float:
    """Locate Now without changing either clock or the authored trajectory."""

    if str(plan.get("temporal_mode") or "linear") == "linear":
        start = date.fromisoformat(str(plan.get("start_date") or today.isoformat()))
        end_value = plan.get("end_date") or plan.get("target_date")
        end = date.fromisoformat(str(end_value)) if end_value else start + timedelta(days=max(1, int(plan.get("horizon_days") or 365)))
        return min(1.0, max(0.0, (today - start).days / max(1, (end - start).days)))
    realised = [
        float(item.get("time_parameter") or 0.0)
        for item in primitives
        if str(item.get("status") or "Planned") in REALIZED_STATUSES
    ]
    return min(1.0, max(realised, default=0.0))


def realize_primitive(
    primitive: Mapping[str, object],
    *,
    status: str,
    changed_at: datetime,
    actual_timestamp: str | None = None,
    actual_time_expression: str = "",
    note: str = "",
    revision_needed: bool = False,
) -> dict[str, object]:
    """Append the prior realisation state and return an updated primitive."""

    if status not in REALIZATION_STATUSES:
        raise ValueError(f"Unknown realisation status: {status}")
    if status == "Changed" and not note.strip():
        raise ValueError("Changed primitives require a realisation note.")
    updated = dict(primitive)
    history = list(updated.get("realization_history") or [])
    previous = {
        "status": str(updated.get("status") or "Planned"),
        "actual_timestamp": updated.get("actual_timestamp"),
        "actual_time_expression": str(updated.get("actual_time_expression") or ""),
        "realization_note": str(updated.get("realization_note") or ""),
        "trajectory_revision_needed": bool(updated.get("trajectory_revision_needed", False)),
        "revised_at": changed_at.astimezone().isoformat(),
    }
    history.append(previous)
    updated.update({
        "status": status,
        "actual_timestamp": actual_timestamp if status in {"Done", "Changed", "Skipped"} else None,
        "actual_time_expression": actual_time_expression if actual_timestamp else "",
        "realization_note": note.strip(),
        "trajectory_revision_needed": bool(revision_needed),
        "realization_history": history,
        "modified_at": changed_at.astimezone().isoformat(),
    })
    return updated


def duration_in_days(value: int, unit: str) -> int:
    """Convert a player-authored duration to a usable geometry interval."""

    try:
        factor = TIME_UNITS_IN_DAYS[unit]
    except KeyError as exc:
        raise ValueError(f"Unknown time unit: {unit}") from exc
    return max(1, round(max(1, int(value)) * factor))


def duration_label(value: int, unit: str) -> str:
    """Return compact participant-facing duration language."""

    clean_value = max(1, int(value))
    clean_unit = str(unit).strip().lower()
    if clean_value == 1 and clean_unit.endswith("s"):
        clean_unit = clean_unit[:-1]
    return f"{clean_value} {clean_unit}"


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def linear_time_ticks(
    *,
    start_date: date,
    end_date: date,
    unit: str,
) -> tuple[tuple[float, str], ...]:
    """Return elapsed-time-proportional ticks for the linear timeline."""

    if end_date <= start_date:
        raise ValueError("Linear time requires an end after its start.")
    span_days = (end_date - start_date).days
    if unit == "Months":
        ticks: list[tuple[float, str]] = [(0.0, start_date.strftime("%d %b"))]
        boundary = _next_month(start_date)
        while boundary < end_date:
            ticks.append(
                ((boundary - start_date).days / span_days, boundary.strftime("%b"))
            )
            boundary = _next_month(boundary)
        ticks.append((1.0, end_date.strftime("%d %b")))
        return tuple(ticks)
    if unit == "Years":
        ticks = [(0.0, start_date.strftime("%d %b %Y"))]
        boundary = date(start_date.year + 1, 1, 1)
        while boundary < end_date:
            ticks.append(
                ((boundary - start_date).days / span_days, str(boundary.year))
            )
            boundary = date(boundary.year + 1, 1, 1)
        ticks.append((1.0, end_date.strftime("%d %b %Y")))
        return tuple(ticks)

    elapsed_days = list(
        dict.fromkeys(
            round(span_days * fraction)
            for fraction in (0, 0.25, 0.5, 0.75, 1)
        )
    )
    if unit == "Weeks":
        labels = [f"Week {days / 7:g}" for days in elapsed_days]
    elif unit == "Hours":
        labels = [f"Hour {days * 24}" for days in elapsed_days]
    else:
        labels = [f"Day {days}" for days in elapsed_days]
    return tuple(
        (days / span_days, label)
        for days, label in zip(elapsed_days, labels)
    )


def qualitative_time_label(parameter: float) -> str:
    """Return the nearest ordered qualitative anchor without exposing s."""

    bounded = min(1.0, max(0.0, float(parameter)))
    return min(
        QUALITATIVE_TIME_ANCHORS,
        key=lambda anchor: abs(anchor[1] - bounded),
    )[0]


def build_plan_payload(
    *,
    plan_id: str = "",
    title: str,
    description: str,
    initial_condition: str,
    goal_statement: str,
    goal_conditions: str,
    landing_mode: str,
    temporal_mode: str,
    created_at: str,
    guided_horizon: str | None = None,
    guided_value: int | None = None,
    guided_unit: str | None = None,
    fixed_kind: str | None = None,
    fixed_value: int | None = None,
    fixed_unit: str | None = None,
    fixed_date: date | None = None,
    linear_unit: str | None = None,
) -> dict[str, object]:
    """Build the editor handoff without inventing an authored start date."""

    clean_title = title.strip()
    clean_start = initial_condition.strip()
    clean_goal = goal_statement.strip()
    if not clean_title or not clean_start or not clean_goal:
        raise ValueError("Title, initial condition and goal are required.")
    if landing_mode not in {"Open", "Guided", "Fixed"}:
        raise ValueError(f"Unknown landing mode: {landing_mode}")
    if temporal_mode not in {"Qualitative", "Linear"}:
        raise ValueError(f"Unknown temporal mode: {temporal_mode}")

    creation_moment = datetime.fromisoformat(created_at)
    start_day = creation_moment.date()
    payload: dict[str, object] = {
        "id": plan_id.strip() or f"plan-{creation_moment.timestamp():.0f}",
        "source_kind": "plan",
        "title": clean_title,
        "description": description.strip(),
        "initial_condition": clean_start,
        "goal_statement": clean_goal,
        "goal_conditions": goal_conditions.strip(),
        "destination_label": clean_goal,
        "created_at": creation_moment.isoformat(),
        "start_date": start_day.isoformat(),
        "temporal_mode": temporal_mode.lower(),
        "time_unit": linear_unit or "",
        "qualitative_anchors": QUALITATIVE_TIME_ANCHORS,
        "guided_setup": True,
        "axis_y_label": "Uncertainty",
        "suggested_moves": (),
        "prompt": (
            "What should happen—not necessarily first, but off the top of "
            "your head?"
        ),
    }

    if landing_mode == "Open":
        payload.update(
            {
                "landing_mode": "open",
                "horizon_label": "Open horizon",
                "horizon_days": 365,
                "duration_label": "No target date",
                "target_date": None,
            }
        )
    elif landing_mode == "Guided":
        if guided_value is not None and guided_unit in TIME_UNITS_IN_DAYS:
            clean_guided_value = max(1, int(guided_value))
            clean_guided_unit = str(guided_unit)
            horizon_label = duration_label(
                clean_guided_value,
                clean_guided_unit,
            )
            horizon_days = duration_in_days(
                clean_guided_value,
                clean_guided_unit,
            )
        elif guided_horizon in GUIDED_HORIZONS:
            horizon_label, horizon_days = GUIDED_HORIZONS[guided_horizon]
            clean_guided_value = horizon_days
            clean_guided_unit = "Days"
        else:
            raise ValueError("A guided duration and unit are required.")
        payload.update(
            {
                "landing_mode": "guided",
                "horizon_label": horizon_label,
                "horizon_days": horizon_days,
                "duration_label": horizon_label,
                "guided_value": clean_guided_value,
                "guided_unit": clean_guided_unit,
                "target_date": None,
            }
        )
    else:
        if fixed_kind == "Date":
            if fixed_date is None or fixed_date <= start_day:
                raise ValueError("The fixed landing date must follow now.")
            end_day = fixed_date
            fixed_duration_label = fixed_date.strftime("%d %b %Y")
        elif fixed_kind == "Duration":
            if fixed_value is None or fixed_unit not in TIME_UNITS_IN_DAYS:
                raise ValueError("A fixed duration and unit are required.")
            horizon_days = duration_in_days(fixed_value, fixed_unit)
            end_day = start_day + timedelta(days=horizon_days)
            fixed_duration_label = f"In {fixed_value} {fixed_unit.lower()}"
        else:
            raise ValueError("A fixed landing needs a date or duration.")
        payload.update(
            {
                "landing_mode": "planned",
                "horizon_label": fixed_duration_label,
                "horizon_days": (end_day - start_day).days,
                "duration_label": fixed_duration_label,
                "target_date": end_day.isoformat(),
                "end_date": end_day.isoformat(),
            }
        )

    return payload


def plan_summary(payload: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Return the compact onboarding review in a stable order."""

    landing_copy = {
        "open": "Open",
        "guided": "Guided",
        "planned": "Fixed",
    }
    return (
        ("Plan", str(payload["title"])),
        ("Now", str(payload["initial_condition"])),
        ("Goal", str(payload["goal_statement"])),
        ("Landing", landing_copy[str(payload["landing_mode"])]),
        ("Time language", str(payload["temporal_mode"]).title()),
    )
