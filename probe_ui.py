"""Generic Streamlit presentation for canonical Probe Engine definitions."""

from __future__ import annotations

import json
import re
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
from protocol.probe_draft import dump_checkpoint_draft
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


def _condition_matches(condition: Any, answers: Mapping[str, Any]) -> bool:
    if condition.operator == "any":
        return any(_condition_matches(clause, answers) for clause in condition.clauses)
    actual = answers.get(condition.field_id)
    if isinstance(actual, Mapping) and "selected" in actual:
        actual = actual.get("selected")
    if condition.operator == "contains":
        return isinstance(actual, (list, tuple, set)) and condition.value in actual
    if isinstance(actual, (list, tuple, set)):
        return condition.value in actual
    return actual == condition.value


def _is_visible(field: QuestionDefinition, answers: dict[str, Any]) -> bool:
    return field.visible_if is None or _condition_matches(field.visible_if, answers)


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
    taxonomy_presentation = dict(taxonomy.presentation) if taxonomy else {}
    collapse_groups = taxonomy_presentation.get("groups") == "expanders"
    if field.input_type == InputType.GROUPED_MULTIPLE and groups:
        for group in groups:
            current = [value for value in saved_selected if value in group.option_values]
            current = list(st.session_state.get(f"{key}_{group.id}", current))
            selected_count = len(current)
            group_title = group.label
            if taxonomy_presentation.get("show_selected_count"):
                group_title += f" · {selected_count} sélectionné{'s' if selected_count != 1 else ''}"
            target = (
                st.expander(
                    group_title,
                    expanded=taxonomy_presentation.get("default_state") == "expanded",
                )
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
        current_selection = list(st.session_state.get(key, saved_selected))
        for shortcut in field.shortcuts:
            shortcut_values = list(shortcut.select)
            shortcut_selected = bool(shortcut_values) and set(shortcut_values) <= set(
                current_selection
            )
            if st.button(
                ("✓ " if shortcut_selected else "")
                + (shortcut.label or shortcut.id or "Tout sélectionner"),
                type="secondary",
                key=f"{key}_shortcut_{shortcut.id}",
            ):
                current_selection = shortcut_values
                st.session_state[key] = shortcut_values
        selected = list(
            st.pills(
                field.prompt,
                options=option_values,
                selection_mode="multi",
                format_func=lambda value: labels.get(value, value),
                label_visibility="collapsed",
                key=key,
                **({} if key in st.session_state else {"default": current_selection}),
            )
        )
    if field.max_select is not None:
        feedback = dict(field.presentation.get("selection_feedback") or {})
        count = len(selected)
        if count > field.max_select:
            message = str(
                feedback.get("message")
                or f"Maximum : {field.max_select} choix. Retirez un choix pour continuer."
            )
            if feedback.get("over_limit") == "spectacular_soft_block":
                st.markdown(f"### ✨ {message} ✨")
            else:
                st.warning(message)
        elif count == field.max_select:
            st.info(
                str(feedback.get("at_limit") or f"Maximum atteint : {field.max_select} choix")
            )
        else:
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
                str(field.presentation.get("suggestion_label") or "Suggestions"),
                options=values,
                index=values.index(saved) if saved in values else None,
                placeholder="Choisir une suggestion ou écrire librement",
                format_func=lambda value: next(
                    item.label for item in field.suggestions if item.value == value
                ),
                key=f"{key}_suggestion",
            ) or ""
        typed = st.text_input(
            str(field.presentation.get("detail_prompt") or field.prompt),
            value=("" if saved in [item.value for item in field.suggestions] else str(saved or "")),
            placeholder=str(field.presentation.get("detail_placeholder") or "") or None,
            label_visibility=(
                "visible" if field.presentation.get("detail_prompt") else "collapsed"
            ),
            key=key,
        )
        voice_note = field.presentation.get("voice_note") or {}
        if voice_note:
            st.button(
                str(voice_note.get("label") or "Message vocal"),
                icon=":material/mic:",
                disabled=not bool(voice_note.get("enabled")),
                help=str(voice_note.get("disabled_note") or "") or None,
                key=f"{key}_voice_note",
            )
            if not voice_note.get("enabled") and voice_note.get("disabled_note"):
                st.caption(str(voice_note["disabled_note"]))
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
        return render_location_lookup(
            label=field.prompt,
            value=saved,
            key=key,
            automatic=bool(
                field.capabilities
                and field.capabilities.lookup_trigger == "after_text_input"
            ),
        )
    st.error(f"Primitive canonique non prise en charge : {field.input_type.value}")
    return None


def _render_question_actions(
    probe: ProbeDefinition,
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
                option.value: option.label
                for option in probe.resolution.flag_reasons.options
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
    trajectory_key: str,
    stage_key: str,
) -> None:
    open_key = f"probe_skip_dialog_{participation_id}_{field.id}"
    if not st.session_state.get(open_key):
        return

    @st.dialog("Passer cette question")
    def dialog() -> None:
        st.markdown(f"### {field.prompt}")
        reasons = {
            option.value: option.label
            for option in runtime.probe.resolution.skip_reasons.options
        }
        selected = st.radio(
            "Pourquoi souhaitez-vous passer ?",
            options=list(reasons),
            format_func=reasons.get,
            index=None,
            key=f"probe_skip_reason_choice_{participation_id}_{field.id}",
        )
        note = ""
        if selected is not None:
            note = st.text_input(
                "Précisons pourquoi" if selected == "other" else "Note facultative",
                key=f"probe_skip_reason_note_{participation_id}_{field.id}",
            )
        confirm_column, cancel_column = st.columns(2)
        if confirm_column.button(
            "Passer et continuer",
            type="secondary",
            width="stretch",
            disabled=selected is None or (selected == "other" and not note.strip()),
            key=f"probe_skip_confirm_{participation_id}_{field.id}",
        ):
            runtime.skip(field.id, reason_codes=[str(selected)], note=note)
            st.session_state[trajectory_key] = runtime.trajectory
            if field.skip_action == "end":
                st.session_state[stage_key] = "done"
                st.session_state[f"probe_terminal_reason_{participation_id}"] = "skipped_consent"
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
    selected = value.get("selected") if isinstance(value, Mapping) else value
    if (
        field.max_select is not None
        and isinstance(selected, (list, tuple, set))
        and len(selected) > field.max_select
    ):
        return False
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
    code = str(getattr(exc, "code", ""))
    if code == "other_detail_required" or "requires other text" in message:
        return "Précisez votre réponse « Autre » avant de continuer."
    if "other text without selecting other" in message:
        return "Le texte « Autre » ne peut être conservé que si « Autre » est sélectionné."
    if "requires a collection of options" in message:
        return "Sélectionnez un ou plusieurs choix proposés."
    if "Invalid option for question" in message:
        return "Un choix ne fait pas partie des options proposées pour cette question."
    if "requires a non-empty answer" in message:
        return "Ajoutez une réponse ou choisissez Passer."
    if code == "max_select" or "allows at most" in message:
        limit = re.search(r"allows at most (\d+)", message)
        return (
            f"Sélectionnons au maximum {limit.group(1)} réponses."
            if limit
            else "Réduisons le nombre de réponses sélectionnées."
        )
    if code == "min_select" or (
        "requires at least" in message and "selections" in message
    ):
        return message.replace("Question `", "La question « ").replace(
            "` requires at least ", " » demande au moins "
        ).replace(" selections.", " choix.")
    if code == "repeatable_required_field" and "actors" in message:
        return "Ajoutons au moins un acteur à cette étape."
    if code == "repeatable_required_field" or (
        "item" in message and "required fields" in message
    ):
        return (
            "Une étape est incomplète. Choisissez une suggestion ou saisissez "
            "une action, puis sélectionnez les éléments demandés."
        )
    if "`" in message:
        return "Cette réponse n’est pas encore complète ou valide."
    return message


def _skip_summary(probe: ProbeDefinition, event: Any) -> str:
    labels = {item.value: item.label for item in probe.resolution.skip_reasons.options}
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


def _render_probe_styles() -> None:
    """Apply a responsive hierarchy without changing canonical Probe content."""
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] h1 {
            font-size: clamp(2.35rem, 7vw, 5.5rem);
            line-height: .96;
        }
        [data-testid="stAppViewContainer"] h4 {
            font-size: clamp(1.25rem, 2.6vw, 1.75rem);
            line-height: 1.18;
        }
        [data-testid="stBaseButton-secondary"] {
            background: transparent;
            box-shadow: none;
        }
        @media (max-width: 700px) {
            [data-testid="stAppViewContainer"] h1 {
                font-size: clamp(2rem, 11vw, 3.4rem);
            }
        }
        </style>
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
    trajectory_key: str,
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
        skip_reasons = {
            option.value: option.label
            for option in probe.resolution.skip_reasons.options
        }
        skip_reason = st.selectbox(
            "Motif si vous souhaitez passer cette question",
            options=list(skip_reasons),
            index=None,
            format_func=skip_reasons.get,
            placeholder="Choisir un motif canonique",
            key=f"probe_review_skip_reason_{participation_id}_{field.id}",
        )
        skip_note = ""
        if skip_reason == "other":
            skip_note = st.text_input(
                "Précisons pourquoi",
                key=f"probe_review_skip_note_{participation_id}_{field.id}",
            )
        flag_action = _render_question_actions(
            probe,
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
                st.session_state[trajectory_key] = runtime.trajectory
            except ProbeRuntimeError as exc:
                st.error(_participant_runtime_error(exc))
            else:
                st.session_state.pop(f"probe_edit_{participation_id}", None)
                st.rerun()
        if skip_column.button(
            "Passer",
            type="secondary",
            width="stretch",
            disabled=(
                not field.skippable
                or skip_reason is None
                or (skip_reason == "other" and not skip_note.strip())
            ),
            key=f"probe_review_skip_{field.id}",
        ):
            runtime.skip(
                field.id,
                reason_codes=[str(skip_reason)],
                note=skip_note,
            )
            st.session_state[trajectory_key] = runtime.trajectory
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
            if item["operation"]
            in {"draft.session.save", "sync.arrival", "submission.commit"}
        ),
        None,
    )
    st.sidebar.markdown(
        """
        <style>
        [data-testid="stSidebar"] [data-testid="stCode"] {background:#081d18;color:#f7fff9;border:1px solid #78998f}
        [data-testid="stSidebar"] code {color:#f7fff9!important}
        [data-testid="stSidebar"] summary {color:#f7fff9!important;font-weight:650}
        [data-testid="stSidebar"] [data-testid="stAlert"] {color:#07130f}
        </style>
        """,
        unsafe_allow_html=True,
    )
    identity_debug = {
        "event_id": registration.event_id,
        "event_slug": registration.event_slug,
        "session": registration.session_code,
        "probe": f"{probe.id}@{probe.revision}",
        "probe_engine": package_version("probe-engine"),
        "pinned_commit": PROBE_ENGINE_COMMIT,
        "participation": runtime.trajectory.participation.id,
        "participant": runtime.trajectory.participation.participant_id,
        "section": current_section.id if current_section else "complete",
        "step": current_step.id if current_step else "complete",
        "test_mode": test_mode,
    }
    state = "ephemeral.session"
    if hydrated:
        state = "checkpoint.hydrated"
    latest_operation = persistence_log[-1] if persistence_log else None
    if latest_operation and latest_operation.get("success"):
        state = {
            "session.mutation": "ephemeral.session.mutated",
            "draft.hydrate": "checkpoint.hydrated",
            "draft.session.save": "checkpointed.draft",
            "draft.yaml.export": "checkpointed.draft.exported",
            "sync.arrival": "sync.arrival.recorded",
            "submission.preview": "submission.previewed",
            "submission.commit": "committed.submission",
        }.get(latest_operation["operation"], state)
    submission_commits = sum(
        1
        for item in persistence_log
        if item.get("operation") == "submission.commit" and item.get("success")
    )
    notion_request_count = submission_commits * 2
    notion_request_mode = (
        "estimated real"
        if "submission=NotionRepository" in backend and not test_mode
        else "supposed production-equivalent"
    )
    persistence_debug = {
        "backend": backend,
        "target": (
            "debug dry-run memory"
            if test_mode
            else "separate draft checkpoint and final submission stores"
        ),
        "participant": runtime.trajectory.participation.participant_id,
        "trajectory": runtime.trajectory.participation.id,
        "probe_revision": probe.revision,
        "last_persisted_event_count": (latest_write or {}).get("trajectory_event_count"),
        "last_checkpoint": last_checkpoint,
        "hydrated": hydrated,
        "state": state,
        "notion_api_requests_so_far": notion_request_count,
        "notion_api_request_count_mode": notion_request_mode,
        "notion_api_request_basis": (
            "2 requests per final commit: lookup plus create/update; pagination retries excluded"
        ),
    }
    with st.sidebar.expander("Developer · Identity", expanded=False):
        st.code(
            json.dumps(identity_debug, indent=2, ensure_ascii=False),
            language="json",
        )
    with st.sidebar.expander("Developer · Persistence", expanded=False):
        st.code(
            json.dumps(persistence_debug, indent=2, ensure_ascii=False),
            language="json",
        )
        for item in reversed(persistence_log):
            label = f"{item['timestamp']} · {item['operation']} · {'OK' if item['success'] else 'FAILED'}"
            with st.expander(label):
                st.json(item)
    checkpoint_events = [
        (index, event)
        for index, event in enumerate(events)
        if event.kind.value == "checkpoint"
    ]
    latest_checkpoint_event = checkpoint_events[-1] if checkpoint_events else None
    draft_state = "never_saved"
    if latest_checkpoint_event:
        draft_state = (
            "dirty"
            if any(
                event.kind.value in {"answered", "skipped", "flagged"}
                for event in events[latest_checkpoint_event[0] + 1 :]
            )
            else "saved"
        )
    reviewed = runtime.review()
    with st.sidebar.expander("Developer · Draft", expanded=False):
        st.code(
            json.dumps(
                {
                    "section": current_section.id if current_section else "complete",
                    "checkpoint": (
                        latest_checkpoint_event[1].metadata.get("section_id")
                        if latest_checkpoint_event
                        else None
                    ),
                    "checkpoint_state": draft_state,
                    "checkpoint_revision": probe.revision if latest_checkpoint_event else None,
                    "checkpoint_timestamp": (
                        latest_checkpoint_event[1].timestamp
                        if latest_checkpoint_event
                        else None
                    ),
                    "answers": sum(item.state.startswith("answered") for item in reviewed),
                    "skipped": sum(item.state.startswith("skipped") for item in reviewed),
                    "flagged": sum(event.kind.value == "flagged" for event in events),
                    "yaml_export": (
                        "generated"
                        if any(
                            item.get("operation") == "draft.yaml.export"
                            and item.get("success")
                            for item in persistence_log
                        )
                        else "not_generated"
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            language="json",
        )
    with st.sidebar.expander("Developer · Copy debug state", expanded=False):
        st.caption("Use the copy action on this code block.")
        st.code(
            json.dumps(
                {"identity": identity_debug, "persistence": persistence_debug},
                indent=2,
                ensure_ascii=False,
            ),
            language="json",
        )
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


def _render_checkpoint_surface(
    *,
    probe: ProbeDefinition,
    runtime: ProbeRuntime,
    store: ProbeRepositoryStore,
    section: Any,
    participation_id: str,
    trajectory_key: str,
    pending_key: str,
    stage_key: str,
) -> None:
    config = section.checkpoint_config
    st.caption(section.title.upper())
    st.title("Enregistrer cette étape")
    st.write("Mes réponses restent modifiables. Rien n’est encore soumis à la base de données.")
    st.write(
        "Vous pouvez ci-dessous télécharger un fichier contenant vos réponses "
        "jusqu’à cette étape."
    )
    boundary_rows = []
    for authored_section in probe.sections:
        saved = any(
            event.kind.value == "checkpoint"
            and event.metadata.get("section_id") == authored_section.id
            for event in runtime.trajectory.events
        )
        marker = "●" if saved else "○"
        suffix = "saved" if saved else ""
        if authored_section.id == section.id:
            suffix = "checkpoint"
        boundary_rows.append(
            f"{authored_section.title.upper()}  ──────────────{marker} {suffix}".rstrip()
        )
    st.code("\n".join(boundary_rows), language=None)

    checkpoint_indexes = [
        index
        for index, event in enumerate(runtime.trajectory.events)
        if event.kind.value == "checkpoint"
        and event.metadata.get("section_id") == section.id
    ]
    checkpointed = bool(checkpoint_indexes) and checkpoint_indexes[-1] == (
        len(runtime.trajectory.events) - 1
    )
    latest_checkpoint = (
        runtime.trajectory.events[checkpoint_indexes[-1]] if checkpoint_indexes else None
    )
    if latest_checkpoint and checkpointed:
        st.success(f"✓ Enregistré · {latest_checkpoint.timestamp}")
    elif latest_checkpoint:
        st.warning("● Modifications non enregistrées")
    else:
        st.caption("○ Jamais enregistré")
    flash_key = f"probe_checkpoint_flash_{participation_id}_{section.id}"
    if st.session_state.pop(flash_key, False):
        st.toast(
            "Étape enregistrée. Une copie YAML a été téléchargée sur votre appareil."
        )
    review_key = f"probe_checkpoint_review_{participation_id}_{section.id}"
    save_column, review_column, continue_column = st.columns(3)
    prepared = runtime.prepare_checkpoint(section.id)

    def save_checkpoint() -> None:
        runtime.commit_checkpoint(section.id, store, prepared=prepared)
        st.session_state[trajectory_key] = runtime.trajectory
        store.observe("draft.yaml.export", runtime.trajectory)
        st.session_state[flash_key] = True

    with save_column:
        if config.export_yaml:
            st.download_button(
                "Enregistrer et télécharger",
                data=dump_checkpoint_draft(probe, prepared, section_id=section.id),
                file_name=f"{probe.id}-{section.id}-brouillon.yaml",
                mime="application/yaml",
                type="secondary" if checkpointed else "primary",
                width="stretch",
                on_click=save_checkpoint,
                key=f"probe_checkpoint_save_{section.id}",
            )
        elif st.button(
            "Enregistrer",
            type="secondary" if checkpointed else "primary",
            width="stretch",
            key=f"probe_checkpoint_save_{section.id}",
        ):
            runtime.commit_checkpoint(section.id, store, prepared=prepared)
            st.session_state[trajectory_key] = runtime.trajectory
            st.session_state[flash_key] = True
            st.rerun()
    if review_column.button(
        "Relire cette section",
        width="stretch",
        disabled=not config.review,
        key=f"probe_checkpoint_review_button_{section.id}",
    ):
        st.session_state[review_key] = not bool(st.session_state.get(review_key))
        st.rerun()
    if continue_column.button(
        "Continuer",
        type="primary",
        width="stretch",
        disabled=not checkpointed,
        key=f"probe_checkpoint_continue_{section.id}",
    ):
        if section.sync_point:
            runtime.reach_sync_point(section.id, store)
            st.session_state[trajectory_key] = runtime.trajectory
        st.session_state.pop(pending_key, None)
        if section.step_ids[-1] == probe.steps[-1].id:
            st.session_state[stage_key] = "review"
        st.rerun()

    if config.review and st.session_state.get(review_key):
        review = {item.question_id: item for item in runtime.review()}
        step_ids = set(section.step_ids)
        for step in probe.steps:
            if step.id not in step_ids:
                continue
            st.subheader(step.title)
            for field_id in step.field_ids:
                item = review[field_id]
                if item.value is None and not item.state.startswith("skipped"):
                    continue
                field = probe.question(field_id)
                answer_column, edit_column = st.columns([8, 2])
                with answer_column:
                    st.markdown(f"**{field.prompt}**")
                    st.text(
                        "Question passée"
                        if item.state.startswith("skipped")
                        else _review_value(probe, field, item.value)
                    )
                with edit_column:
                    if st.button(
                        "Modifier",
                        key=f"probe_checkpoint_edit_{section.id}_{field_id}",
                    ):
                        st.session_state[f"probe_edit_{participation_id}"] = field_id
                        st.rerun()
        edit_field_id = str(st.session_state.get(f"probe_edit_{participation_id}") or "")
        if edit_field_id:
            _render_review_editor(
                probe=probe,
                runtime=runtime,
                store=store,
                field=probe.question(edit_field_id),
                participation_id=participation_id,
                trajectory_key=trajectory_key,
            )


def render_registered_probe(
    *,
    registration: RegisteredProbe,
    probe: ProbeDefinition,
    repository: Repository,
    draft_repository: Repository | None = None,
    test_mode: bool = False,
) -> None:
    _render_probe_styles()
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

    draft_repository = draft_repository or repository
    submission_backend = repository.__class__.__name__
    draft_backend = draft_repository.__class__.__name__
    backend = f"draft={draft_backend}; submission={submission_backend}"
    draft_store = ProbeRepositoryStore(
        draft_repository,
        probe_id=probe.id,
        participant_id=participant_id,
        scope_id=registration.session_code,
        diagnostic_sink=record_persistence,
        target="checkpoint drafts",
    )
    submission_store = ProbeRepositoryStore(
        repository,
        probe_id=probe.id,
        participant_id=participant_id,
        scope_id=registration.session_code,
        diagnostic_sink=record_persistence,
        target=(
            "debug dry-run memory"
            if test_mode
            else f"{submission_backend}:final submissions"
        ),
    )
    trajectory_key = f"probe_session_trajectory_{participation_id}"
    hydrated_key = f"probe_hydrated_{participation_id}"
    session_trajectory = st.session_state.get(trajectory_key)
    if session_trajectory is None:
        stored = draft_store.load(participation_id)
        if (
            stored is not None
            and stored.participation.probe_revision != probe.revision
        ):
            st.error(
                "Ce brouillon appartient à une autre révision du questionnaire. "
                "Une migration explicite est nécessaire avant de le reprendre."
            )
            with st.sidebar.expander("Developer · Draft revision", expanded=False):
                st.code(
                    json.dumps(
                        {
                            "stored_revision": stored.participation.probe_revision,
                            "current_revision": probe.revision,
                            "migration": "required",
                        },
                        indent=2,
                    ),
                    language="json",
                )
            return
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
        st.session_state[trajectory_key] = runtime.trajectory
        st.session_state[hydrated_key] = hydrated
    else:
        runtime = ProbeRuntime.hydrate(
            probe,
            session_trajectory,
            participant_id=participant_id,
            scope_id=registration.session_code,
        )
        hydrated = bool(st.session_state.get(hydrated_key))
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
    pending_checkpoint_key = f"probe_pending_checkpoint_{participation_id}"

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

    pending_checkpoint = str(st.session_state.get(pending_checkpoint_key) or "")
    if pending_checkpoint:
        _render_checkpoint_surface(
            probe=probe,
            runtime=runtime,
            store=draft_store,
            section=probe.section(pending_checkpoint),
            participation_id=participation_id,
            trajectory_key=trajectory_key,
            pending_key=pending_checkpoint_key,
            stage_key=stage_key,
        )
        return

    if stage == "done":
        terminal_reason = st.session_state.get(
            f"probe_terminal_reason_{participation_id}"
        )
        if terminal_reason in {"skipped_consent", "consent_not_accepted"}:
            st.info(
                "Vous n’avez pas accepté les modalités de participation. Votre participation "
                "n’est pas considérée comme consentie et aucune réponse ne sera soumise."
            )
        elif test_mode:
            st.success("Simulation terminée. Aucune écriture de production n’a été effectuée.")
        elif st.session_state.get(f"probe_submission_receipt_{participation_id}"):
            done = probe.step("done")
            st.title(done.title)
            st.write(done.body)
        else:
            st.warning(
                "Aucun reçu de persistance n’est disponible. "
                "Les réponses ne sont pas présentées comme enregistrées."
            )
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
                            reason = _skip_summary(probe, latest_skip) if latest_skip else ""
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
                store=draft_store,
                field=probe.question(edit_field_id),
                participation_id=participation_id,
                trajectory_key=trajectory_key,
            )
        preview_hints = probe.authoring.presentation_hints.get("submission_preview", {})
        prepared = runtime.prepare_finalisation(idempotency_key=participation_id)
        payload = submission_store.preview_payload(
            prepared,
            idempotency_key=participation_id,
        )
        if test_mode and preview_hints.get("enabled", True):
            with st.expander(
                str(preview_hints.get("title") or "Prévisualiser ce qui sera envoyé"),
                expanded=False,
            ):
                st.code(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    language="json",
                )
                st.caption(
                    "Payload exact transmis à l’adaptateur de persistance après confirmation."
                )
        if not test_mode and repository_mode() != "notion":
            st.warning(
                "L’écriture de production exige une authentification Notion configurée."
            )
        if st.button(
            "Intégrer au paysage commun",
            type="primary",
            width="stretch",
            disabled=not test_mode and repository_mode() != "notion",
        ):
            runtime.finalise(
                submission_store,
                idempotency_key=participation_id,
                prepared=prepared,
            )
            if not test_mode:
                st.session_state[f"probe_submission_receipt_{participation_id}"] = True
            st.session_state[stage_key] = "done"
            st.rerun()
        return

    informational_key = f"probe_information_steps_{participation_id}"
    visited_information_steps = set(st.session_state.get(informational_key, ()))
    step_index = 0
    for index, step in enumerate(probe.steps):
        authored_section = next(
            (item for item in probe.sections if step.id in item.step_ids),
            None,
        )
        if (
            authored_section is not None
            and not step.field_ids
            and step.id not in visited_information_steps
        ):
            step_index = index
            break
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
                st.caption(f"Question passée · {_skip_summary(probe, latest_skip)}")
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
                            f"Question passée · {_skip_summary(probe, latest_skip)}"
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
                    probe,
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
                elif field.skippable:
                    pass_clicked = st.button(
                        "Passer",
                        type="secondary",
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
                store=draft_store,
                trajectory_key=trajectory_key,
                stage_key=stage_key,
            )

    if single_question_step and visible_fields:
        field = visible_fields[0]
        skipped = review_by_id[field.id].state.startswith("skipped")
        reopened = bool(
            st.session_state.get(f"probe_reopen_{participation_id}_{field.id}")
        )
        continue_column, skip_column, flag_column = st.columns([1.6, 0.4, 0.5])
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
        skip_button_clicked = False
        if field.skippable:
            skip_button_clicked = skip_column.button(
                "Passer",
                type="secondary",
                width="stretch",
                key=f"probe_skip_{participation_id}_{field.id}",
            )
        with flag_column:
            actions[field.id] = _render_question_actions(
                probe,
                field,
                key=f"probe_action_{participation_id}_{field.id}",
                label="Signaler",
            )
        if skip_button_clicked:
            st.session_state[f"probe_skip_dialog_{participation_id}_{field.id}"] = True
            st.rerun()
        _render_skip_dialog(
            field,
            participation_id=participation_id,
            runtime=runtime,
            store=draft_store,
            trajectory_key=trajectory_key,
            stage_key=stage_key,
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
        matched_routes = [
            route
            for field in visible_fields
            for route in field.routes
            if _condition_matches(route.when, {**answers, **draft})
        ]
        return_route = next(
            (route for route in matched_routes if route.action == "return_to_information"),
            None,
        )
        if return_route:
            st.toast(str(return_route.metadata.get("toast") or "Merci de relire les informations."))
            return
        if any(route.action == "show_contact" for route in matched_routes):
            st.info("Contactez l’équipe indiquée ci-dessus avant de poursuivre.")
            return
        terminal = any(route.action == "end" for route in matched_routes)
        section = next(
            (
                item
                for item in probe.sections
                if item.step_ids and item.step_ids[-1] == step.id
            ),
            None,
        )
        st.session_state[trajectory_key] = scratch.trajectory
        if not step.field_ids:
            visited_information_steps.add(step.id)
            st.session_state[informational_key] = sorted(visited_information_steps)
        record_persistence(
            {
                "operation": "session.mutation",
                "timestamp": scratch.trajectory.events[-1].timestamp,
                "target": "browser/session state",
                "record_identity": participation_id,
                "success": True,
                "trajectory_event_count": len(scratch.trajectory.events),
                "items_affected": 1,
                "duration_ms": 0,
            }
        )
        if terminal:
            if any(
                field.id == "participation_acknowledgement"
                and draft.get(field.id) != "accept"
                for field in visible_fields
            ):
                st.session_state[
                    f"probe_terminal_reason_{participation_id}"
                ] = "consent_not_accepted"
            st.session_state[stage_key] = "done"
        elif section and section.checkpoint:
            st.session_state[pending_checkpoint_key] = section.id
        elif step_index + 1 >= len(probe.steps):
            st.session_state[stage_key] = "review"
        st.rerun()
