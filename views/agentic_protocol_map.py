"""Evidence-backed timeline and temporal multiplex map of agentic protocols."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from agentic_registry import RegistryValidationError, load_compiled_artifacts
from agentic_registry.graph_view import render_multiplex_graph
from agentic_registry.timeline_view import render_protocol_timeline


SHARED_PROTOCOL_KEY = "agentic_map_protocols"
SELECTED_TIMELINE_RECORD_KEY = "agentic_protocol_timeline_selected_event"


def _transition_graph_date(transition: Mapping[str, Any] | None) -> str | None:
    if not transition:
        return None
    effective = transition.get("effective") or {}
    if effective.get("mode") == "interval":
        return str(effective.get("end") or effective.get("start") or "") or None
    return str(effective.get("start") or "") or None


def _actor_interval(record: Mapping[str, Any]) -> str:
    actor = record.get("actor") or {}
    start = (record.get("valid_from") or {}).get("value") or "unknown"
    end = (record.get("valid_to") or {}).get("value") or "open"
    return f"{actor.get('label') or actor.get('id')} ({start} → {end})"


def _governance_value(field: str, value: Any) -> str:
    if value is None or value == []:
        return "Not recorded in the certified registry"
    if field in {
        "governing_body",
        "technical_steering_committee",
        "voting_organisations",
        "named_representatives",
        "appointment_intervals",
        "maintainer_intervals",
    }:
        return "; ".join(
            _actor_interval(item) if isinstance(item, Mapping) else str(item)
            for item in value
        )
    if field == "transfer_of_stewardship":
        return "; ".join(
            f"{(item.get('date') or {}).get('value') or 'unknown'} · "
            f"{item.get('summary') or item.get('event_id')}"
            for item in value
        )
    return str(value)


def _render_governance_surface(
    protocols: Sequence[Mapping[str, Any]], selected_ids: Sequence[str]
) -> None:
    available = [item for item in protocols if item.get("id") in selected_ids]
    if not available:
        st.info("Select at least one protocol to inspect its governance record.")
        return
    labels = {
        str(item["id"]): f"{item.get('acronym')} · {item.get('name')}"
        for item in available
    }
    protocol_id = st.selectbox(
        "Governance record",
        options=list(labels),
        format_func=labels.get,
        key="agentic_map_governance_protocol",
    )
    protocol = next(item for item in available if item.get("id") == protocol_id)
    surface = protocol.get("governance_surface") or {}
    field_labels = (
        ("governing_body", "Governing body"),
        ("technical_steering_committee", "Technical steering committee"),
        ("voting_organisations", "Voting organisation"),
        ("named_representatives", "Named representative"),
        ("appointment_intervals", "Appointment interval"),
        ("maintainer_intervals", "Maintainer interval"),
        ("decision_procedure", "Decision procedure"),
        ("transfer_of_stewardship", "Transfer of stewardship"),
    )
    st.dataframe(
        [
            {
                "Governance dimension": label,
                "Certified record": _governance_value(field, surface.get(field)),
            }
            for field, label in field_labels
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "Governance dimension": st.column_config.TextColumn(width="medium"),
            "Certified record": st.column_config.TextColumn(width="large"),
        },
    )
    gaps = surface.get("gaps") or []
    if gaps:
        st.caption(
            "Explicit registry gaps: "
            + ", ".join(str(item).replace("_", " ") for item in gaps)
            + ". Missing fields are not inferred from foundation membership, source titles, or launch announcements."
        )
    sources = surface.get("governance_evidence") or []
    if sources:
        st.markdown("**Governance sources**")
        for source in sources:
            st.markdown(
                f"- [{source.get('title') or source.get('id')}]({source.get('url')})"
                f" · {source.get('authority') or 'authority not stated'}"
            )


try:
    compiled = load_compiled_artifacts()
except (RegistryValidationError, OSError, ValueError) as error:
    st.error("The certified registry artifacts could not be validated.")
    st.exception(error)
    st.stop()

timeline = compiled.timeline
graph = compiled.graph
transition_cards = compiled.transition_cards
validation = compiled.validation
protocols = timeline["protocols"]
counts = validation["counts"]
st.html(
    f"""
    <style>
      .agentic-map-hero {{ padding: .2rem 0 .55rem; max-width: 72rem; }}
      .agentic-map-kicker {{ color: #8f6e42; letter-spacing: .13em; font-size: .7rem;
        font-weight: 700; text-transform: uppercase; }}
      .agentic-map-hero h1 {{ font-size: clamp(2.15rem, 3.2vw, 3.15rem); line-height: .98;
        margin: .38rem 0 .55rem; max-width: 16ch; }}
      .agentic-map-hero p {{ color: color-mix(in srgb, currentColor 70%, transparent);
        font-size: 1rem; line-height: 1.45; margin: 0; max-width: 68rem; }}
      .agentic-map-stats {{ display: flex; flex-wrap: wrap; gap: .3rem .8rem;
        margin-top: .7rem; color: color-mix(in srgb, currentColor 62%, transparent);
        font-size: .75rem; }}
      .agentic-map-stats b {{ color: currentColor; font-variant-numeric: tabular-nums; }}
      .agentic-map-question {{ border-left: 3px solid #c59152; padding: .12rem 0 .12rem .8rem;
        margin: .3rem 0 .65rem; font-size: .87rem; }}
    </style>
    <section class="agentic-map-hero">
      <div class="agentic-map-kicker">Mosaic relational observatory · certified core</div>
      <h1>Agentic protocol map</h1>
      <p>One evidence-backed history across proposal, implementation, governance and
      institutional consolidation.</p>
      <div class="agentic-map-stats" aria-label="Registry summary">
        <span><b>{counts['protocols']}</b> protocols</span>
        <span><b>{counts['protocol_events']}</b> events</span>
        <span><b>{counts['actors']}</b> actors</span>
        <span><b>{counts['actor_protocol_relations']}</b> authored relations</span>
        <span><b>{counts['protocol_regimes']}</b> regimes</span>
        <span><b>{counts['protocol_transitions']}</b> transitions</span>
        <span><b>{counts['evidence_sources']}</b> sources</span>
        <span><b>{counts['frontier_candidates']}</b> frontier</span>
      </div>
    </section>
    """
)
protocol_labels = {
    str(item["id"]): f"{item.get('acronym')} · {item.get('name')}"
    for item in protocols
}
if SHARED_PROTOCOL_KEY not in st.session_state:
    st.session_state[SHARED_PROTOCOL_KEY] = list(protocol_labels)
with st.popover("Filter protocols", icon="⚙️"):
    selected_protocols = st.multiselect(
        "Protocols shown in both views",
        options=list(protocol_labels),
        format_func=protocol_labels.get,
        key=SHARED_PROTOCOL_KEY,
        help="The timeline and network stay aligned to this certified protocol selection.",
    )

timeline_tab, network_tab = st.tabs(
    ["◷ Protocol timeline", "⬡ Actor–protocol network"]
)
with timeline_tab:
    st.caption(
        "Historical question: how did each protocol move from proposal to implementation, "
        "governance and institutional consolidation?"
    )
    timeline_payload = render_protocol_timeline(
        timeline=timeline,
        transition_cards=transition_cards,
        protocol_ids=selected_protocols,
    )

selected_record_id = st.session_state.get(SELECTED_TIMELINE_RECORD_KEY)
selected_transition = timeline_payload.transition_cards.get(
    str(selected_record_id or "")
)

with network_tab:
    st.html(
        '<div class="agentic-map-question"><b>Who exercises which relation</b> to each '
        "protocol, and how does that structure change over time?</div>"
    )
    render_multiplex_graph(
        graph,
        protocol_ids=selected_protocols,
        selected_date=_transition_graph_date(selected_transition),
        selected_transition=selected_transition,
    )

st.divider()
st.subheader("Governance surface")
st.caption(
    "The eight requested dimensions are shown even when the certified registry does not yet contain a claim for them."
)
_render_governance_surface(protocols, selected_protocols)

with st.expander("Validation and provenance"):
    st.success("Compiler validation passed. Timeline and graph share one source snapshot.")
    st.code(
        f"Registry {validation['metadata']['registry_id']} · "
        f"version {validation['metadata']['registry_version']} · "
        f"observed {validation['metadata']['observed_at']}\n"
        f"SHA-256 {validation['metadata']['source_sha256']}",
        language=None,
    )
    st.caption(
        "Held frontier candidates stay outside the certified views until their missing gates and evidence are resolved."
    )
    for warning in validation.get("warnings") or []:
        st.warning(warning["message"], icon="⚠️")
