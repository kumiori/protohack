"""Generic Streamlit presentation for canonical Probe Engine definitions."""

from __future__ import annotations

import uuid
from importlib.metadata import version as package_version
from typing import Any, Mapping

import streamlit as st
from probe_engine import (
    FieldDefinition,
    InputType,
    ProbeDefinition,
    ProbeRuntime,
    QuestionDefinition,
    RuntimeError as ProbeRuntimeError,
)

from protocol.probe_registry import PROBE_ENGINE_COMMIT, RegisteredProbe, resolve_event
from protocol.location_lookup import render_location_lookup
from protocol.probe_store import ProbeRepositoryStore
from storage.base import Repository
from storage.context import repository_mode
from track_ui import participant_uuid


def _answers(runtime: ProbeRuntime) -> dict[str, Any]:
    return {
        item.question_id: item.value
        for item in runtime.review()
        if item.value is not None
    }


def _is_visible(field: QuestionDefinition, answers: dict[str, Any]) -> bool:
    condition = field.visible_if
    if condition is None:
        return True

    def evaluate(item: Any) -> bool:
        if item.operator == "any":
            return any(evaluate(clause) for clause in item.clauses)
        actual = answers.get(item.field_id)
        if isinstance(actual, Mapping) and "selected" in actual:
            actual = actual.get("selected")
        if item.operator == "contains":
            return isinstance(actual, (list, tuple, set)) and item.value in actual
        if isinstance(actual, (list, tuple, set)):
            return item.value in actual
        return actual == item.value

    return evaluate(condition)


def _options(probe: ProbeDefinition, field: Any) -> tuple[Any, ...]:
    if field.taxonomy_id:
        return probe.taxonomy(field.taxonomy_id).options
    return field.options


def _render_multiple(
    probe: ProbeDefinition,
    field: Any,
    *,
    key: str,
    saved: Any,
) -> list[str]:
    options = _options(probe, field)
    labels = {option.value: option.label for option in options}
    if field.other.enabled:
        labels["other"] = field.other.label or "Autre"
    saved_selected = (
        list(saved.get("selected") or []) if isinstance(saved, Mapping) else list(saved or [])
    )
    saved_other = (
        str((saved.get("other") or {}).get("value") or "")
        if isinstance(saved, Mapping) and isinstance(saved.get("other"), Mapping)
        else ""
    )
    selected: list[str] = []
    taxonomy = probe.taxonomy(field.taxonomy_id) if field.taxonomy_id else None
    groups = field.option_groups or (taxonomy.groups if taxonomy else ())
    collapse_groups = bool(taxonomy and taxonomy.groups)
    if field.input_type == InputType.GROUPED_MULTIPLE and groups:
        for group in groups:
            current = [value for value in saved_selected if value in group.option_values]
            target = (
                st.expander(group.label, expanded=False)
                if collapse_groups
                else st.container()
            )
            with target:
                if not collapse_groups:
                    st.markdown(f"**{group.label}**")
                selected.extend(
                    st.pills(
                        field.prompt,
                        options=list(group.option_values),
                        default=current,
                        selection_mode="multi",
                        format_func=lambda value: labels.get(value, value),
                        label_visibility="collapsed",
                        key=f"{key}_{group.id}",
                    )
                )
        if field.other.enabled:
            selected.extend(
                st.pills(
                    field.prompt,
                    options=["other"],
                    default=["other"] if "other" in saved_selected else [],
                    selection_mode="multi",
                    format_func=labels.get,
                    label_visibility="collapsed",
                    key=f"{key}_other_choice",
                )
            )
    else:
        option_values = [option.value for option in options]
        if field.other.enabled and "other" not in option_values:
            option_values.append("other")
        selected = list(
            st.pills(
                field.prompt,
                options=option_values,
                default=saved_selected,
                selection_mode="multi",
                format_func=lambda value: labels.get(value, value),
                label_visibility="collapsed",
                key=key,
            )
        )
    if field.max_select is not None:
        st.caption(f"Maximum : {field.max_select} choix")
    if field.other.enabled and "other" in selected:
        other_text = st.text_input(
            field.other.label or "Autre",
            value=saved_other,
            placeholder=field.other.placeholder or "Précisez…",
            key=f"{key}_other",
        )
        return {"selected": selected, "other": {"value": other_text.strip()}}
    return selected


def _render_field(
    probe: ProbeDefinition,
    field: QuestionDefinition | FieldDefinition,
    *,
    key: str,
    saved: Any,
    show_prompt: bool = True,
) -> Any:
    if show_prompt:
        st.markdown(f"#### {field.prompt}")
    if show_prompt and field.context:
        st.caption(field.context)
    text_types = {InputType.TEXT, InputType.TEXT_WITH_SUGGESTIONS, InputType.URL}
    single_types = {InputType.SINGLE, InputType.SINGLE_WITH_OTHER}
    multiple_types = {
        InputType.MULTIPLE,
        InputType.GROUPED_MULTIPLE,
        InputType.MULTIPLE_WITH_OTHER,
    }
    repeatable_types = {InputType.REPEATABLE, InputType.REPEATABLE_GROUP}
    if field.input_type in text_types:
        suggestion = ""
        if field.suggestions:
            values = [item.value for item in field.suggestions]
            suggestion = st.selectbox(
                "Suggestions",
                options=values,
                index=values.index(saved) if saved in values else None,
                placeholder="Choisir une suggestion ou écrire librement",
                format_func=lambda value: next(
                    item.label for item in field.suggestions if item.value == value
                ),
                key=f"{key}_suggestion",
            ) or ""
        typed = st.text_input(
            field.prompt,
            value=("" if saved in [item.value for item in field.suggestions] else str(saved or "")),
            label_visibility="collapsed",
            key=key,
        )
        return str(typed or "").strip() or suggestion
    if field.input_type in single_types:
        options = _options(probe, field)
        values = [option.value for option in options]
        labels = {option.value: option.label for option in options}
        if field.other.enabled and "other" not in values:
            values.append("other")
            labels["other"] = field.other.label or "Autre"
        saved_selected = saved.get("selected") if isinstance(saved, Mapping) else saved
        selected = st.radio(
            field.prompt,
            options=values,
            index=values.index(saved_selected) if saved_selected in values else None,
            format_func=lambda value: labels.get(value, value),
            label_visibility="collapsed",
            key=key,
        )
        if field.other.enabled and selected == "other":
            saved_other = (
                str((saved.get("other") or {}).get("value") or "")
                if isinstance(saved, Mapping) and isinstance(saved.get("other"), Mapping)
                else ""
            )
            other_text = st.text_input(
                field.other.label or "Autre",
                value=saved_other,
                placeholder=field.other.placeholder or "Précisez…",
                key=f"{key}_other",
            )
            value: Any = {"selected": selected, "other": {"value": other_text.strip()}}
        else:
            value = selected
        if field.companions:
            saved_companions = (
                saved.get("companions", {}) if isinstance(saved, Mapping) else {}
            )
            companions = {
                companion.id: companion_value
                for companion in field.companions
                if (
                    companion_value := _render_field(
                    probe,
                    companion,
                    key=f"{key}_companion_{companion.id}",
                    saved=saved_companions.get(companion.id),
                    )
                ) not in (None, "", [])
                or companion.required
            }
            if isinstance(value, Mapping):
                value = {**value, "companions": companions}
            else:
                value = {"selected": selected, "companions": companions}
        return value
    if field.input_type in multiple_types:
        value = _render_multiple(probe, field, key=key, saved=saved)
        if field.companions:
            saved_companions = (
                saved.get("companions", {}) if isinstance(saved, Mapping) else {}
            )
            companions = {
                companion.id: companion_value
                for companion in field.companions
                if (
                    companion_value := _render_field(
                    probe,
                    companion,
                    key=f"{key}_companion_{companion.id}",
                    saved=saved_companions.get(companion.id),
                    )
                ) not in (None, "", [])
                or companion.required
            }
            if isinstance(value, Mapping):
                value = {**value, "companions": companions}
            else:
                value = {"selected": value, "companions": companions}
        return value
    if field.input_type in repeatable_types:
        return _render_repeatable(probe, field, key=key, saved=saved)
    if field.input_type == InputType.LOCATION:
        return render_location_lookup(label=field.prompt, value=saved, key=key)
    st.error(f"Primitive canonique non prise en charge : {field.input_type.value}")
    return None


def _render_question_actions(
    field: QuestionDefinition,
    *,
    key: str,
    label: str = "Signaler",
) -> dict[str, Any]:
    result = {
        "skip": False,
        "skip_reason": "",
        "flags": [],
        "flag_note": "",
    }
    if not field.skippable and not field.flaggable:
        return result
    with st.popover(label, help="Commenter cette question", width="stretch"):
        if field.flaggable:
            st.caption(
                "Signalez positivement ou négativement ce qui fonctionne, ce qui "
                "ne fonctionne pas ou mérite attention."
            )
            labels = {
                "interesting_question": "Intéressante",
                "useful_for_coordination": "Utile",
                "thought_provoking": "Stimulante",
                "well_framed": "Bien formulée",
                "incomplete": "Incomplète",
                "misleading": "Trompeuse",
                "too_narrow": "Trop étroite",
                "unclear": "Peu claire",
                "missing_option": "Option manquante",
            }
            result["flags"] = list(
                st.pills(
                    "Retour sur la question",
                    options=list(labels),
                    selection_mode="multi",
                    format_func=labels.get,
                    label_visibility="collapsed",
                    key=f"{key}_flags",
                )
            )
            result["flag_note"] = st.text_input(
                "Note facultative",
                placeholder="Courte note facultative",
                label_visibility="collapsed",
                key=f"{key}_flag_note",
            )
    return result


def _render_repeatable(
    probe: ProbeDefinition,
    field: QuestionDefinition | FieldDefinition,
    *,
    key: str,
    saved: Any,
) -> list[dict[str, Any]]:
    state_key = f"{key}_rows"
    if state_key not in st.session_state:
        st.session_state[state_key] = [dict(item) for item in (saved or [])]
    rows = st.session_state[state_key]
    for index, row in enumerate(list(rows)):
        st.markdown(f"**ÉTAPE {index + 1}**")
        updated = {"id": str(row.get("id") or uuid.uuid4().hex)}
        columns = st.columns(2, gap="large")
        for nested_index, nested in enumerate(field.item_fields):
            target = columns[nested_index] if nested_index < 2 else st.container()
            with target:
                updated[nested.id] = _render_field(
                    probe,
                    nested,
                    key=f"{key}_{updated['id']}_{nested.id}",
                    saved=row.get(nested.id),
                )
        rows[index] = updated
        if st.button("Supprimer", key=f"{key}_delete_{updated['id']}"):
            rows.pop(index)
            st.rerun()
        st.divider()
    if st.button("＋ Ajouter une étape", key=f"{key}_add"):
        rows.append({"id": uuid.uuid4().hex})
        st.rerun()
    return [dict(row) for row in rows]


def _append_flags(runtime: ProbeRuntime, field: QuestionDefinition, action: dict[str, Any]) -> None:
    existing = {
        code
        for event in runtime.trajectory.events
        if event.question_id == field.id and event.kind.value == "flagged"
        for code in event.reason_codes
    }
    added = [reason for reason in action["flags"] if reason not in existing]
    if added:
        runtime.flag(
            field.id,
            reason_codes=added,
            note=str(action["flag_note"] or ""),
        )


def _render_skip_dialog(
    field: QuestionDefinition,
    *,
    participation_id: str,
    runtime: ProbeRuntime,
    store: ProbeRepositoryStore,
) -> None:
    open_key = f"probe_skip_dialog_{participation_id}_{field.id}"
    if not st.session_state.get(open_key):
        return

    @st.dialog("Passer cette question")
    def dialog() -> None:
        st.markdown(f"### {field.prompt}")
        reasons = {
            "not_relevant": "Non applicable",
            "dont_know": "Je ne sais pas",
            "no_option_fits": (
                "La question ne me permet pas de répondre correctement"
            ),
            "other": "Autre",
        }
        selected = st.radio(
            "Pourquoi souhaitez-vous passer ?",
            options=list(reasons),
            format_func=reasons.get,
            index=None,
            key=f"probe_skip_reason_choice_{participation_id}_{field.id}",
        )
        note = st.text_input(
            "Note facultative",
            key=f"probe_skip_reason_note_{participation_id}_{field.id}",
        )
        confirm_column, cancel_column = st.columns(2)
        if confirm_column.button(
            "Passer et continuer",
            type="primary",
            width="stretch",
            disabled=selected is None,
            key=f"probe_skip_confirm_{participation_id}_{field.id}",
        ):
            runtime.skip(field.id, reason_codes=[str(selected)], note=note)
            runtime.checkpoint(store)
            st.session_state[open_key] = False
            st.rerun()
        if cancel_column.button(
            "Annuler",
            width="stretch",
            key=f"probe_skip_cancel_{participation_id}_{field.id}",
        ):
            st.session_state[open_key] = False
            st.rerun()

    dialog()


def _is_subordinate(field: QuestionDefinition) -> bool:
    """Use only Probe Engine resolution semantics; never infer from layout or ids."""
    return not field.independently_answerable


def _has_resolved_value(field: QuestionDefinition, value: Any) -> bool:
    if value in (None, "", []):
        return False
    if field.other.enabled and isinstance(value, Mapping):
        selected = value.get("selected")
        if "other" in (selected or ()):
            other = value.get("other")
            return bool(
                isinstance(other, Mapping) and str(other.get("value") or "").strip()
            )
    if field.input_type not in {InputType.REPEATABLE, InputType.REPEATABLE_GROUP}:
        return True
    if not isinstance(value, list) or not value:
        return False
    for row in value:
        if not isinstance(row, dict):
            return False
        for nested in field.item_fields:
            nested_value = row.get(nested.id)
            if nested.required and nested_value in (None, "", []):
                return False
    return True


def _participant_runtime_error(exc: Exception) -> str:
    message = str(exc)
    if "item" in message and "required fields" in message:
        return (
            "Une étape est incomplète. Choisissez une suggestion ou saisissez "
            "une action, puis sélectionnez les éléments demandés."
        )
    if "`" in message:
        return "Cette réponse n’est pas encore complète ou valide."
    return message


def _skip_summary(event: Any) -> str:
    labels = {
        "not_relevant": "Non applicable",
        "dont_know": "Je ne sais pas",
        "prefer_not_to_answer": "Je préfère ne pas répondre",
        "dont_understand": "Je ne comprends pas la question",
        "no_option_fits": "Aucune option ne convient",
        "too_difficult_briefly": "Trop difficile à résumer",
        "other": "Autre",
    }
    reasons = [labels.get(code, code) for code in event.reason_codes]
    if event.reason_note:
        reasons.append(event.reason_note)
    return " · ".join(reasons) or "sans motif"


def _render_viewport_notice() -> None:
    st.markdown(
        """
        <style>
        .probe-viewport-note { padding:.7rem .9rem; border:1px solid rgba(18,33,27,.2); border-radius:.65rem; margin:.5rem 0 1rem; font-size:.9rem; }
        .probe-viewport-note.mobile { display:none; }
        @media (max-width: 700px) {
          .probe-viewport-note.wide { display:none; }
          .probe-viewport-note.mobile { display:block; }
        }
        </style>
        <div class="probe-viewport-note mobile">Vue étroite détectée. Nous avons privilégié les choix rapides plutôt que la saisie ; vous pouvez néanmoins préciser librement vos réponses.</div>
        <div class="probe-viewport-note wide">Vue large détectée. Les interactions sont disposées côte à côte lorsque l’espace le permet et restent utilisables sur une vue plus étroite.</div>
        """,
        unsafe_allow_html=True,
    )


def _render_review_editor(
    *,
    probe: ProbeDefinition,
    runtime: ProbeRuntime,
    store: ProbeRepositoryStore,
    field: QuestionDefinition,
    participation_id: str,
) -> None:
    item = next(row for row in runtime.review() if row.question_id == field.id)
    latest = next(
        (
            event
            for event in reversed(runtime.trajectory.events)
            if event.question_id == field.id
            and event.kind.value in {"answered", "skipped"}
        ),
        None,
    )

    @st.dialog("Modifier cette réponse", width="large")
    def editor() -> None:
        st.markdown(f"### {field.prompt}")
        value = _render_field(
            probe,
            field,
            key=f"probe_review_edit_{participation_id}_{field.id}",
            saved=item.value,
        )
        skip_reason = st.text_input(
            "Motif si vous souhaitez passer cette question",
            value=(latest.reason if latest and latest.kind.value == "skipped" else ""),
            key=f"probe_review_skip_reason_{participation_id}_{field.id}",
        )
        flag_action = _render_question_actions(
            field,
            key=f"probe_review_flag_{participation_id}_{field.id}",
            label="Ajouter un signalement",
        )
        save_column, skip_column, cancel_column = st.columns(3)
        if save_column.button(
            "Enregistrer la révision",
            type="primary",
            width="stretch",
            key=f"probe_review_save_{field.id}",
        ):
            try:
                if value in (None, "", []):
                    raise ProbeRuntimeError("Ajoutez une réponse ou choisissez Passer.")
                runtime.answer(field.id, value)
                _append_flags(runtime, field, flag_action)
                runtime.checkpoint(store)
            except ProbeRuntimeError as exc:
                st.error(_participant_runtime_error(exc))
            else:
                st.session_state.pop(f"probe_edit_{participation_id}", None)
                st.rerun()
        if skip_column.button(
            "Passer",
            width="stretch",
            disabled=not field.skippable,
            key=f"probe_review_skip_{field.id}",
        ):
            runtime.skip(field.id, reason=skip_reason or "participant_skip")
            runtime.checkpoint(store)
            st.session_state.pop(f"probe_edit_{participation_id}", None)
            st.rerun()
        if cancel_column.button(
            "Annuler",
            width="stretch",
            key=f"probe_review_cancel_{field.id}",
        ):
            st.session_state.pop(f"probe_edit_{participation_id}", None)
            st.rerun()

    editor()


def _review_value(probe: ProbeDefinition, field: QuestionDefinition, value: Any) -> str:
    if field.input_type in {InputType.REPEATABLE, InputType.REPEATABLE_GROUP} and isinstance(value, list):
        actor_field = next((item for item in field.item_fields if item.id == "actors"), None)
        actor_labels = {
            option.value: option.label
            for option in (_options(probe, actor_field) if actor_field else ())
        }
        lines = []
        for item in value:
            actor_value = item.get("actors", [])
            actor_selected = (
                actor_value.get("selected", [])
                if isinstance(actor_value, Mapping)
                else actor_value
            )
            actors = " → ".join(
                actor_labels.get(actor, actor) for actor in actor_selected
            )
            if isinstance(actor_value, Mapping):
                other_text = str(
                    ((actor_value.get("other") or {}).get("value") or "")
                ).strip()
                if other_text:
                    actors = " → ".join(part for part in (actors, other_text) if part)
            lines.append(f"{item.get('action', '')} → {actors}")
        return "\n".join(lines)
    if field.input_type == InputType.LOCATION and isinstance(value, Mapping):
        return str(value.get("display_label") or "—")
    if isinstance(value, Mapping) and "selected" in value:
        selected = value.get("selected")
        values = list(selected) if isinstance(selected, (list, tuple, set)) else [selected]
        labels = {option.value: option.label for option in _options(probe, field)}
        if field.other.enabled:
            labels["other"] = field.other.label or "Autre"
        rendered = [labels.get(item, item) for item in values if item]
        other_text = str(((value.get("other") or {}).get("value") or "")).strip()
        if other_text:
            rendered.append(other_text)
        companion_values = value.get("companions") or {}
        for companion in field.companions:
            companion_value = companion_values.get(companion.id)
            if companion_value not in (None, "", []):
                rendered.append(f"{companion.prompt}: {companion_value}")
        return ", ".join(rendered)
    if isinstance(value, list):
        labels = {option.value: option.label for option in _options(probe, field)}
        return ", ".join(labels.get(item, item) for item in value)
    labels = {option.value: option.label for option in _options(probe, field)}
    return labels.get(value, str(value or "—"))


def _sidebar_debug(
    registration: RegisteredProbe,
    probe: ProbeDefinition,
    runtime: ProbeRuntime,
    *,
    test_mode: bool,
    hydrated: bool,
    persistence_log: list[dict[str, Any]],
    backend: str,
) -> None:
    answers = _answers(runtime)
    completed = {
        item.question_id
        for item in runtime.review()
        if item.state.startswith("answered") or item.state.startswith("skipped")
    }
    current_step = next(
        (
            step
            for step in probe.steps
            if not {
                field_id
                for field_id in step.field_ids
                if _is_visible(probe.question(field_id), answers)
            } <= completed
        ),
        None,
    )
    current_section = next(
        (
            section
            for section in probe.sections
            if current_step and current_step.id in section.step_ids
        ),
        None,
    )
    events = list(runtime.trajectory.events)
    last_checkpoint = next(
        (
            event.timestamp
            for event in reversed(events)
            if event.kind.value in {"checkpoint", "sync_point_reached"}
        ),
        "none",
    )
    latest_write = next(
        (
            item
            for item in reversed(persistence_log)
            if item["operation"] in {"upsert", "integrate"}
        ),
        None,
    )
    with st.sidebar.expander("Developer · Identity", expanded=True):
        st.code(
            f"event id: {registration.event_id}\n"
            f"event slug: {registration.event_slug}\n"
            f"session: {registration.session_code}\n"
            f"probe: {probe.id}@{probe.revision}\n"
            f"Probe Engine: {package_version('probe-engine')}\n"
            f"pinned commit: {PROBE_ENGINE_COMMIT}\n"
            f"participation: {runtime.trajectory.participation.id}\n"
            f"run/participant: {runtime.trajectory.participation.participant_id}\n"
            f"section: {current_section.id if current_section else 'complete'}\n"
            f"step: {current_step.id if current_step else 'complete'}\n"
            f"TEST MODE: {'YES' if test_mode else 'NO'}"
        )
    with st.sidebar.expander("Developer · Persistence", expanded=True):
        st.code(
            f"backend: {backend}\n"
            f"target: {'debug dry-run memory (no database query)' if test_mode else 'responses collection'}\n"
            f"participant/profile: {runtime.trajectory.participation.participant_id}\n"
            f"trajectory/submission: {runtime.trajectory.participation.id}\n"
            f"probe revision: {probe.revision}\n"
            f"last persisted event count: {(latest_write or {}).get('trajectory_event_count', 'none')}\n"
            f"last checkpoint: {last_checkpoint}\n"
            f"hydrated/resumed: {'YES' if hydrated else 'NO'}\n"
            f"state: {'saved' if latest_write and latest_write.get('success') else 'not yet saved'}"
        )
        for item in reversed(persistence_log):
            label = f"{item['timestamp']} · {item['operation']} · {'OK' if item['success'] else 'FAILED'}"
            with st.expander(label):
                st.json(item)
    with st.sidebar.expander("Developer · Canonical event log", expanded=False):
        chronological = st.toggle("Chronological", value=False, key="probe_event_order")
        ordered = events if chronological else list(reversed(events))
        for event in ordered:
            payload = event.to_dict()
            if payload.get("value") not in (None, "", []):
                value = payload["value"]
                payload["value"] = {
                    "redacted": True,
                    "shape": type(value).__name__,
                    "items": len(value) if isinstance(value, (list, dict)) else None,
                }
            label = f"{event.timestamp} · {event.kind.value} · {event.question_id or 'process'}"
            with st.expander(label):
                st.json(payload)
    with st.sidebar.expander("Developer · Boundaries", expanded=False):
        st.markdown("Protocol Hack ↔ Probe Engine: canonical trajectory events")
        st.markdown("Protocol Hack ↔ persistence: instrumented adapter operations")
        st.markdown("Runtime ↔ process: checkpoint and sync-point events")
        if test_mode:
            st.warning("Upserts are simulated in process memory; no database query executes.")
    with st.sidebar.expander("Developer · Capability gaps", expanded=False):
        engine_version = package_version("probe-engine")
        st.caption(
            f"Source canonique : Probe Engine {engine_version} · commit "
            f"{PROBE_ENGINE_COMMIT}."
        )
        st.info(
            f"Welcome, Review et Done sont des états d'application dans {engine_version}, "
            "pas des StepDefinition canoniques."
        )
        st.warning(
            "Les exemples facultatifs de Montréal restent déclarés comme "
            "independently_answerable dans la définition canonique."
        )
        st.warning(
            f"Probe Engine {engine_version} sait ajouter des signalements mais ne définit pas "
            "d'événement de retrait; la Review peut en ajouter, pas en supprimer."
        )
        st.warning(
            "Aucun composant GPS navigateur n'existe dans la référence IceIceBaby; "
            "son aide de localisation est une recherche textuelle OpenCage."
        )


def render_registered_probe(
    *,
    registration: RegisteredProbe,
    probe: ProbeDefinition,
    repository: Repository,
    test_mode: bool = False,
) -> None:
    participant_id = participant_uuid()
    participation_key = f"probe_participation_{registration.session_code}"
    derived_participation_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"{registration.session_code}:{probe.id}:{participant_id}",
    ).hex
    participation_id = str(
        st.query_params.get("participation")
        or st.session_state.get(participation_key)
        or derived_participation_id
    )
    st.session_state[participation_key] = participation_id
    persistence_key = f"probe_persistence_log_{participation_id}"
    persistence_log = st.session_state.setdefault(persistence_key, [])

    def record_persistence(item: dict[str, Any]) -> None:
        persistence_log.append(item)
        del persistence_log[:-50]

    backend = repository.__class__.__name__
    store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id=participant_id,
        scope_id=registration.session_code,
        diagnostic_sink=record_persistence,
        target=(
            "debug dry-run memory"
            if test_mode
            else f"{backend}:responses"
        ),
    )
    stored = store.load(participation_id)
    hydrated = stored is not None
    runtime = (
        ProbeRuntime.hydrate(
            probe,
            stored,
            participant_id=participant_id,
            scope_id=registration.session_code,
        )
        if stored
        else ProbeRuntime(
            probe,
            participant_id=participant_id,
            scope_id=registration.session_code,
            participation_id=participation_id,
        )
    )
    _sidebar_debug(
        registration,
        probe,
        runtime,
        test_mode=test_mode,
        hydrated=hydrated,
        persistence_log=persistence_log,
        backend=backend,
    )
    if test_mode:
        st.error("TEST MODE · DRY RUN · no production database writes")
    elif repository_mode() == "demo":
        st.error(
            "TEST MODE · stockage temporaire en mémoire · les réponses disparaîtront "
            "au redémarrage du processus"
        )
    answers = _answers(runtime)
    completed = {
        item.question_id
        for item in runtime.review()
        if item.state.startswith("answered") or item.state.startswith("skipped")
    }
    stage_key = f"probe_stage_{participation_id}"
    stage = str(st.session_state.get(stage_key) or "welcome")

    if stage == "welcome":
        st.title(probe.title)
        st.write("Questionnaire participant · environ 20 minutes")
        _render_viewport_notice()
        event = resolve_event(event_id=registration.event_id)
        for paragraph in event.participant_intro:
            st.write(paragraph)
        if st.button("Commencer", type="primary", width="stretch"):
            st.session_state[stage_key] = "steps"
            st.rerun()
        return

    if stage == "done":
        st.success("Merci. Vos réponses ont bien été enregistrées.")
        return

    if stage == "review":
        st.title("Relire vos réponses")
        review = {item.question_id: item for item in runtime.review()}
        for step in probe.steps:
            st.subheader(step.title)
            for field_id in step.field_ids:
                item = review[field_id]
                field = probe.question(field_id)
                if item.value is None and not item.state.startswith("skipped"):
                    continue
                with st.container(border=True):
                    answer_column, edit_column = st.columns(
                        [8, 2], gap="small", vertical_alignment="center"
                    )
                    with answer_column:
                        st.markdown(f"**{field.prompt}**")
                        if item.state.startswith("skipped"):
                            latest_skip = next(
                                (
                                    event
                                    for event in reversed(runtime.trajectory.events)
                                    if event.question_id == field_id
                                    and event.kind.value == "skipped"
                                ),
                                None,
                            )
                            reason = _skip_summary(latest_skip) if latest_skip else ""
                            st.caption(
                                "Question passée"
                                + (f" · {reason}" if reason else "")
                            )
                        else:
                            st.text(_review_value(probe, field, item.value))
                        if item.flags:
                            st.caption("Signalée · " + " · ".join(item.flags))
                    with edit_column:
                        if st.button(
                            "Modifier",
                            icon=":material/edit:",
                            type="tertiary",
                            key=f"probe_review_edit_button_{field_id}",
                        ):
                            st.session_state[f"probe_edit_{participation_id}"] = field_id
                            st.rerun()
        edit_field_id = str(
            st.session_state.get(f"probe_edit_{participation_id}") or ""
        )
        if edit_field_id:
            _render_review_editor(
                probe=probe,
                runtime=runtime,
                store=store,
                field=probe.question(edit_field_id),
                participation_id=participation_id,
            )
        if st.button(
            "Intégrer au paysage commun",
            type="primary",
            width="stretch",
        ):
            runtime.finalise(store, idempotency_key=participation_id)
            st.session_state[stage_key] = "done"
            st.rerun()
        return

    step_index = 0
    for index, step in enumerate(probe.steps):
        visible_ids = [
            field_id
            for field_id in step.field_ids
            if _is_visible(probe.question(field_id), answers)
        ]
        if not set(visible_ids) <= completed:
            step_index = index
            break
    else:
        st.session_state[stage_key] = "review"
        st.rerun()
        return

    step = probe.steps[step_index]
    st.progress((step_index + 1) / len(probe.steps), text=f"Étape {step_index + 1} sur {len(probe.steps)}")
    section = next(
        (item for item in probe.sections if step.id in item.step_ids),
        None,
    )
    if section:
        st.caption(section.title.upper())
    st.title(step.title)
    if step.body:
        st.write(step.body)
    draft: dict[str, Any] = {}
    actions: dict[str, dict[str, Any]] = {}
    visible_fields: list[QuestionDefinition] = []
    review_by_id = {item.question_id: item for item in runtime.review()}
    visibility_answers = dict(answers)
    for field_id in step.field_ids:
        widget_key = f"probe_{participation_id}_{field_id}"
        if widget_key in st.session_state:
            visibility_answers[field_id] = st.session_state[widget_key]
    initially_visible = [
        field_id
        for field_id in step.field_ids
        if _is_visible(probe.question(field_id), visibility_answers)
    ]
    single_question_step = len(initially_visible) == 1
    for field_id in step.field_ids:
        field = probe.question(field_id)
        if not _is_visible(field, {**answers, **draft}):
            continue
        visible_fields.append(field)
        action_key = f"probe_action_{participation_id}_{field.id}"
        reopen_key = f"probe_reopen_{participation_id}_{field.id}"
        skipped = review_by_id[field.id].state.startswith("skipped")
        reopened = bool(st.session_state.get(reopen_key))
        if single_question_step:
            if skipped and not reopened:
                st.markdown(f"#### {field.prompt}")
                latest_skip = next(
                    event
                    for event in reversed(runtime.trajectory.events)
                    if event.question_id == field.id and event.kind.value == "skipped"
                )
                st.caption(f"Question passée · {_skip_summary(latest_skip)}")
                if st.button("Modifier", key=f"probe_reopen_button_{field.id}"):
                    st.session_state[reopen_key] = True
                    st.rerun()
            else:
                draft[field.id] = _render_field(
                    probe,
                    field,
                    key=f"probe_{participation_id}_{field.id}",
                    saved=answers.get(field.id),
                )
        else:
            st.markdown(f"#### {field.prompt}")
            answer_column, flag_column, skip_column = st.columns(
                [8, 2, 1.5], vertical_alignment="top"
            )
            with answer_column:
                if skipped and not reopened:
                    latest_skip = next(
                        event
                        for event in reversed(runtime.trajectory.events)
                        if event.question_id == field.id
                        and event.kind.value == "skipped"
                    )
                    with st.container(border=True):
                        st.caption(
                            f"Question passée · {_skip_summary(latest_skip)}"
                        )
                else:
                    draft[field.id] = _render_field(
                        probe,
                        field,
                        key=f"probe_{participation_id}_{field.id}",
                        saved=answers.get(field.id),
                        show_prompt=False,
                    )
            with flag_column:
                actions[field.id] = _render_question_actions(
                    field,
                    key=action_key,
                    label="Signaler",
                )
            with skip_column:
                if skipped and not reopened:
                    reopen_clicked = st.button(
                        "Modifier",
                        width="stretch",
                        key=f"probe_reopen_button_{field.id}",
                    )
                    if reopen_clicked:
                        st.session_state[reopen_key] = True
                        st.rerun()
                else:
                    pass_clicked = st.button(
                        "Passer",
                        width="stretch",
                        disabled=not field.skippable,
                        key=f"probe_skip_{participation_id}_{field.id}",
                    )
                    if pass_clicked:
                        st.session_state[
                            f"probe_skip_dialog_{participation_id}_{field.id}"
                        ] = True
                        st.rerun()
            _render_skip_dialog(
                field,
                participation_id=participation_id,
                runtime=runtime,
                store=store,
            )

    if single_question_step and visible_fields:
        field = visible_fields[0]
        skipped = review_by_id[field.id].state.startswith("skipped")
        reopened = bool(
            st.session_state.get(f"probe_reopen_{participation_id}_{field.id}")
        )
        continue_column, flag_column, skip_column = st.columns([1.6, 0.5, 0.4])
        single_resolved = _has_resolved_value(field, draft.get(field.id)) or (
            skipped and not reopened
        )
        continue_clicked = continue_column.button(
            step.cta or "Continuer",
            type="primary",
            width="stretch",
            disabled=not single_resolved,
            key=f"probe_continue_{participation_id}_{step.id}",
        )
        with flag_column:
            actions[field.id] = _render_question_actions(
                field,
                key=f"probe_action_{participation_id}_{field.id}",
                label="Signaler",
            )
        skip_button_clicked = skip_column.button(
            "Passer",
            width="stretch",
            disabled=not field.skippable,
            key=f"probe_skip_{participation_id}_{field.id}",
        )
        if skip_button_clicked:
            st.session_state[f"probe_skip_dialog_{participation_id}_{field.id}"] = True
            st.rerun()
        _render_skip_dialog(
            field,
            participation_id=participation_id,
            runtime=runtime,
            store=store,
        )
    else:
        unresolved = [
            field
            for field in visible_fields
            if not _is_subordinate(field)
            and not (
                review_by_id[field.id].state.startswith("skipped")
                and not st.session_state.get(
                    f"probe_reopen_{participation_id}_{field.id}"
                )
            )
            and not _has_resolved_value(field, draft.get(field.id))
        ]
        continue_clicked = st.button(
            step.cta or "Continuer",
            type="primary",
            width="stretch",
            disabled=bool(unresolved),
            key=f"probe_continue_{participation_id}_{step.id}",
        )

    if continue_clicked:
        scratch = ProbeRuntime.hydrate(
            probe,
            runtime.trajectory,
            participant_id=participant_id,
            scope_id=registration.session_code,
        )
        try:
            for field in visible_fields:
                value = draft.get(field.id)
                action = actions.get(
                    field.id,
                    {"flags": [], "flag_note": "", "skip": False, "skip_reason": ""},
                )
                skipped = review_by_id[field.id].state.startswith("skipped")
                reopened = bool(
                    st.session_state.get(f"probe_reopen_{participation_id}_{field.id}")
                )
                if skipped and not reopened:
                    _append_flags(scratch, field, action)
                    continue
                if not _has_resolved_value(field, value) and _is_subordinate(field):
                    _append_flags(scratch, field, action)
                    continue
                if not _has_resolved_value(field, value):
                    raise ProbeRuntimeError(
                        f"Répondez à « {field.prompt} » ou choisissez Passer."
                    )
                if value != answers.get(field.id) or skipped:
                    scratch.answer(field.id, value)
                st.session_state.pop(
                    f"probe_reopen_{participation_id}_{field.id}", None
                )
                _append_flags(scratch, field, action)
        except ProbeRuntimeError as exc:
            st.error(_participant_runtime_error(exc))
            return
        terminal = any(
            route.action == "end"
            and route.when.operator == "equals"
            and draft.get(route.when.field_id) == route.when.value
            for field in visible_fields
            for route in field.routes
        )
        section = next(
            (
                item
                for item in probe.sections
                if item.step_ids and item.step_ids[-1] == step.id
            ),
            None,
        )
        if section and (section.checkpoint or section.sync_point):
            scratch.reach_section_boundary(section.id, store)
        else:
            scratch.checkpoint(store)
        if terminal:
            st.session_state[stage_key] = "done"
        elif step_index + 1 >= len(probe.steps):
            st.session_state[stage_key] = "review"
        st.rerun()
