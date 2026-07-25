"""Protected, YAML-first operator console for every questionnaire bundle."""

from __future__ import annotations

import hmac
import html
import os
from pathlib import Path

import streamlit as st

from protocol import (
    QuestionDefinition,
    QuestionSetBundle,
    QuestionSetCatalog,
    load_question_set_catalog,
)
from storage import get_repository


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


def _host_styles() -> None:
    st.markdown(
        """
        <style>
        .host-hero { padding:2.4rem 0 1rem; max-width:920px; }
        .host-hero h1 { margin:.35rem 0 .7rem; }
        .host-hero p { max-width:760px; color:rgba(18,33,27,.68); font-size:1.08rem; line-height:1.55; }
        .host-overview { display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; padding:.65rem 0 1.2rem; }
        .host-overview h2 { margin:0 0 .3rem; }
        .host-overview p { margin:0; color:rgba(18,33,27,.66); }
        .host-count { font-family:"DM Mono",monospace; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; white-space:nowrap; }
        .host-meta-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.65rem; margin:.65rem 0 1.5rem; }
        .host-meta-card { min-width:0; background:#fffdf6; border:1px solid rgba(18,33,27,.34); border-radius:12px; padding:.72rem .78rem; }
        .host-meta-label { font-family:"DM Mono",monospace; font-size:.62rem; text-transform:uppercase; letter-spacing:.09em; color:rgba(18,33,27,.55); }
        .host-meta-value { margin-top:.25rem; font-family:"DM Mono",monospace; font-size:.76rem; overflow-wrap:anywhere; }
        .host-question-title { font-size:1.03rem; font-weight:700; line-height:1.35; margin:.08rem 0 .2rem; }
        .host-question-id { font-family:"DM Mono",monospace; font-size:.7rem; letter-spacing:.08em; color:rgba(18,33,27,.58); }
        .host-question-meta { color:rgba(18,33,27,.62); font-size:.8rem; }
        .host-flow-node { display:grid; grid-template-columns:3rem minmax(0,1fr) auto; align-items:center; gap:.9rem; padding:.9rem 1rem; background:#fffdf6; border:1px solid rgba(18,33,27,.3); border-radius:13px; margin:.35rem 0; }
        .host-flow-index { font-family:"DM Mono",monospace; font-size:.7rem; color:rgba(18,33,27,.55); }
        .host-flow-title { font-weight:700; }
        .host-flow-meta { font-family:"DM Mono",monospace; font-size:.68rem; color:rgba(18,33,27,.58); text-align:right; }
        .host-flow-arrow { height:1rem; margin-left:2.4rem; border-left:1px solid rgba(18,33,27,.45); }
        .host-section-space { height:.55rem; }
        @media (max-width: 820px) {
          .host-meta-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
          .host-overview { align-items:flex-start; flex-direction:column; }
          .host-flow-node { grid-template-columns:2.4rem minmax(0,1fr); }
          .host-flow-meta { grid-column:2; text-align:left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _source_label(bundle: QuestionSetBundle) -> str:
    try:
        return str(bundle.source_path.relative_to(Path.cwd()))
    except ValueError:
        return str(bundle.source_path)


def _metadata_card(label: str, value: str) -> str:
    return (
        '<div class="host-meta-card">'
        f'<div class="host-meta-label">{html.escape(label)}</div>'
        f'<div class="host-meta-value">{html.escape(value or "—")}</div>'
        "</div>"
    )


def _render_bundle_header(bundle: QuestionSetBundle) -> None:
    st.markdown(
        f"""
        <div class="host-meta-grid">
          {_metadata_card("campaign_slug", bundle.campaign_slug)}
          {_metadata_card("event_slug", bundle.event_slug)}
          {_metadata_card("question_set_id", bundle.question_set_id)}
          {_metadata_card("schema_id", bundle.schema_id)}
          {_metadata_card("YAML source", _source_label(bundle))}
          {_metadata_card("version", bundle.version)}
          {_metadata_card("question count", str(bundle.question_count))}
          {_metadata_card("last loaded", bundle.loaded_at.strftime("%Y-%m-%d %H:%M:%S UTC"))}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_statistics(bundle: QuestionSetBundle) -> None:
    columns = st.columns(6)
    columns[0].metric("Questions", bundle.question_count)
    columns[1].metric("Required", bundle.required_count)
    columns[2].metric("Optional", bundle.optional_count)
    columns[3].metric("Multiple choice", bundle.multiple_choice_count)
    columns[4].metric("Open text", bundle.open_text_count)
    columns[5].metric("Estimated time", f"{bundle.estimated_minutes} min")
    if bundle.disabled_question_count:
        st.caption(
            f"{bundle.active_question_count} active · "
            f"{bundle.disabled_question_count} disabled for this pilot"
        )


def _render_activity(
    *,
    bundle: QuestionSetBundle,
    events: list[dict[str, object]],
    feedback: list[dict[str, object]],
) -> None:
    answered = sum(event.get("status") == "answered" for event in events)
    skipped = sum(event.get("status") == "skipped" for event in events)
    answered_and_flagged = sum(
        event.get("status") == "answered_and_flagged" for event in events
    )
    flags = sum(
        event.get("event_type") == "question_flagged"
        and event.get("track_id") == bundle.question_set_id
        for event in feedback
    )

    st.markdown("### Question activity")
    metrics = st.columns(4)
    metrics[0].metric("Answered", answered)
    metrics[1].metric("Skipped", skipped)
    metrics[2].metric("Flags", flags)
    metrics[3].metric("Answered + flagged", answered_and_flagged)

    if events:
        st.dataframe(
            [
                {
                    "question_id": event.get("question_id"),
                    "status": event.get("status"),
                    "reason_code": event.get("reason_code") or "—",
                    "participant": event.get("participant_alias") or "—",
                    "timestamp": event.get("timestamp"),
                }
                for event in events
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No participant question events have been recorded yet.")


def _render_bundle_records(
    *,
    bundle: QuestionSetBundle,
    submissions: list[dict[str, object]],
    contacts: list[dict[str, object]],
) -> None:
    consent_count = 0
    for submission in submissions:
        responses = submission.get("responses")
        if not isinstance(responses, list):
            continue
        if any(
            isinstance(response, dict)
            and (
                response.get("canonical_field") == "consent.coordination"
                or response.get("field_id") == "mosaic_communication_consent"
            )
            and response.get("value") == "yes"
            for response in responses
        ):
            consent_count += 1

    st.markdown("### Bundle records")
    metrics = st.columns(4)
    metrics[0].metric("Response records", len(submissions))
    metrics[1].metric("Conditional fields", bundle.conditional_count)
    metrics[2].metric("Communication consent", consent_count)
    metrics[3].metric("Contact records", len(contacts))


def _render_question_detail(question: QuestionDefinition) -> None:
    st.markdown("**Context**")
    st.write(question.context or "—")

    if question.option_groups:
        st.markdown("**Options**")
        for group, options in question.option_groups:
            st.markdown(f"**{group}**")
            st.markdown("\n".join(f"- {option}" for option in options))
    elif question.options:
        st.markdown("**Options**")
        st.markdown(
            "\n".join(
                f"- `{option}` — {question.option_label(option)}"
                for option in question.options
            )
        )
    else:
        st.markdown("**Options**")
        st.write("Resolved by the runtime." if question.dynamic else "—")

    identifiers, authoring = st.columns(2)
    with identifiers:
        st.markdown("**Identifiers**")
        st.code(
            (
                f"yaml_id        = {question.id}\n"
                f"field_id       = {question.field_id}\n"
                f"canonical_field = {question.canonical_field or '—'}\n"
                f"data_scope     = {question.data_scope}"
            ),
            language="text",
        )
    with authoring:
        st.markdown("**Notes**")
        st.write(question.notes or "—")
        if question.placeholder:
            st.caption(f"Placeholder: {question.placeholder}")
        if question.allow_other:
            st.caption("An authored “Other” response is allowed.")
        if question.visible_when:
            field_id, expected = question.visible_when
            st.caption(f"Visible when `{field_id}` equals `{expected}`.")
        if question.required_when:
            field_id, expected = question.required_when
            st.caption(f"Required when `{field_id}` equals `{expected}`.")


def _render_question_list(bundle: QuestionSetBundle) -> None:
    for question in bundle.questions:
        with st.container(border=True):
            identity, metadata = st.columns([3, 2])
            with identity:
                st.markdown(
                    f'<div class="host-question-id">{html.escape(question.id)}</div>'
                    f'<div class="host-question-title">{html.escape(question.title)}</div>',
                    unsafe_allow_html=True,
                )
            with metadata:
                if not question.enabled:
                    status = "Disabled for pilot"
                else:
                    status = "Required" if question.required else "Optional"
                st.markdown(
                    f'<div class="host-question-meta">{html.escape(question.type_label)}<br>'
                    f'{html.escape(question.group)}<br>{status}</div>',
                    unsafe_allow_html=True,
                )
            with st.expander("↓ Expand", expanded=False):
                _render_question_detail(question)


def _render_section_structure(bundle: QuestionSetBundle) -> None:
    st.markdown("### Section structure")
    by_id = {question.id: question for question in bundle.questions}
    for section in bundle.sections:
        st.markdown(f"#### {section.title}")
        if section.description:
            st.caption(section.description)
        for question_id in section.question_ids:
            question = by_id[question_id]
            with st.container(border=True):
                identity, metadata = st.columns([3, 2])
                with identity:
                    st.markdown(
                        f'<div class="host-question-id">{html.escape(question.id)}</div>'
                        f'<div class="host-question-title">{html.escape(question.title)}</div>',
                        unsafe_allow_html=True,
                    )
                with metadata:
                    if not question.enabled:
                        status = "Disabled for pilot"
                    elif question.required_when:
                        status = "Conditionally required"
                    else:
                        status = "Required" if question.required else "Optional"
                    st.markdown(
                        f'<div class="host-question-meta">{html.escape(question.type_label)}<br>'
                        f'{html.escape(section.title)}<br>{status}</div>',
                        unsafe_allow_html=True,
                    )
                with st.expander("↓ Expand", expanded=False):
                    _render_question_detail(question)


def _render_simulation_flow(bundle: QuestionSetBundle) -> None:
    metrics = st.columns(5)
    metrics[0].metric("Scenario count", bundle.count_nodes("scenario"))
    metrics[1].metric("Decision nodes", bundle.count_nodes("decision"))
    metrics[2].metric("Action nodes", bundle.count_nodes("action"))
    metrics[3].metric("Review node", bundle.count_nodes("review"))
    metrics[4].metric("Simulation flow", f"{len(bundle.flow)} steps")

    st.markdown("### Simulation flow")
    for index, label in enumerate(bundle.flow, start=1):
        question = bundle.questions[index - 1] if index <= len(bundle.questions) else None
        question_id = question.id if question else "—"
        question_type = question.type_label if question else "Unmapped"
        st.markdown(
            f"""
            <div class="host-flow-node">
              <div class="host-flow-index">{index:02d}</div>
              <div class="host-flow-title">{html.escape(label)}</div>
              <div class="host-flow-meta">{html.escape(question_id)} · {html.escape(question_type)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if question:
            with st.expander(f"Inspect node {question.id}", expanded=False):
                _render_question_detail(question)
        if index < len(bundle.flow):
            st.markdown('<div class="host-flow-arrow"></div>', unsafe_allow_html=True)


def render_question_set(
    bundle: QuestionSetBundle,
    *,
    events: list[dict[str, object]] | None = None,
    feedback: list[dict[str, object]] | None = None,
    submissions: list[dict[str, object]] | None = None,
    contacts: list[dict[str, object]] | None = None,
) -> None:
    """Render any validated YAML questionnaire bundle without protocol-specific code."""

    st.markdown("### Question Set Overview")
    st.markdown(
        f"""
        <div class="host-overview">
          <div>
            <h2>{html.escape(bundle.title)}</h2>
            <p>{html.escape(bundle.summary or bundle.description)}</p>
          </div>
          <div class="host-count">{bundle.question_count} questions</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if bundle.description and bundle.summary:
        st.caption(bundle.description)

    st.markdown("### Resolved bundle")
    _render_bundle_header(bundle)
    _render_activity(
        bundle=bundle,
        events=events or [],
        feedback=feedback or [],
    )
    _render_bundle_records(
        bundle=bundle,
        submissions=submissions or [],
        contacts=contacts or [],
    )

    if bundle.flow:
        _render_simulation_flow(bundle)
    elif bundle.sections:
        st.markdown("### Question statistics")
        _render_statistics(bundle)
        _render_section_structure(bundle)
    else:
        st.markdown("### Question statistics")
        _render_statistics(bundle)
        st.markdown('<div class="host-section-space"></div>', unsafe_allow_html=True)
        st.markdown("### Question list")
        _render_question_list(bundle)


def _diagnostic_values(values: list[str], empty_message: str) -> None:
    if values:
        st.code("\n".join(values), language="text")
    else:
        st.success(empty_message)


def _render_diagnostics(catalog: QuestionSetCatalog) -> None:
    st.markdown("### Loaded YAML")
    st.dataframe(
        [
            {
                "bundle": bundle.title,
                "question_set_id": bundle.question_set_id,
                "source": _source_label(bundle),
                "version": bundle.version,
                "questions": bundle.question_count,
                "loaded": bundle.loaded_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
            for bundle in catalog.bundles
        ],
        hide_index=True,
        width="stretch",
    )

    validation_errors = [
        f"{bundle.title}: {message}"
        for bundle in catalog.bundles
        for message in bundle.validation.errors
    ] + list(catalog.discovery_errors)
    warnings = [
        f"{bundle.title}: {message}"
        for bundle in catalog.bundles
        for message in bundle.validation.warnings
    ]
    missing_fields = [
        f"{bundle.title}: {field}"
        for bundle in catalog.bundles
        for field in bundle.validation.missing_fields
    ]
    unknown_types = sorted(
        {
            field_type
            for bundle in catalog.bundles
            for field_type in bundle.validation.unknown_field_types
        }
    )
    duplicate_ids = sorted(
        set(catalog.duplicate_question_ids).union(
            duplicate
            for bundle in catalog.bundles
            for duplicate in bundle.validation.duplicate_ids
        )
    )

    st.markdown("### Validation")
    status = st.columns(3)
    status[0].metric("Bundles", len(catalog.bundles))
    status[1].metric("Errors", len(validation_errors))
    status[2].metric("Warnings", len(warnings))
    _diagnostic_values(validation_errors, "All loaded bundles passed structural validation.")

    left, right = st.columns(2)
    with left:
        st.markdown("### Schema")
        st.dataframe(
            [
                {
                    "question_set_id": bundle.question_set_id,
                    "schema_id": bundle.schema_id,
                }
                for bundle in catalog.bundles
            ],
            hide_index=True,
            width="stretch",
        )
        st.markdown("### Missing fields")
        _diagnostic_values(missing_fields, "No required fields are missing.")
        st.markdown("### Unknown field types")
        _diagnostic_values(unknown_types, "All field types are known.")
    with right:
        st.markdown("### Warnings")
        _diagnostic_values(warnings, "No authoring warnings.")
        st.markdown("### Question ids")
        st.code("\n".join(catalog.question_ids) or "—", language="text")
        st.markdown("### Duplicate ids")
        _diagnostic_values(duplicate_ids, "Question ids are unique.")

    st.markdown("### Estimated duration")
    st.metric("All loaded question sets", f"{catalog.estimated_minutes} min")
    st.caption(
        "Estimate uses a fixed per-field reading and response allowance; it is an operator planning aid."
    )

    if st.button("Lock host view"):
        st.session_state.host_authenticated = False
        st.rerun()


_host_styles()
st.markdown(
    """
    <div class="host-hero">
      <div class="eyebrow">Protocol operations</div>
      <h1>Commons Host</h1>
      <p>Inspect the loaded questionnaire bundles, their authored questions and their technical health.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not authenticated():
    st.stop()

catalog = load_question_set_catalog()
repository = get_repository()
tab_labels = [bundle.title for bundle in catalog.bundles] + ["Diagnostics"]
tabs = st.tabs(tab_labels)
for tab, bundle in zip(tabs[:-1], catalog.bundles):
    with tab:
        try:
            events = repository.list_question_events(bundle.question_set_id)
            feedback = repository.list_question_feedback(bundle.session_code)
            submissions = repository.list_question_set_submissions(
                bundle.question_set_id
            )
            contacts = repository.list_question_set_contacts(
                bundle.question_set_id
            )
        except Exception:
            st.error("Question activity could not be loaded.")
            events = []
            feedback = []
            submissions = []
            contacts = []
        render_question_set(
            bundle,
            events=events,
            feedback=feedback,
            submissions=submissions,
            contacts=contacts,
        )
with tabs[-1]:
    _render_diagnostics(catalog)

st.markdown(
    f'<div class="footer">QUESTION-SET CONSOLE · {len(catalog.bundles)} YAML BUNDLES</div>',
    unsafe_allow_html=True,
)
