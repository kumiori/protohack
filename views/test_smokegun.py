"""Preserved smoke-test path and shared source for the refined Commons page."""

from __future__ import annotations

from email.utils import parseaddr
import html
import uuid
from typing import Any

import streamlit as st

from protocol import (
    QUESTION_FLAG_LABELS,
    QUESTION_FLAG_OPTIONS,
    access_key_emoji,
    access_key_hash,
    build_question_feedback,
    build_strategic_profile,
    load_protocol,
    normalize_access_key,
    normalize_rationale,
)
from protocol.domain import utc_now_iso
from storage import get_repository
from ui import (
    compact_masthead,
    footer,
    header,
    participant_refinement_styles,
    privacy_note,
)


protocol = load_protocol()
repository = get_repository()
refined_commons = __name__ == "__commons_flow__"

if refined_commons:
    participant_refinement_styles()

if protocol.interaction.question_actions != ("continue", "flag", "skip"):
    raise RuntimeError(
        "This participant surface requires the continue/flag/skip interaction contract."
    )


def participant_uuid() -> str:
    stored = st.session_state.get("participant_uuid")
    if stored:
        return str(stored)
    candidate = str(st.query_params.get("run") or "")
    try:
        value = normalize_access_key(candidate)
    except ValueError:
        value = str(uuid.uuid4())
        st.query_params["run"] = value
    st.session_state.participant_uuid = value
    return value


def switch_participant(access_key: str) -> None:
    canonical = normalize_access_key(access_key)
    for key in (
        "stage",
        "action_id",
        "rationale",
        "rationale_skipped",
        "integrated_profile",
        "question_feedback_state",
        "scenario_action_choice",
        "rationale_answer",
        "scenario_validation",
        "rationale_validation",
        "show_integration_balloons",
    ):
        st.session_state.pop(key, None)
    st.session_state.participant_uuid = canonical
    st.query_params["run"] = canonical


def valid_optional_email(value: str) -> bool:
    if not value.strip():
        return True
    parsed = parseaddr(value.strip())[1]
    return (
        parsed == value.strip() and "@" in parsed and "." in parsed.rsplit("@", 1)[-1]
    )


def participant_number() -> int:
    profiles = sorted(
        repository.list_strategic_profiles(protocol.session_code),
        key=lambda row: (
            str(row.get("integrated_at") or ""),
            str(row.get("participant_uuid") or ""),
        ),
    )
    for index, profile in enumerate(profiles, start=1):
        if str(profile.get("participant_uuid") or "") == participant:
            return index
    return len(profiles) or 1


def feedback_state(question_id: str) -> dict[str, Any]:
    all_feedback = st.session_state.setdefault("question_feedback_state", {})
    return dict(all_feedback.get(question_id) or {})


def save_feedback_state(question_id: str, *, flags: list[str], note: str) -> None:
    all_feedback = st.session_state.setdefault("question_feedback_state", {})
    all_feedback[question_id] = {"flags": list(flags), "note": note}


def feedback_payload(
    *,
    event_type: str,
    question_id: str,
    question_prompt: str,
    flags: list[str],
    note: str,
) -> dict[str, Any]:
    return build_question_feedback(
        event_type=event_type,
        participant_uuid=participant,
        session_code=protocol.session_code,
        protocol_id=protocol.id,
        protocol_version=protocol.version,
        question_id=question_id,
        question_prompt=question_prompt,
        flags=flags,
        note=note,
    )


def render_flag_control(question_id: str, question_prompt: str) -> None:
    existing = feedback_state(question_id)
    saved_flags = list(existing.get("flags") or [])
    saved_note = str(existing.get("note") or "")
    count = len(saved_flags) + (1 if saved_note else 0)
    label = f"Flag ({count})" if count else "Flag"
    with st.popover(label, width="stretch"):
        st.caption(
            "Mark if the question feels incomplete, misleading, narrow, or otherwise off."
        )
        with st.form(f"flag_form_{question_id}"):
            selected = st.pills(
                "Question feedback",
                options=[value for value, _label in QUESTION_FLAG_OPTIONS],
                default=saved_flags,
                selection_mode="multi",
                format_func=lambda value: QUESTION_FLAG_LABELS[value],
                label_visibility="collapsed",
            )
            note = st.text_input(
                "Optional note",
                value=saved_note,
                placeholder="Optional short note",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Save flag", width="stretch")
        if submitted:
            try:
                payload = feedback_payload(
                    event_type="question_flagged",
                    question_id=question_id,
                    question_prompt=question_prompt,
                    flags=list(selected),
                    note=note,
                )
                repository.record_question_feedback(payload)
            except ValueError as exc:
                st.warning(str(exc))
            except Exception:
                st.error("The flag was not saved. Please try again.")
            else:
                save_feedback_state(
                    question_id,
                    flags=list(payload["flags"]),
                    note=str(payload["note"]),
                )
                st.success("Flag saved.")
                st.rerun()


def open_skip_dialog(
    *,
    question_id: str,
    question_prompt: str,
    outcome: str,
) -> None:
    existing = feedback_state(question_id)

    @st.dialog("Skip question")
    def skip_dialog() -> None:
        st.markdown(f"### {question_prompt}")
        st.caption(
            "You can skip this question, but tell us why so we can improve the simulation."
        )
        selected = st.pills(
            "Why skip?",
            options=[value for value, _label in QUESTION_FLAG_OPTIONS],
            default=list(existing.get("flags") or []),
            selection_mode="multi",
            format_func=lambda value: QUESTION_FLAG_LABELS[value],
        )
        note = st.text_area(
            "Optional note",
            value=str(existing.get("note") or ""),
            placeholder="A short reason for skipping this question",
            height=140,
        )
        if st.button("Skip and continue", type="primary", width="stretch"):
            try:
                payload = feedback_payload(
                    event_type="question_skipped",
                    question_id=question_id,
                    question_prompt=question_prompt,
                    flags=list(selected),
                    note=note,
                )
                repository.record_question_feedback(payload)
            except ValueError as exc:
                st.warning(str(exc))
                return
            except Exception:
                st.error("The skip was not saved. Please try again.")
                return
            save_feedback_state(
                question_id,
                flags=list(payload["flags"]),
                note=str(payload["note"]),
            )
            if outcome == "skip_simulation":
                st.session_state.stage = "skipped"
            else:
                st.session_state.rationale = ""
                st.session_state.rationale_skipped = True
                st.session_state.pop("rationale_answer", None)
                st.session_state.stage = "review"
            st.rerun()

    skip_dialog()


def render_question_actions(
    *,
    question_id: str,
    question_prompt: str,
    continue_label: str,
    continue_action: Any,
    skip_outcome: str,
) -> None:
    primary, flag_column, skip_column = st.columns([1.6, 0.5, 0.4])
    with primary:
        if st.button(
            continue_label,
            type="secondary" if refined_commons else "primary",
            width="stretch",
            key=f"continue_{question_id}",
        ):
            continue_action()
    with flag_column:
        render_flag_control(question_id, question_prompt)
    with skip_column:
        if st.button("Skip", width="stretch", key=f"skip_{question_id}"):
            open_skip_dialog(
                question_id=question_id,
                question_prompt=question_prompt,
                outcome=skip_outcome,
            )


def open_integration_confirmation(action_id: str) -> None:
    action = protocol.scenario.decision.action(action_id)

    @st.dialog("Save this key", width="large")
    def confirmation_dialog() -> None:
        st.markdown(
            f"<div style='text-align:center;font-size:4rem;line-height:1.2;padding:.5rem 0'>{html.escape(access_key_emoji(participant))}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Full textual return key — copy this on a laptop**")
        st.code(participant, language=None)
        st.markdown("**Full verification hash**")
        st.code(access_key_hash(participant), language=None)
        st.caption(
            "The textual key also remains in this page's private `run` link. It identifies an anonymous trajectory, not a person."
        )
        st.divider()
        st.markdown(f"### Confirm · {action.label}")
        if st.session_state.get("rationale_skipped"):
            st.write("Rationale skipped with feedback recorded.")
        else:
            st.write(str(st.session_state.get("rationale") or ""))
        if st.button("Confirm and integrate", type="primary", width="stretch"):
            profile = build_strategic_profile(
                protocol=protocol,
                participant_uuid=participant,
                action_id=action.id,
                rationale=str(st.session_state.get("rationale") or ""),
                rationale_skipped=bool(st.session_state.get("rationale_skipped")),
            )
            try:
                st.session_state.integrated_profile = (
                    repository.integrate_strategic_profile(profile)
                )
            except Exception:
                st.error(
                    "Integration did not complete. Your draft is still here; please try again."
                )
                return
            st.session_state.show_integration_balloons = (
                protocol.interaction.balloons_after_integration
            )
            st.session_state.stage = "coordination"
            st.rerun()

    confirmation_dialog()


participant = participant_uuid()
existing_profile = repository.get_strategic_profile(
    participant, protocol.scenario.id, protocol.version
)
if existing_profile:
    st.session_state.integrated_profile = existing_profile
    st.session_state.stage = st.session_state.get("stage", "coordination")

stage = st.session_state.get("stage", "orientation")

if refined_commons and stage != "orientation":
    compact_masthead(protocol)
else:
    header(
        protocol,
        eyebrow=(
            "A strategic exploration"
            if refined_commons
            else "Protocol Hack · Smoke simulation"
        ),
        title="Question the commons.",
        copy=(
            "There is no right or wrong answer. We are exploring strategies, fuck the system."
            if refined_commons
            else "One situation. One strategic move. One sentence about why. Then see your trajectory enter a collective map."
        ),
        pilot_display="badge" if refined_commons else "banner",
        show_storage_warning=not refined_commons,
    )

progress = {
    "orientation": 0.10,
    "scenario": 0.30,
    "rationale": 0.55,
    "review": 0.75,
    "coordination": 0.90,
    "done": 1.0,
    "skipped": 1.0,
}.get(stage, 0.1)
st.progress(progress, text=f"Movement · {stage.replace('_', ' ').title()}")

if stage == "orientation":
    if not refined_commons:
        st.subheader("A strategic simulation, not a test")
        st.write(
            "You are making a first move under uncertainty. Every question can be flagged or skipped with a reason. Your explanation is stored as written and is not automatically classified."
        )
        privacy_note()
    if st.button(
        "Enter the scenario",
        type="primary",
        width="stretch",
        key="enter_scenario" if refined_commons else "enter_smokegun",
    ):
        st.session_state.stage = "scenario"
        st.rerun()
    with st.expander("Return with a saved textual key"):
        saved_key = st.text_input(
            "Full textual access key",
            placeholder="00000000-0000-4000-8000-000000000000",
        )
        if st.button("Resume anonymous trajectory", width="stretch"):
            try:
                switch_participant(saved_key)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()

elif stage == "scenario":
    scenario = protocol.scenario
    st.markdown(
        f"""
        <div class="scenario">
          <div class="eyebrow">{html.escape(scenario.id)}</div>
          <h2>{html.escape(scenario.title)}</h2>
          <p>{html.escape(scenario.body)}</p>
          <div class="notice">{html.escape(scenario.notice)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    choice = st.radio(
        scenario.decision.prompt,
        options=[action.id for action in scenario.decision.actions],
        format_func=lambda action_id: next(
            action.label
            for action in scenario.decision.actions
            if action.id == action_id
        ),
        index=None,
        key="scenario_action_choice",
    )
    if refined_commons:
        if choice:
            selected_action = scenario.decision.action(choice)
            st.caption(selected_action.description)
    else:
        for action in scenario.decision.actions:
            st.caption(f"{action.label} — {action.description}")

    def continue_scenario() -> None:
        if not choice:
            st.session_state.scenario_validation = (
                "Choose one first move or skip with a reason."
            )
            st.rerun()
        st.session_state.scenario_validation = ""
        st.session_state.action_id = choice
        st.session_state.rationale_skipped = False
        st.session_state.stage = "rationale"
        st.rerun()

    if st.session_state.get("scenario_validation"):
        st.error(str(st.session_state.scenario_validation))
    render_question_actions(
        question_id=scenario.decision.id,
        question_prompt=scenario.decision.prompt,
        continue_label="Continue",
        continue_action=continue_scenario,
        skip_outcome="skip_simulation",
    )

elif stage == "rationale":
    action = protocol.scenario.decision.action(str(st.session_state.get("action_id")))
    st.caption(f"Your first move · {action.label}")
    rationale = st.text_area(
        protocol.rationale_prompt,
        value=str(st.session_state.get("rationale", "")),
        placeholder=protocol.rationale_hint,
        max_chars=600,
        height=140,
        key="rationale_answer",
    )

    def continue_rationale() -> None:
        try:
            st.session_state.rationale = normalize_rationale(rationale)
        except ValueError as exc:
            st.session_state.rationale_validation = str(exc)
            st.rerun()
        st.session_state.rationale_validation = ""
        st.session_state.rationale_skipped = False
        st.session_state.stage = "review"
        st.rerun()

    if st.session_state.get("rationale_validation"):
        st.error(str(st.session_state.rationale_validation))
    render_question_actions(
        question_id=protocol.rationale_id,
        question_prompt=protocol.rationale_prompt,
        continue_label="Continue to review",
        continue_action=continue_rationale,
        skip_outcome="review_without_rationale",
    )

elif stage == "review":
    action = protocol.scenario.decision.action(str(st.session_state.action_id))
    rationale_copy = (
        "Rationale skipped · feedback recorded"
        if st.session_state.get("rationale_skipped")
        else str(st.session_state.get("rationale") or "")
    )
    if refined_commons:
        st.markdown(
            f"""
            <div class="review-card">
              <div class="eyebrow">First move</div>
              <div class="review-action">{html.escape(action.label)}</div>
              <div class="review-description">{html.escape(action.description)}</div>
              <div class="eyebrow review-because">Because…</div>
              <div class="review-rationale">{html.escape(rationale_copy)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.subheader("Review before integration")
        st.markdown(
            f"""
            <div class="scenario">
              <div class="eyebrow">{html.escape(protocol.scenario.id)} → {html.escape(protocol.scenario.decision.id)} → {html.escape(action.id)}</div>
              <h2>{html.escape(action.label)}</h2>
              <p>{html.escape(rationale_copy)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Authored themes · " + " · ".join(action.semantic_tags))
    left, middle, right = st.columns([1, 1, 2])
    if left.button("Change move", width="stretch"):
        st.session_state.stage = "scenario"
        st.rerun()
    if middle.button("Edit why", width="stretch"):
        st.session_state.stage = "rationale"
        st.rerun()
    if right.button("Review integration", type="primary", width="stretch"):
        open_integration_confirmation(action.id)

elif stage == "coordination":
    if st.session_state.pop("show_integration_balloons", False):
        st.balloons()
    if refined_commons:
        number = participant_number()
        st.markdown(
            f"""
            <div class="reward">
              <div class="reward-check">✓</div>
              <div class="eyebrow">You are participant #{number}</div>
              <h2>Your trajectory has entered the Commons Map.</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link(
            "views/commons_map.py",
            label="See the evolving map →",
            icon="🗺️",
        )
        st.divider()
    else:
        st.success(
            "Your anonymous trajectory has been added to the Commons Map.", icon="✅"
        )
    st.subheader("Would you like to help build the next step?")
    privacy_note()
    with st.form("coordination_form"):
        interest = st.radio(
            "Would you be interested in discussing strategy with other participants?",
            options=["Yes", "Not now"],
            index=None,
        )
        email = st.text_input(
            "Email (optional)",
            placeholder="you@example.org",
            help="If you choose Yes without an email, we record anonymous interest only.",
        )
        submitted = st.form_submit_button("Finish", width="stretch")
    if submitted:
        if interest is None:
            st.error("Choose Yes or Not now.")
        elif interest == "Yes" and not valid_optional_email(email):
            st.error(
                "That email address does not look complete. You can also leave it blank."
            )
        else:
            if interest == "Yes":
                try:
                    repository.record_coordination_interest(
                        participant_uuid=participant,
                        session_code=protocol.session_code,
                        email=email or None,
                        consent_version=protocol.coordination_consent_version,
                        consented_at=utc_now_iso(),
                    )
                except Exception:
                    st.error(
                        "Your coordination preference was not saved. Please try again."
                    )
                    st.stop()
            st.session_state.stage = "done"
            st.rerun()

elif stage == "skipped":
    st.subheader("Question skipped")
    st.write(
        "Your feedback was recorded, but no strategic trajectory was added because the scenario decision was skipped."
    )
    left, right = st.columns(2)
    if left.button("Return to the question", width="stretch"):
        st.session_state.stage = "scenario"
        st.rerun()
    right.page_link("views/commons_map.py", label="Open the Commons Map", icon="🗺️")

elif stage == "done":
    contact = repository.get_coordination_interest(participant)
    st.subheader("Your trajectory is in the map.")
    st.markdown("**Saved textual return key**")
    st.code(participant, language=None)
    st.markdown("**Full verification hash**")
    st.code(access_key_hash(participant), language=None)
    if contact and contact.get("coordination_status") == "reachable_interest":
        st.write(
            "Coordination interest recorded with an email. No automatic introduction will be made."
        )
    elif contact:
        st.write(
            "Anonymous coordination interest recorded. No contact route was stored."
        )
    else:
        st.write("No coordination record was created.")

    st.page_link("views/commons_map.py", label="Open the Commons Map", icon="🗺️")
    if contact:
        st.divider()
        st.caption("Contact controls")
        st.write(
            "Deleting this coordination record does not delete your anonymous strategy."
        )
        if st.button("Delete my contact data", width="stretch"):
            try:
                deleted = repository.delete_contact_data(participant)
            except Exception:
                st.error("Contact deletion did not complete. Please try again.")
            else:
                if deleted:
                    st.success(
                        "Contact data deleted. Your anonymous strategy remains in the map."
                    )
                st.rerun()

footer(protocol)
