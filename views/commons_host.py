"""Protected pilot diagnostics with intentionally separated strategy/contact tabs."""

from __future__ import annotations

import hmac
import os

import streamlit as st

from protocol import load_protocol, participant_alias
from storage import get_repository
from ui import footer, header, repository_mode, strategic_graph_dot


protocol = load_protocol()
repository = get_repository()


def configured_host_code() -> str:
    from_environment = os.getenv("PROTOHACK_HOST_CODE", "").strip()
    if from_environment:
        return from_environment
    try:
        return str(st.secrets.get("app", {}).get("host_access_code", "")).strip()
    except Exception:
        return ""


def authenticated() -> bool:
    if st.session_state.get("host_authenticated"):
        return True
    expected = configured_host_code()
    if not expected:
        st.error("Host access is not configured. Add app.host_access_code to secrets.")
        return False
    with st.form("host_login"):
        supplied = st.text_input("Host access code", type="password")
        submitted = st.form_submit_button("Open host view", width="stretch")
    if submitted:
        if hmac.compare_digest(supplied, expected):
            st.session_state.host_authenticated = True
            st.rerun()
        st.error("Access code not recognised.")
    return False


header(
    protocol,
    eyebrow="Pilot operations",
    title="Commons Host",
    copy="Strategic analysis and coordination records are kept in separate views, joined only by the participant's random code.",
)

if not authenticated():
    st.stop()

strategies = repository.list_strategic_profiles(protocol.session_code)
coordination = repository.list_coordination_interests(protocol.session_code)
feedback = repository.list_question_feedback(protocol.session_code)
reachable = [row for row in coordination if row.get("coordination_status") == "reachable_interest"]
anonymous = [row for row in coordination if row.get("coordination_status") == "anonymous_interest"]

st.warning(
    "Coordination policy: OPEN — pending discussion with Nathalie. This pilot records interest only; it sends nothing and makes no automatic introductions."
)

strategy_tab, feedback_tab, coordination_tab, diagnostics_tab = st.tabs(
    ["Strategic profiles", "Question feedback", "Coordination", "Diagnostics"]
)

with strategy_tab:
    st.caption("Anonymous analysis layer")
    if strategies:
        st.graphviz_chart(strategic_graph_dot(strategies), width="stretch")
        st.dataframe(
            [
                {
                    "Alias": row.get("participant_alias"),
                    "Move": row.get("action_label"),
                    "Rationale": row.get("rationale"),
                    "Themes": ", ".join(row.get("semantic_tags") or []),
                    "Integrated": row.get("integrated_at"),
                }
                for row in strategies
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No strategies integrated yet.")

with feedback_tab:
    st.caption("Anonymous flag and skip trail")
    if feedback:
        st.dataframe(
            [
                {
                    "Alias": row.get("participant_alias"),
                    "Event": str(row.get("event_type") or "").replace("question_", ""),
                    "Question": row.get("question_id"),
                    "Reasons": ", ".join(row.get("flag_labels") or []),
                    "Note": row.get("note"),
                    "Recorded": row.get("created_at"),
                }
                for row in feedback
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No flags or skips recorded yet.")

with coordination_tab:
    st.caption("Consent-based contact layer")
    first, second = st.columns(2)
    first.metric("Reachable interest", len(reachable))
    second.metric("Anonymous interest", len(anonymous))
    if reachable:
        st.dataframe(
            [
                {
                    "Alias": participant_alias(str(row["participant_uuid"])),
                    "Email": row.get("email"),
                    "Consented": row.get("coordination_consented_at"),
                    "Consent version": row.get("coordination_consent_version"),
                }
                for row in reachable
            ],
            hide_index=True,
            width="stretch",
        )
    if anonymous:
        st.write(f"{len(anonymous)} participant(s) expressed interest without leaving an email.")
    if not coordination:
        st.info("No coordination interest recorded yet.")

with diagnostics_tab:
    strategic_ids = {row.get("participant_uuid") for row in strategies}
    contact_ids = {row.get("participant_uuid") for row in coordination}
    st.write(
        {
            "storage_mode": repository_mode(),
            "protocol_version": protocol.version,
            "strategic_records": len(strategies),
            "coordination_records": len(coordination),
            "question_feedback_records": len(feedback),
            "coordination_without_strategy": len(contact_ids - strategic_ids),
        }
    )
    if st.button("Lock host view"):
        st.session_state.host_authenticated = False
        st.rerun()

footer(protocol)
