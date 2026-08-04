"""Protected diagnostics and field-note console for Protocol Laboratory."""

from __future__ import annotations

import hmac
import html
import os
from pathlib import Path

import streamlit as st

from protocol_lab import load_atlas, load_experiment
from protocol_lab.laboratory_ui import LAB_CYCLE
from storage import get_repository, repository_mode


ROOT = Path(__file__).parents[1]
SPEC_DIRECTORY = ROOT / "protocol_lab" / "specs"


def configured_host_code() -> str:
    configured = os.getenv("PROTOHACK_HOST_CODE", "").strip()
    if configured:
        return configured
    try:
        return str(
            st.secrets.get("app", {}).get("host_access_code", "")
        ).strip()
    except Exception:
        return ""


def authenticated() -> bool:
    if st.session_state.get("protocol_lab_host_authenticated"):
        return True
    expected = configured_host_code()
    if not expected:
        st.error(
            "Host access is not configured. Add app.host_access_code to secrets."
        )
    with st.form("protocol_lab_host_login"):
        supplied = st.text_input("Host access code", type="password")
        submitted = st.form_submit_button("Open host view", width="stretch")
    if submitted:
        if expected and hmac.compare_digest(supplied, expected):
            st.session_state.protocol_lab_host_authenticated = True
            st.rerun()
        st.error("Access code not recognised.")
    return False


st.markdown(
    """
    <style>
    .lab-host-hero { padding:2.4rem 0 1rem; max-width:900px; }
    .lab-host-hero p { max-width:720px; color:rgba(18,33,27,.68); line-height:1.55; }
    .lab-host-contract { display:flex; flex-wrap:wrap; gap:.4rem; margin:1rem 0; }
    .lab-host-contract span { border:1px solid rgba(18,33,27,.4); border-radius:999px; padding:.35rem .6rem; font-family:"DM Mono",monospace; font-size:.68rem; }
    .lab-host-record { border:1px solid rgba(18,33,27,.3); border-radius:14px; background:#fffdf6; padding:1rem; margin:.55rem 0; }
    .lab-host-record small { font-family:"DM Mono",monospace; }
    </style>
    <section class="lab-host-hero">
      <div class="eyebrow">Protocol operations</div>
      <h1>Protocol Laboratory Host</h1>
      <p>Inspect the fixed laboratory contract, experiment provenance, participant observations and definition health.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

if not authenticated():
    st.stop()

atlas = load_atlas(SPEC_DIRECTORY)
experiment = load_experiment(SPEC_DIRECTORY / "tcp_handshake_v1.yaml")
repository = get_repository()
try:
    list_field_notes = getattr(repository, "list_protocol_lab_field_notes", None)
    field_notes = list(list_field_notes()) if callable(list_field_notes) else []
    if not callable(list_field_notes):
        st.warning(
            "This running app predates Protocol Laboratory Field Notes storage. "
            "Restart the app to refresh the repository adapter."
        )
except Exception:
    st.error("Field-note records could not be loaded.")
    field_notes = []

overview_tab, contract_tab, provenance_tab, notes_tab, diagnostics_tab = st.tabs(
    ("Overview", "Contract", "Provenance", "Field notes", "Diagnostics")
)

with overview_tab:
    st.subheader("Experiment 01 · Connection")
    columns = st.columns(5)
    columns[0].metric("Experiments", len(atlas.entries))
    columns[1].metric("Shippable", sum(entry.experiment.shippable for entry in atlas.entries))
    columns[2].metric("Messages", len(experiment.messages))
    columns[3].metric("Invariants", len(experiment.invariants))
    columns[4].metric("Field notes", len(field_notes))
    st.markdown(f"**Technical question:** {experiment.question}")
    st.markdown(f"**Human translation:** {experiment.human_question}")
    st.markdown(f"**Need:** {experiment.need}")
    st.markdown(f"**Protocol:** {experiment.protocol.name}")
    st.caption(f"Storage mode: {repository_mode()}")

with contract_tab:
    st.subheader("Fixed laboratory contract")
    st.markdown(
        '<div class="lab-host-contract">'
        + "".join(f"<span>{html.escape(step)}</span>" for step in LAB_CYCLE)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("### Atlas functions")
    for function_name in atlas.functions:
        entries = atlas.entries_for(function_name)
        state = "active" if any(entry.experiment.shippable for entry in entries) else "canary"
        titles = ", ".join(entry.experiment.title for entry in entries) or "No experiment yet"
        st.markdown(f"**{function_name}** · {state}  \n{titles}")

with provenance_tab:
    st.subheader("Content provenance")
    st.caption(
        "Technical facts, historical claims, interpretive hypotheses and participant observations remain separate."
    )
    provenance_kinds = (
        "technical_fact",
        "historical_claim",
        "interpretive_hypothesis",
        "participant_observation",
    )
    for kind in provenance_kinds:
        st.markdown(f"### `{kind}`")
        claims = [claim for claim in experiment.archaeology if claim.provenance == kind]
        hidden_rules = [
            rule for rule in experiment.hidden_state_rules if rule.provenance == kind
        ]
        prompts = [
            prompt for prompt in experiment.reflection_prompts if prompt.provenance == kind
        ]
        if not claims and not hidden_rules and not prompts and kind != "participant_observation":
            st.caption("No authored entries.")
        for claim in claims:
            st.markdown(f"- **{claim.id}** — {claim.text}")
        for rule in hidden_rules:
            st.markdown(f"- **{rule.id}** — {rule.observation}")
        for prompt in prompts:
            st.markdown(f"- **{prompt.id}** — {prompt.question}")
        if kind == "participant_observation":
            st.caption(
                f"{len(field_notes)} saved participant-authored record(s); content appears in the Field notes tab."
            )

with notes_tab:
    st.subheader("Field-note records")
    st.caption(
        "Ownership hashes and contact details are intentionally omitted from this reading view."
    )
    if not field_notes:
        st.info("No participant field notes have been explicitly saved yet.")
    for note in field_notes:
        observations = note.get("observations") or {}
        if not isinstance(observations, dict):
            observations = {}
        body = "".join(
            f"<p><b>{html.escape(str(key))}</b><br>{html.escape(str(value))}</p>"
            for key, value in observations.items()
        )
        st.markdown(
            f"""
            <article class="lab-host-record">
              <small>{html.escape(str(note.get('participant_alias') or 'Anonymous'))} · {html.escape(str(note.get('created_at') or ''))}</small>
              {body}
            </article>
            """,
            unsafe_allow_html=True,
        )

with diagnostics_tab:
    st.subheader("Definition diagnostics")
    for entry in atlas.entries:
        definition = entry.experiment
        with st.expander(
            f"{definition.title} · {definition.version} · "
            f"{'shippable' if definition.shippable else 'canary'}"
        ):
            st.write(
                {
                    "id": definition.id,
                    "schema_version": definition.schema_version,
                    "atlas_functions": definition.atlas_functions,
                    "participants": len(definition.participants),
                    "messages": len(definition.messages),
                    "transitions": len(definition.transitions),
                    "invariants": len(definition.invariants),
                    "failure_scenarios": len(definition.failure_scenarios),
                    "hidden_state_rules": len(definition.hidden_state_rules),
                    "reflection_prompts": len(definition.reflection_prompts),
                }
            )
    if st.button("Lock host view", key="protocol_lab_host_lock"):
        st.session_state.protocol_lab_host_authenticated = False
        st.rerun()
