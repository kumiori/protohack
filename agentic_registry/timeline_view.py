"""Streamlit renderer for the compiler-owned protocol timeline artifact.

This module is intentionally a thin view adapter.  It never reads the registry
source and does not decide which records are events or versions; those semantic
decisions belong to :mod:`agentic_registry.compiler`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape
from typing import Any, Callable, Iterable, Mapping, Sequence

from agentic_registry import load_compiled_artifacts


_FUNCTION_TITLES = {
    "tool_context": "Tool context",
    "agent_communication": "Agent communication",
    "delegated_authority": "Delegated authority",
    "commerce": "Commerce",
    "machine_payment": "Machine payment",
}

_SHAPE_GLYPHS = {
    "diamond": "◆",
    "triangle": "▲",
    "circle": "●",
    "hexagon": "⬢",
    "square": "■",
    "star": "★",
}

_EVENT_COLOURS = {
    "public_launch": "#2563eb",
    "governance_adoption": "#7c3aed",
    "stewardship_transfer": "#ea580c",
    "specification_release": "#0891b2",
    "archival": "#64748b",
    "production_deployment": "#15803d",
}

_STEWARDSHIP_OFFSET = 0.2
_GOVERNANCE_OFFSET = -0.2


@dataclass(frozen=True)
class TimelinePayload:
    """Renderer-ready data, retaining the compiler artifact as the authority."""

    items: tuple[dict[str, Any], ...]
    groups: tuple[dict[str, Any], ...]
    item_index: Mapping[str, Mapping[str, Any]]
    supplemental_versions: tuple[Mapping[str, Any], ...]
    unresolved_items: tuple[Mapping[str, Any], ...]
    included_protocol_ids: tuple[str, ...]
    observation_date: str
    regimes: tuple[Mapping[str, Any], ...]
    transitions: tuple[Mapping[str, Any], ...]
    transition_index: Mapping[str, Mapping[str, Any]]
    transition_cards: Mapping[str, Mapping[str, Any]]


def load_timeline_artifact() -> Mapping[str, Any]:
    """Load only the validated timeline side of the compiler contract."""

    return load_compiled_artifacts().timeline


def protocol_options(timeline: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Return stable protocol identifiers and labels, including superseded ones."""

    return tuple(
        (
            str(protocol["id"]),
            f'{protocol["acronym"]} — {protocol["name"]}'
            + (
                " (superseded)"
                if str(protocol.get("status", "")).lower() == "superseded"
                else ""
            ),
        )
        for protocol in sorted(
            timeline.get("protocols", ()), key=lambda row: row.get("display_order", 99)
        )
    )


def filter_timeline_records(
    timeline: Mapping[str, Any], protocol_ids: Iterable[str] | None = None
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
]:
    """Filter compiler-classified event, supplemental, and unresolved records."""

    admitted = {protocol_id for protocol_id, _ in protocol_options(timeline)}
    selected = admitted if protocol_ids is None else admitted.intersection(protocol_ids)

    events = tuple(
        item
        for item in timeline.get("items", ())
        if str((item.get("protocol") or {}).get("id")) in selected
    )
    supplemental = tuple(
        item
        for item in timeline.get("supplemental_versions", ())
        if str(item.get("protocol_id")) in selected
    )
    unresolved = tuple(
        item
        for item in timeline.get("unresolved_items", ())
        if _record_protocol_id(item) in selected
    )
    return events, supplemental, unresolved


def build_timeline_payload(
    timeline: Mapping[str, Any],
    protocol_ids: Iterable[str] | None = None,
    transition_cards: Mapping[str, Any] | None = None,
) -> TimelinePayload:
    """Adapt the validated artifact to one shared protocol-lane time field."""

    options = protocol_options(timeline)
    admitted_ids = tuple(protocol_id for protocol_id, _ in options)
    requested_ids = None if protocol_ids is None else set(protocol_ids)
    selected = (
        admitted_ids
        if requested_ids is None
        else tuple(protocol_id for protocol_id in admitted_ids if protocol_id in requested_ids)
    )
    events, supplemental, unresolved = filter_timeline_records(timeline, selected)

    protocol_rows = {
        str(protocol["id"]): protocol for protocol in timeline.get("protocols", ())
    }
    ordered_protocols = tuple(
        protocol_rows[protocol_id]
        for protocol_id in selected
        if protocol_id in protocol_rows
    )
    vis_group_ids = {
        str(protocol["id"]): index
        for index, protocol in enumerate(ordered_protocols, start=1)
    }
    groups = tuple(
        {
            "id": vis_group_ids[str(protocol["id"])],
            "protocol_id": str(protocol["id"]),
            "acronym": str(protocol.get("acronym") or ""),
            "function_label": _FUNCTION_TITLES.get(
                str(protocol.get("layer")),
                str(protocol.get("layer") or "").replace("_", " ").title(),
            ),
            "content": (
                '<div class="protocol-lane-label">'
                f'<b>{escape(str(protocol.get("acronym") or ""))}</b>'
                f'<span>{escape(_FUNCTION_TITLES.get(str(protocol.get("layer")), str(protocol.get("layer") or "").replace("_", " ").title()))}</span>'
                "</div>"
            ),
            "title": str(protocol.get("name") or ""),
            "order": int(protocol.get("display_order", 99)),
        }
        for protocol in ordered_protocols
    )

    rendered_events = tuple(
        _vis_item(
            event,
            vis_group_ids[str((event.get("protocol") or {})["id"])],
            vis_item_id,
        )
        for vis_item_id, event in enumerate(events, start=1)
    )
    event_index = {
        str(vis_item_id): event
        for vis_item_id, event in enumerate(events, start=1)
    }
    next_item_id = len(rendered_events) + 1
    release_ticks: list[dict[str, Any]] = []
    for version in supplemental:
        protocol_id = str(version.get("protocol_id") or "")
        released = version.get("date") or {}
        if protocol_id not in vis_group_ids or not released.get("start"):
            continue
        release_ticks.append(
            _vis_release_tick(version, vis_group_ids[protocol_id], next_item_id)
        )
        next_item_id += 1

    lifelines: list[dict[str, Any]] = []
    for protocol in ordered_protocols:
        lifeline = protocol.get("lifeline") or {}
        start = (lifeline.get("start") or {}).get("start")
        end = (lifeline.get("end") or {}).get("start")
        if not start or not end:
            continue
        lifelines.append(
            _vis_lifeline(
                protocol,
                vis_group_ids[str(protocol["id"])],
                next_item_id,
            )
        )
        next_item_id += 1

    # An undated supplemental version remains supplemental semantically, but it
    # belongs in the off-axis unresolved-date list visually.
    unresolved_supplemental = tuple(
        item for item in supplemental if not (item.get("date") or {}).get("start")
    )

    regimes = tuple(
        regime
        for regime in timeline.get("regimes", ())
        if str(regime.get("protocol_id") or "") in selected
    )
    selected_set = set(selected)
    transitions = tuple(
        transition
        for transition in timeline.get("transitions", ())
        if {
            str(value) for value in transition.get("affected_protocol_ids", ())
        }.intersection(selected_set)
    )
    transition_index = {
        str(transition.get("id") or ""): transition for transition in transitions
    }
    card_index = _transition_card_index(transition_cards)
    selected_cards = {
        transition_id: card_index.get(transition_id, transition)
        for transition_id, transition in transition_index.items()
    }

    return TimelinePayload(
        items=tuple(lifelines) + tuple(release_ticks) + rendered_events,
        groups=groups,
        item_index=event_index,
        supplemental_versions=supplemental,
        unresolved_items=unresolved + unresolved_supplemental,
        included_protocol_ids=selected,
        observation_date=str((timeline.get("metadata") or {}).get("observed_at") or ""),
        regimes=regimes,
        transitions=transitions,
        transition_index=transition_index,
        transition_cards=selected_cards,
    )


def selected_item_id(selection: Any) -> str | None:
    """Extract an item id from the component's bidirectional return value."""

    if selection is None:
        return None
    if isinstance(selection, (str, int)):
        return str(selection)
    if not isinstance(selection, Mapping):
        return None
    if selection.get("id") is not None:
        return str(selection["id"])
    nested = selection.get("item")
    if isinstance(nested, Mapping) and nested.get("id") is not None:
        return str(nested["id"])
    if nested is not None and not isinstance(nested, Mapping):
        return str(nested)
    return None


def selected_plot_event_id(selection: Any) -> str | None:
    """Extract the compiler event id from a Streamlit Plotly selection."""

    if selection is None:
        return None
    if not isinstance(selection, Mapping):
        return None
    selected = selection.get("selection", selection)
    if not isinstance(selected, Mapping):
        return None
    points = selected.get("points") or []
    if not points or not isinstance(points[0], Mapping):
        return None
    custom = points[0].get("customdata")
    if isinstance(custom, Sequence) and not isinstance(custom, str):
        custom = custom[0] if custom else None
    return str(custom) if custom else None


def evidence_card(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete, display-neutral evidence card for one event."""

    protocol = item.get("protocol") or {}
    date = item.get("date") or {}
    return {
        "id": str(item.get("id") or ""),
        "protocol": str(protocol.get("acronym") or protocol.get("name") or ""),
        "protocol_status": str(protocol.get("status") or ""),
        "event_type": str(item.get("event_type") or ""),
        "date": _date_label(date),
        "date_precision": str(date.get("precision") or "unknown"),
        "summary": str(item.get("summary") or ""),
        "actors": tuple(str(actor.get("label") or actor.get("id") or "") for actor in item.get("actors", ())),
        "version": _version_label(item.get("version")),
        "evidence_state": (
            str(item["evidence_state"]) if item.get("evidence_state") else None
        ),
        "evidence_resolution": str(item.get("evidence_resolution") or "unknown"),
        "evidence": tuple(
            {
                "id": str(source.get("id") or ""),
                "claim": str(source.get("claim") or ""),
                "authority": str(source.get("authority") or ""),
                "publisher": str(source.get("publisher") or ""),
                "title": str(source.get("title") or ""),
                "published_at": _source_date_label(source, "published_at"),
                "observed_at": str(source.get("observed_at") or "Unknown"),
                "url": str(source.get("url") or ""),
            }
            for source in item.get("evidence", ())
        ),
    }


def transition_card(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return a display-neutral before/operation/after institutional card.

    Participant labels come from the compiled transition. Raw actor identifiers
    are intentionally excluded from this view contract.
    """

    effective = item.get("effective") or {}
    source_protocols = tuple(
        str(protocol.get("acronym") or protocol.get("name") or "")
        for protocol in item.get("source_protocols", ())
        if protocol.get("acronym") or protocol.get("name")
    )
    target_protocol = item.get("target_protocol") or {}
    target_label = str(
        target_protocol.get("acronym") or target_protocol.get("name") or ""
    )
    protocols = tuple(
        dict.fromkeys(
            label
            for label in (
                *source_protocols,
                target_label,
                *(
                    str(regime.get("protocol_acronym") or "")
                    for regime in (*item.get("before", ()), *item.get("after", ()))
                ),
            )
            if label
        )
    )
    kind_label = _human_label(item.get("kind") or "institutional transition")
    mechanism_label = _human_label(item.get("mechanism") or "")
    return {
        "id": str(item.get("id") or ""),
        "title": (
            f'{" → ".join(source_protocols + ((target_label,) if target_label else ()))} · '
            f"{kind_label}"
            if source_protocols or target_label
            else f'{" / ".join(protocols)} · {kind_label}'
            if protocols
            else kind_label
        ),
        "protocols": protocols,
        "before": tuple(_display_regime(regime) for regime in item.get("before", ())),
        "operation": {
            "kind": kind_label,
            "mechanism": mechanism_label or None,
            "effective": _transition_date_label(effective),
            "date_mode": str(effective.get("mode") or "point"),
            "summary": str(item.get("summary") or ""),
            "governance_instrument": item.get("governance_instrument"),
            "decision_rules": item.get("decision_rules"),
            "participation_conditions": item.get("participation_conditions"),
            "access_conditions": item.get("access_conditions"),
            "effects": tuple(
                {
                    "asset": _human_label(effect.get("asset") or ""),
                    "effect": _human_label(effect.get("effect") or ""),
                }
                for effect in item.get("transfer_effect", ())
            ),
            "continuities": tuple(str(value) for value in item.get("continuities", ())),
            "discontinuities": tuple(
                str(value) for value in item.get("discontinuities", ())
            ),
        },
        "after": tuple(_display_regime(regime) for regime in item.get("after", ())),
        "missing_fields": tuple(
            _human_label(value) for value in item.get("missing_fields", ())
        ),
        "evidence": tuple(
            _display_evidence(source) for source in item.get("evidence", ())
        ),
    }


def build_timeline_figure(payload: TimelinePayload) -> Any:
    """Build the single shared temporal field from compiler-owned records."""

    import plotly.graph_objects as go

    figure = go.Figure()
    groups = sorted(payload.groups, key=lambda group: group.get("order", 99))
    y_by_protocol = {
        str(group["protocol_id"]): int(group["id"]) for group in groups
    }
    window_start = _timeline_window_start(payload.items)
    observation_date = payload.observation_date
    function_colours = {
        "Tool context": "rgba(49,92,70,.055)",
        "Agent communication": "rgba(37,99,235,.045)",
        "Delegated authority": "rgba(124,58,237,.045)",
        "Commerce": "rgba(21,128,61,.045)",
        "Machine payment": "rgba(180,83,9,.05)",
    }

    for group in groups:
        y = int(group["id"])
        figure.add_shape(
            type="rect",
            x0=window_start,
            x1=observation_date,
            y0=y - 0.43,
            y1=y + 0.43,
            fillcolor=function_colours.get(
                str(group.get("function_label")), "rgba(100,116,139,.035)"
            ),
            line={"width": 0},
            layer="below",
        )

    for item in payload.items:
        if "protocol-lifeline" not in str(item.get("className") or ""):
            continue
        closed = "protocol-lifeline-closed" in str(item.get("className") or "")
        figure.add_trace(
            go.Scatter(
                x=[item["start"], item["end"]],
                y=[item["group"], item["group"]],
                mode="lines",
                line={
                    "color": "#b45309" if closed else "#8a9790",
                    "width": 4 if closed else 3,
                },
                hovertemplate=f'{item.get("title") or "Protocol lifetime"}<extra></extra>',
                showlegend=False,
            )
        )

    for item in payload.items:
        if not item.get("release_id"):
            continue
        y = int(item["group"])
        figure.add_shape(
            type="line",
            x0=item["start"],
            x1=item["start"],
            y0=y - 0.16,
            y1=y + 0.16,
            line={"color": "#7c8982", "width": 1.5},
        )

    _add_regime_layers(
        figure,
        payload.regimes,
        y_by_protocol,
        observation_date,
    )

    symbol_by_type = {
        "public_launch": "diamond",
        "specification_release": "circle",
        "archival": "square",
        "production_deployment": "star",
    }
    per_protocol_count: dict[str, int] = {}
    events_by_type: dict[str, list[Mapping[str, Any]]] = {}
    for event in payload.item_index.values():
        events_by_type.setdefault(str(event.get("event_type") or "event"), []).append(
            event
        )

    for event_type in (
        "public_launch",
        "specification_release",
        "archival",
        "production_deployment",
    ):
        events = [
            event
            for event in events_by_type.get(event_type, [])
            if not _is_transition_archive_endpoint(event, payload.transitions)
        ]
        if not events:
            continue
        x_values: list[str] = []
        y_values: list[int] = []
        labels: list[str] = []
        positions: list[str] = []
        customdata: list[list[str]] = []
        hovertext: list[str] = []
        for event in events:
            protocol = event.get("protocol") or {}
            protocol_id = str(protocol.get("id") or "")
            date_value = event.get("date") or {}
            start = str(date_value.get("start") or "")
            end = str(date_value.get("end") or "")
            x_value = _date_midpoint(start, end) if end else start
            y = y_by_protocol[protocol_id]
            count = per_protocol_count.get(protocol_id, 0)
            per_protocol_count[protocol_id] = count + 1
            x_values.append(x_value)
            y_values.append(y)
            labels.append(_event_label(event))
            positions.append(
                _label_position(x_value, observation_date, count)
            )
            customdata.append([str(event.get("id") or "")])
            hovertext.append(str(event.get("summary") or ""))
            if end:
                figure.add_shape(
                    type="line",
                    x0=start,
                    x1=end,
                    y0=y,
                    y1=y,
                    line={
                        "color": _EVENT_COLOURS.get(event_type, "#475569"),
                        "width": 10,
                    },
                    opacity=0.16,
                )
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers+text",
                name=event_type.replace("_", " ").title(),
                text=labels,
                textposition=positions,
                textfont={"size": 10, "color": "#26332d"},
                customdata=customdata,
                hovertext=hovertext,
                hovertemplate=(
                    "<b>%{text}</b><br>%{x|%d %b %Y}<br>%{hovertext}"
                    "<extra></extra>"
                ),
                marker={
                    "symbol": symbol_by_type[event_type],
                    "size": 11,
                    "color": _EVENT_COLOURS.get(event_type, "#475569"),
                    "line": {"color": "#ffffff", "width": 1.2},
                },
                selected={"marker": {"size": 14, "opacity": 1}},
                unselected={"marker": {"opacity": 0.72}},
            )
        )

    _add_transition_marks(
        figure,
        payload.transitions,
        y_by_protocol,
    )

    figure.add_vline(
        x=observation_date,
        line={"color": "#8f6e42", "width": 1.5, "dash": "dot"},
        annotation_text=f"Observed {observation_date}",
        annotation_position="top left",
        annotation_font={"size": 10, "color": "#725633"},
    )
    figure.update_layout(
        height=max(470, len(groups) * 72 + 84),
        margin={"l": 128, "r": 12, "t": 72, "b": 44},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fbfaf6",
        hovermode="closest",
        clickmode="event+select",
        dragmode=False,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.08,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 10},
            "itemsizing": "constant",
        },
        xaxis={
            "range": [window_start, observation_date],
            "fixedrange": True,
            "showgrid": True,
            "gridcolor": "rgba(74,88,80,.12)",
            "tickformat": "%b\n%Y",
            "dtick": "M3",
            "showline": True,
            "linecolor": "rgba(74,88,80,.25)",
            "zeroline": False,
            "title": None,
        },
        yaxis={
            "tickmode": "array",
            "tickvals": [int(group["id"]) for group in groups],
            "ticktext": [
                f'<b>{group["acronym"]}</b><br>{group["function_label"]}'
                for group in groups
            ],
            "range": [len(groups) + 0.55, 0.45],
            "fixedrange": True,
            "showgrid": False,
            "zeroline": False,
        },
    )
    return figure


def _add_regime_layers(
    figure: Any,
    regimes: Sequence[Mapping[str, Any]],
    y_by_protocol: Mapping[str, int],
    observation_date: str,
) -> None:
    """Draw compiler-declared stewardship and governance regimes."""

    import plotly.graph_objects as go

    for regime in regimes:
        regime_type = str(regime.get("regime_type") or "")
        if regime_type not in {"stewardship", "governance"}:
            continue
        protocol_id = str(regime.get("protocol_id") or "")
        if protocol_id not in y_by_protocol:
            continue
        start = str((regime.get("valid_from") or {}).get("start") or "")
        end = str(
            (regime.get("valid_to") or {}).get("start") or observation_date or ""
        )
        if not start or not end:
            continue
        verified = str(regime.get("status") or "") == "verified"
        y = y_by_protocol[protocol_id] + (
            _STEWARDSHIP_OFFSET
            if regime_type == "stewardship"
            else _GOVERNANCE_OFFSET
        )
        participant_labels = tuple(
            str(participant.get("label") or "")
            for participant in regime.get("participants", ())
            if participant.get("label")
        )
        state_label = " · ".join(participant_labels) or _human_label(
            regime.get("status") or "unknown"
        )
        colour = (
            "#a55b16"
            if regime_type == "stewardship" and verified
            else "#6d4bc3"
            if regime_type == "governance" and verified
            else "#7c8982"
        )
        width = 6 if regime_type == "stewardship" else 2.5
        figure.add_trace(
            go.Scatter(
                x=[start, end],
                y=[y, y],
                mode="lines",
                line={
                    "color": colour,
                    "width": width,
                    "dash": "solid" if verified else "dot",
                },
                opacity=0.92 if verified else 0.5,
                name=(
                    "Stewardship regime"
                    if regime_type == "stewardship"
                    else "Governance regime"
                ),
                legendgroup=f"regime-{regime_type}",
                showlegend=False,
                hovertemplate=(
                    f'<b>{escape(str(regime.get("protocol_acronym") or ""))} '
                    f'{escape(_human_label(regime_type))}</b><br>'
                    f'{escape(state_label)}<br>{escape(start)} → {escape(end)}<br>'
                    f'Status: {escape(_human_label(regime.get("status") or "unknown"))}'
                    "<extra></extra>"
                ),
            )
        )
        if verified and regime_type == "stewardship" and participant_labels:
            figure.add_trace(
                go.Scatter(
                    x=[_date_midpoint(start, end)],
                    y=[y],
                    mode="text",
                    text=[" / ".join(participant_labels)],
                    textposition="top center",
                    textfont={"size": 8, "color": "#75400f"},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        if not verified:
            midpoint = _date_midpoint(start, end)
            figure.add_trace(
                go.Scatter(
                    x=[midpoint],
                    y=[y],
                    mode="markers+text",
                    marker={
                        "symbol": "circle-open",
                        "size": 8 if regime_type == "stewardship" else 6,
                        "color": "#68766f",
                    },
                    text=["?"],
                    textposition="middle center",
                    textfont={"size": 8, "color": "#4b5a53"},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )


def _add_transition_marks(
    figure: Any,
    transitions: Sequence[Mapping[str, Any]],
    y_by_protocol: Mapping[str, int],
) -> None:
    """Draw institutional marks with transition ids as selection payloads."""

    import plotly.graph_objects as go

    for transition in transitions:
        transition_id = str(transition.get("id") or "")
        effective = transition.get("effective") or {}
        start = str(effective.get("start") or "")
        end = str(effective.get("end") or "")
        if not transition_id or not start:
            continue
        kind = str(transition.get("kind") or "")
        if kind == "protocol_merger":
            _add_protocol_connector(
                figure, transition, y_by_protocol, transition_id, start
            )
            continue

        affected = [
            str(protocol_id)
            for protocol_id in transition.get("affected_protocol_ids", ())
            if str(protocol_id) in y_by_protocol
        ]
        for protocol_id in affected:
            base_y = y_by_protocol[protocol_id]
            after_regimes = tuple(transition.get("after", ()))
            has_stewardship = any(
                str(regime.get("protocol_id") or "") == protocol_id
                and regime.get("regime_type") == "stewardship"
                for regime in after_regimes
            )
            governance_regimes = tuple(
                regime
                for regime in after_regimes
                if str(regime.get("protocol_id") or "") == protocol_id
                and regime.get("regime_type") == "governance"
            )

            if kind == "stewardship_transfer" or has_stewardship:
                mark_date = _date_midpoint(start, end) if end else start
                if end:
                    figure.add_shape(
                        type="rect",
                        x0=start,
                        x1=end,
                        y0=base_y - 0.34,
                        y1=base_y + 0.34,
                        fillcolor="rgba(180,83,9,.12)",
                        line={"color": "rgba(180,83,9,.55)", "width": 1, "dash": "dot"},
                        layer="below",
                    )
                figure.add_trace(
                    go.Scatter(
                        x=[mark_date],
                        y=[base_y + _STEWARDSHIP_OFFSET],
                        mode="markers+text",
                        marker={
                            "symbol": "triangle-right-open" if end else "triangle-right",
                            "size": 13,
                            "color": "#b45309",
                            "line": {"color": "#ffffff", "width": 1},
                        },
                        text=["Transfer window" if end else "Transfer"],
                        textposition="bottom center",
                        textfont={"size": 9, "color": "#7a4214"},
                        customdata=[[transition_id]],
                        hovertext=[str(transition.get("summary") or "")],
                        hovertemplate=(
                            "<b>%{text}</b><br>%{hovertext}<extra></extra>"
                        ),
                        name="Stewardship transition",
                        showlegend=False,
                    )
                )

            for regime in governance_regimes:
                instrument = str(regime.get("governance_instrument") or "")
                instrument_date = str(
                    (regime.get("valid_from") or {}).get("start") or start
                )
                figure.add_trace(
                    go.Scatter(
                        x=[instrument_date],
                        y=[base_y + _GOVERNANCE_OFFSET],
                        mode="markers",
                        marker={
                            "symbol": "hexagon-open",
                            "size": 11,
                            "color": "#6d4bc3",
                            "line": {"color": "#ffffff", "width": 1},
                        },
                        customdata=[[transition_id]],
                        hovertext=[instrument or str(transition.get("summary") or "")],
                        hovertemplate=(
                            "<b>Governance instrument</b><br>%{hovertext}"
                            "<extra></extra>"
                        ),
                        name="Governance instrument",
                        showlegend=False,
                    )
                )


def _add_protocol_connector(
    figure: Any,
    transition: Mapping[str, Any],
    y_by_protocol: Mapping[str, int],
    transition_id: str,
    effective_date: str,
) -> None:
    """Draw compiler-declared source-to-target protocol direction and endpoint."""

    import plotly.graph_objects as go

    target = transition.get("target_protocol") or {}
    target_id = str(target.get("id") or "")
    target_y = y_by_protocol.get(target_id)
    for source in transition.get("source_protocols", ()):
        source_id = str(source.get("id") or "")
        source_y = y_by_protocol.get(source_id)
        source_label = str(source.get("acronym") or source.get("name") or "Source")
        target_label = str(
            target.get("acronym") or target.get("name") or "target protocol"
        )
        if source_y is not None:
            figure.add_trace(
                go.Scatter(
                    x=[effective_date],
                    y=[source_y],
                    mode="markers+text",
                    marker={
                        "symbol": "square",
                        "size": 13,
                        "color": "#9f432d",
                        "line": {"color": "#ffffff", "width": 1},
                    },
                    text=[f"{source_label} archived"],
                    textposition="bottom left",
                    textfont={"size": 9, "color": "#743323"},
                    customdata=[[transition_id]],
                    hovertext=[str(transition.get("summary") or "")],
                    hovertemplate="<b>%{text}</b><br>%{hovertext}<extra></extra>",
                    name="Protocol archive endpoint",
                    showlegend=False,
                )
            )
        if source_y is None or target_y is None:
            continue
        figure.add_annotation(
            x=effective_date,
            y=target_y,
            ax=effective_date,
            ay=source_y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text=f"{source_label} → {target_label}",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.1,
            arrowwidth=1.8,
            arrowcolor="#9f432d",
            font={"size": 9, "color": "#743323"},
            bgcolor="rgba(251,250,246,.82)",
            borderpad=2,
        )
        figure.add_trace(
            go.Scatter(
                x=[effective_date],
                y=[target_y],
                mode="markers",
                marker={
                    "symbol": "triangle-up",
                    "size": 10,
                    "color": "#9f432d",
                    "line": {"color": "#ffffff", "width": 1},
                },
                customdata=[[transition_id]],
                hovertext=[str(transition.get("summary") or "")],
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            )
        )


def _is_transition_archive_endpoint(
    event: Mapping[str, Any], transitions: Sequence[Mapping[str, Any]]
) -> bool:
    if event.get("event_type") != "archival":
        return False
    protocol_id = str((event.get("protocol") or {}).get("id") or "")
    event_start = str((event.get("date") or {}).get("start") or "")
    return any(
        transition.get("kind") == "protocol_merger"
        and str((transition.get("effective") or {}).get("start") or "")
        == event_start
        and protocol_id
        in {
            str(protocol.get("id") or "")
            for protocol in transition.get("source_protocols", ())
        }
        for transition in transitions
    )


def render_protocol_timeline(
    *,
    timeline: Mapping[str, Any] | None = None,
    transition_cards: Mapping[str, Any] | None = None,
    protocol_ids: Iterable[str] | None = None,
    key_prefix: str = "agentic_protocol_timeline",
    protocol_filter_key: str = "agentic_map_protocols",
    st_api: Any = None,
    timeline_component: Callable[..., Any] | None = None,
) -> TimelinePayload:
    """Render the timeline and evidence inspector.

    ``protocol_ids`` can be supplied by a page-level shared filter.  When it is
    omitted, this renderer creates the shared ``agentic_map_protocols`` filter
    itself so a graph view can consume the same selection.
    """

    if timeline is None:
        timeline = load_timeline_artifact()
    if st_api is None:
        import streamlit as st_api
    if timeline_component is None:
        timeline_component = st_api.plotly_chart

    options = protocol_options(timeline)
    labels = dict(options)
    if protocol_ids is None:
        selected_protocols = st_api.multiselect(
            "Protocols",
            options=[protocol_id for protocol_id, _ in options],
            default=[protocol_id for protocol_id, _ in options],
            format_func=lambda protocol_id: labels.get(protocol_id, protocol_id),
            key=protocol_filter_key,
            help="Compare one or more protocol histories on the same time axis.",
        )
    else:
        requested = set(protocol_ids)
        selected_protocols = [
            protocol_id for protocol_id, _ in options if protocol_id in requested
        ]

    payload = build_timeline_payload(
        timeline,
        selected_protocols,
        transition_cards=transition_cards,
    )
    st_api.caption(
        "One shared axis · one lane per protocol · the central line is technical · "
        "stewardship and governance occupy distinct institutional rails."
    )
    if not payload.items:
        st_api.info("No consequential events match this protocol selection.")
        _render_supplemental_versions(st_api, payload.supplemental_versions)
        _render_unresolved_items(st_api, payload.unresolved_items)
        return payload

    figure = build_timeline_figure(payload)
    selection = timeline_component(
        figure,
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        config={"displayModeBar": False, "scrollZoom": False},
        key=f"{key_prefix}_shared_canvas",
    )
    selected_record_id = selected_plot_event_id(selection)
    selected_item = next(
        (
            item
            for item in payload.item_index.values()
            if item.get("id") == selected_record_id
        ),
        None,
    )
    selected_transition = payload.transition_cards.get(selected_record_id or "")
    state = getattr(st_api, "session_state", None)
    state_key = f"{key_prefix}_selected_event"
    if (selected_item is not None or selected_transition is not None) and state is not None:
        state[state_key] = str(selected_record_id or "")
    if selected_item is None and selected_transition is None and state is not None:
        selected_record_id = state.get(state_key)
        selected_item = next(
            (
                item
                for item in payload.item_index.values()
                if item.get("id") == selected_record_id
            ),
            None,
        )
        selected_transition = payload.transition_cards.get(selected_record_id or "")
    if selected_item is not None:
        _render_evidence_card(st_api, evidence_card(selected_item))
    elif selected_transition is not None:
        _render_transition_card(st_api, transition_card(selected_transition))
    else:
        st_api.caption(
            "Select a technical event or institutional transition to inspect its evidence."
        )

    _render_supplemental_versions(st_api, payload.supplemental_versions)
    _render_unresolved_items(st_api, payload.unresolved_items)
    return payload


def _vis_item(
    event: Mapping[str, Any], vis_group_id: int, vis_item_id: int
) -> dict[str, Any]:
    protocol = event.get("protocol") or {}
    event_type = str(event.get("event_type") or "event")
    date = event.get("date") or {}
    mark_shape = str(event.get("mark_shape") or "circle")
    glyph = _SHAPE_GLYPHS.get(mark_shape, "●")
    colour = _EVENT_COLOURS.get(event_type, "#475569")
    precision = str(date.get("precision") or "unknown")
    type_label = _event_label(event)
    content = f'<span class="protocol-event-label">{glyph} {escape(type_label)}</span>'
    item = {
        # The wrapper's bundled react-visjs-timeline release silently drops
        # string item ids, so numeric adapter ids are mapped back through
        # ``item_index`` for evidence selection.
        "id": vis_item_id,
        "event_id": str(event["id"]),
        "editable": False,
        "content": content,
        "group": vis_group_id,
        "start": str(date["start"]),
        "title": escape(str(event.get("summary") or "")),
        "type": "point",
        "className": (
            f"protocol-event protocol-event-{event_type.replace('_', '-')} "
            f"protocol-date-precision-{precision.replace('_', '-')}"
        ),
        "style": _event_style(colour, precision),
    }
    if date.get("end"):
        item["end"] = str(date["end"])
        item["type"] = "range"
    return item


def _vis_release_tick(
    version: Mapping[str, Any], vis_group_id: int, vis_item_id: int
) -> dict[str, Any]:
    released = version.get("date") or {}
    return {
        "id": vis_item_id,
        "release_id": str(version.get("id") or ""),
        "group": vis_group_id,
        "start": str(released["start"]),
        "content": "",
        "title": escape(
            f'{version.get("protocol_acronym") or ""} {version.get("version") or ""} · minor release'
        ),
        "type": "box",
        "selectable": False,
        "editable": False,
        "className": "protocol-release-tick",
        "style": (
            "width:2px;height:13px;padding:0;border:0;border-radius:0;"
            "background:#8a9790;opacity:.62;"
        ),
    }


def _vis_lifeline(
    protocol: Mapping[str, Any], vis_group_id: int, vis_item_id: int
) -> dict[str, Any]:
    lifeline = protocol.get("lifeline") or {}
    start = lifeline.get("start") or {}
    end = lifeline.get("end") or {}
    target = lifeline.get("target_protocol") or {}
    end_label = (
        f'merged into {target.get("acronym")}'
        if lifeline.get("end_reason") == "merged_into" and target.get("acronym")
        else "registry observation date"
    )
    return {
        "id": vis_item_id,
        "group": vis_group_id,
        "start": str(start["start"]),
        "end": str(end["start"]),
        "content": "",
        "title": escape(
            f'{protocol.get("acronym") or ""} lifeline · {start.get("value") or "unknown"} → {end.get("value") or "unknown"} ({end_label})'
        ),
        "type": "background",
        "selectable": False,
        "editable": False,
        "className": (
            "protocol-lifeline protocol-lifeline-closed"
            if lifeline.get("end_reason") != "observation_date"
            else "protocol-lifeline"
        ),
        "style": (
            "background:linear-gradient(to bottom,transparent 48%,#aab5af 48%,"
            "#aab5af 52%,transparent 52%);opacity:.75;"
        ),
    }


def _transition_card_index(
    cards: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    """Accept either the compiler artifact or an already keyed card mapping."""

    if not cards:
        return {}
    card_rows = cards.get("cards")
    if isinstance(card_rows, Sequence) and not isinstance(card_rows, (str, bytes)):
        return {
            str(card.get("id") or ""): card
            for card in card_rows
            if isinstance(card, Mapping) and card.get("id")
        }
    return {
        str(transition_id): card
        for transition_id, card in cards.items()
        if isinstance(card, Mapping)
    }


def _display_regime(regime: Mapping[str, Any]) -> dict[str, Any]:
    participants = tuple(
        {
            "label": str(participant.get("label") or ""),
            "role": _human_label(participant.get("role") or ""),
        }
        for participant in regime.get("participants", ())
        if participant.get("label")
    )
    return {
        "protocol": str(regime.get("protocol_acronym") or ""),
        "regime_type": _human_label(regime.get("regime_type") or ""),
        "status": _human_label(regime.get("status") or "unknown"),
        "confidence": _human_label(regime.get("confidence") or "unknown"),
        "valid_from": _date_label(regime.get("valid_from") or {}),
        "valid_to": (
            _date_label(regime.get("valid_to") or {})
            if (regime.get("valid_to") or {}).get("start")
            else "Open"
        ),
        "participants": participants,
        "asset_scope": tuple(
            _human_label(value) for value in regime.get("asset_scope", ())
        ),
        "governance_instrument": regime.get("governance_instrument"),
        "decision_rules": regime.get("decision_rules"),
        "participation_conditions": regime.get("participation_conditions"),
        "access_conditions": regime.get("access_conditions"),
    }


def _display_evidence(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim": str(source.get("claim") or ""),
        "authority": _human_label(source.get("authority") or ""),
        "confidence": _human_label(source.get("confidence") or "unknown"),
        "evidence_state": _human_label(source.get("evidence_state") or "unknown"),
        "publisher": str(source.get("publisher") or ""),
        "title": str(source.get("title") or ""),
        "published_at": _source_date_label(source, "published_at"),
        "observed_at": str(source.get("observed_at") or "Unknown"),
        "url": str(source.get("url") or ""),
    }


def _render_transition_card(st_api: Any, card: Mapping[str, Any]) -> None:
    operation = card["operation"]
    with st_api.container(border=True):
        st_api.subheader(str(card["title"]))
        mechanism = (
            f' · {operation["mechanism"]}' if operation.get("mechanism") else ""
        )
        st_api.caption(
            f'{operation["effective"]} · {operation["kind"]}{mechanism}'
        )
        st_api.write(operation["summary"])

        st_api.markdown("**Before**")
        _render_regime_snapshots(st_api, card["before"])

        st_api.markdown("**Operation and effects**")
        for effect in operation["effects"]:
            st_api.write(f'{effect["asset"]}: {effect["effect"]}')
        for label, values in (
            ("Continuity", operation["continuities"]),
            ("Change", operation["discontinuities"]),
        ):
            for value in values:
                st_api.write(f"{label}: {value}")
        for label, field in (
            ("Governance instrument", "governance_instrument"),
            ("Decision rules", "decision_rules"),
            ("Participation conditions", "participation_conditions"),
            ("Access conditions", "access_conditions"),
        ):
            if operation.get(field):
                st_api.caption(f'{label}: {operation[field]}')

        st_api.markdown("**After**")
        _render_regime_snapshots(st_api, card["after"])

        if card["missing_fields"]:
            st_api.caption(
                "Not established in the registry: " + ", ".join(card["missing_fields"])
            )

        st_api.markdown("**Evidence**")
        for source in card["evidence"]:
            st_api.markdown(f'**Claim:** {escape(source["claim"])}')
            st_api.caption(
                f'Authority: {source["authority"]} · Publisher: {source["publisher"]} · '
                f'Published: {source["published_at"]} · Observed: {source["observed_at"]} · '
                f'State: {source["evidence_state"]}'
            )
            if source["url"]:
                st_api.link_button(
                    source["title"] or "Open primary source",
                    source["url"],
                )


def _render_regime_snapshots(
    st_api: Any, regimes: Sequence[Mapping[str, Any]]
) -> None:
    if not regimes:
        st_api.write("No compiled regime in this phase.")
        return
    for regime in regimes:
        heading = " · ".join(
            value
            for value in (regime["protocol"], regime["regime_type"], regime["status"])
            if value
        )
        st_api.write(heading)
        participants = ", ".join(
            f'{participant["label"]} ({participant["role"]})'
            if participant["role"]
            else participant["label"]
            for participant in regime["participants"]
        )
        details = [f'{regime["valid_from"]} → {regime["valid_to"]}']
        if participants:
            details.append(participants)
        if regime["asset_scope"]:
            details.append("Scope: " + ", ".join(regime["asset_scope"]))
        st_api.caption(" · ".join(details))


def _render_evidence_card(st_api: Any, card: Mapping[str, Any]) -> None:
    with st_api.container(border=True):
        st_api.subheader(
            f'{card["protocol"]} · '
            f'{str(card["event_type"]).replace("_", " ").title()}'
        )
        st_api.caption(
            f'{card["date"]} · precision: {card["date_precision"]} · '
            f'evidence resolution: {card["evidence_resolution"]}'
        )
        st_api.write(card["summary"])
        details = []
        if card["actors"]:
            details.append("Actors: " + ", ".join(card["actors"]))
        if card["version"]:
            details.append("Specification version: " + str(card["version"]))
        if card["protocol_status"]:
            details.append("Protocol status: " + str(card["protocol_status"]))
        if card["evidence_state"]:
            details.append("Authored evidence state: " + str(card["evidence_state"]))
        if details:
            st_api.caption(" · ".join(details))

        st_api.markdown("**Evidence**")
        for source in card["evidence"]:
            st_api.markdown(f'**Claim:** {escape(source["claim"])}')
            st_api.caption(
                f'Authority: {source["authority"]} · Publisher: {source["publisher"]} · '
                f'Published: {source["published_at"]} · Observed: {source["observed_at"]}'
            )
            if source["url"]:
                st_api.link_button(
                    source["title"] or "Open primary source",
                    source["url"],
                )


def _render_supplemental_versions(
    st_api: Any, versions: Sequence[Mapping[str, Any]]
) -> None:
    dated = [version for version in versions if (version.get("date") or {}).get("start")]
    with st_api.expander(f"Supplemental minor and patch releases ({len(dated)})"):
        st_api.caption(
            "Available for audit without giving routine release cadence equal visual weight."
        )
        if not dated:
            st_api.write("No dated supplemental releases match this protocol selection.")
            return
        rows = []
        for version in dated:
            evidence = tuple(version.get("evidence", ()))
            rows.append(
                {
                    "Date": _date_label(version.get("date") or {}),
                    "Protocol": str(version.get("protocol_acronym") or ""),
                    "Version": str(version.get("version") or ""),
                    "Stability": str(version.get("stability") or ""),
                    "Primary source": str(evidence[0].get("url") or "") if evidence else "",
                }
            )
        st_api.dataframe(rows, hide_index=True, width="stretch")


def _render_unresolved_items(
    st_api: Any, unresolved: Sequence[Mapping[str, Any]]
) -> None:
    if not unresolved:
        return
    st_api.subheader("Unresolved dates")
    st_api.caption(
        "These records remain outside the chronological axis until their date is resolved."
    )
    for item in unresolved:
        protocol = item.get("protocol") or {}
        acronym = str(
            item.get("protocol_acronym")
            or protocol.get("acronym")
            or item.get("protocol_id")
            or "Protocol"
        )
        label = str(
            item.get("summary")
            or item.get("version")
            or item.get("event_type")
            or item.get("id")
            or "Undated record"
        )
        st_api.write(f"{acronym} · {label}")


def _record_protocol_id(record: Mapping[str, Any]) -> str:
    protocol = record.get("protocol") or {}
    return str(record.get("protocol_id") or protocol.get("id") or "")


def _event_style(colour: str, precision: str) -> str:
    style = (
        f"border-color:{colour};background-color:#ffffff;color:#0f172a;"
        "font-size:11px;font-weight:650;line-height:1.15;padding:4px 6px;"
        "border-radius:7px;white-space:nowrap;"
    )
    if precision == "month":
        return style + "opacity:0.74;border-style:dashed;"
    if precision == "year":
        return style + "opacity:0.62;border-style:dashed;border-width:2px;"
    return style


def _event_label(event: Mapping[str, Any]) -> str:
    event_type = str(event.get("event_type") or "event")
    if event_type == "specification_release":
        version = _version_label(event.get("version"))
        if version and len(version) == 10:
            try:
                released = date.fromisoformat(version)
            except ValueError:
                pass
            else:
                return f"Spec {released:%d %b}"
        return f"Spec {version}" if version else "Specification"
    return {
        "public_launch": "Launch",
        "governance_adoption": "Governance",
        "stewardship_transfer": "Transfer",
        "merger": "Merger",
        "archival": "Archived",
        "production_deployment": "Deployment",
    }.get(event_type, event_type.replace("_", " ").title())


def _timeline_window_start(items: Sequence[Mapping[str, Any]]) -> str:
    starts = [date.fromisoformat(str(item["start"])) for item in items]
    return (min(starts) - timedelta(days=30)).isoformat()


def _date_midpoint(start: str, end: str) -> str:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    return (first + (last - first) / 2).isoformat()


def _label_position(event_date: str, observation_date: str, index: int) -> str:
    event_day = date.fromisoformat(event_date)
    observed = date.fromisoformat(observation_date)
    if 0 <= (observed - event_day).days <= 75:
        return "top left" if index % 2 == 0 else "bottom left"
    return ("top right", "bottom right", "top left", "bottom left")[index % 4]


def _transition_date_label(value: Mapping[str, Any]) -> str:
    start = str(value.get("start") or "")
    end = str(value.get("end") or "")
    if start and end:
        return f"{start} → {end} (interval-censored)"
    return _date_label(value)


def _human_label(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().title()


def _version_label(version: Any) -> str | None:
    if version is None:
        return None
    if isinstance(version, Mapping):
        value = version.get("label") or version.get("id")
        return str(value) if value is not None else None
    return str(version)


def _date_label(date_value: Mapping[str, Any]) -> str:
    value = date_value.get("value")
    precision = str(date_value.get("precision") or "unknown")
    if not value:
        return "Unresolved"
    if precision == "month":
        year, month = str(value).split("-", 1)
        month_names = (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
        return f"{month_names[int(month) - 1]} {year}"
    return str(value)


def _source_date_label(source: Mapping[str, Any], field: str) -> str:
    value = source.get(field)
    precision = str(source.get(f"{field}_precision") or "unknown")
    return _date_label({"value": value, "precision": precision})


__all__ = [
    "TimelinePayload",
    "build_timeline_figure",
    "build_timeline_payload",
    "evidence_card",
    "filter_timeline_records",
    "load_timeline_artifact",
    "protocol_options",
    "render_protocol_timeline",
    "selected_item_id",
    "selected_plot_event_id",
    "transition_card",
]
