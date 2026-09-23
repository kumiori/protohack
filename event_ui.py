"""Registry-driven event surfaces: Probe, Results, Host, and observability."""

from __future__ import annotations

from functools import partial
from typing import Any
from urllib.parse import urlencode

import streamlit as st
from probe_engine import (
    InputType,
    ProbeRuntime,
    evaluate_representation,
    evaluate_results,
    trajectory_from_dict,
)

from probe_ui import render_registered_probe
from protocol.probe_registry import RegisteredEvent, resolve_event, resolve_probe
from storage import get_repository, repository_mode
from storage.context import get_test_repository
from storage.memory import InMemoryRepository


def event_page(event_slug: str) -> None:
    render_event(resolve_event(slug=event_slug))


def page_for_event(event: RegisteredEvent) -> Any:
    return st.Page(
        partial(event_page, event.slug),
        title=event.title,
        icon="🧭",
        url_path=event.slug,
    )


@st.cache_resource
def _draft_repository(event_id: str) -> InMemoryRepository:
    """Keep checkpoints outside the production submission repository."""
    return InMemoryRepository()


def _test_mode() -> bool:
    return (
        str(st.query_params.get("test") or "") == "1"
        or repository_mode() == "demo"
    )


def _variant(event: RegisteredEvent) -> str:
    requested = str(st.query_params.get("version") or "").strip().lower()
    return requested or (event.probes[0].variant if event.probes else "")


def _surface_links(event: RegisteredEvent) -> None:
    shared = {
        key: str(st.query_params.get(key))
        for key in ("test", "run", "version")
        if st.query_params.get(key)
    }

    def url(view: str = "") -> str:
        query = {**shared, **({"view": view} if view else {})}
        return f"/{event.slug}" + (f"?{urlencode(query)}" if query else "")

    cols = st.columns(3)
    with cols[0]:
        st.link_button("Probe", url(), width="stretch")
    with cols[1]:
        st.link_button("Results", url("results"), width="stretch")
    with cols[2]:
        st.link_button("Host", url("host"), width="stretch")


def _render_results(
    event: RegisteredEvent, *, test_mode: bool, repository: Any
) -> None:
    st.title(f"{event.title} · Results")
    st.caption("What the Probe represents · public participant-facing surface")
    if not event.results_enabled:
        st.warning("Results are disabled for this event.")
        return
    variant = _variant(event)
    try:
        registration = resolve_probe(event_slug=event.slug, variant=variant)
        probe = registration.load()
    except Exception as exc:
        with st.expander("Developer · canonical source failure"):
            st.exception(exc)
        return
    records = repository.list_probe_trajectories(
        registration.session_code, probe.id
    )
    trajectories = tuple(
        trajectory_from_dict(record["trajectory"])
        for record in records
        if record.get("integrated") and record.get("trajectory")
    )
    if test_mode:
        generate = st.toggle(
            "Generate ephemeral synthetic test data",
            value=False,
            help="Generated for this render only; never persisted.",
        )
        if generate:
            trajectories = _synthetic_trajectories(probe, registration.session_code)
            st.warning("SYNTHETIC TEST DATA · generated on this render · not persisted")
        with st.sidebar:
            st.caption(f"{len(records)} generic test envelope(s)")
            current_only = st.checkbox(
                "Current run only",
                value=True,
                help="Limits cleanup to the current run/participant batch.",
            )
            if st.button("Discard test records", type="secondary"):
                removed = repository.discard_probe_trajectories(
                    registration.session_code,
                    probe.id,
                    batch_id=(
                        str(st.query_params.get("run") or "")
                        if current_only
                        else None
                    ),
                )
                st.toast(f"{removed} test record(s) discarded.")
                st.rerun()
    if test_mode and generate:
        source_label = "données synthétiques éphémères"
        source_detail = f"{len(trajectories)} trajectoires générées · non enregistrées"
        synthetic_label = "oui · remplace les données persistées"
    elif test_mode:
        source_label = "base de test partagée"
        source_detail = f"{len(trajectories)} trajectoire(s) intégrée(s)"
        synthetic_label = "non"
    else:
        source_label = "réponses intégrées au Forum"
        source_detail = f"{len(trajectories)} trajectoire(s) intégrée(s)"
        synthetic_label = "non"
    with st.container(border=True):
        st.markdown("**Source des données**")
        st.write(source_detail)
        st.caption(
            f"Source : {source_label} · Probe : {probe.id}@{probe.revision} · "
            f"Données synthétiques : {synthetic_label}"
        )
    if not probe.representations:
        st.info("Aucune représentation n’est définie pour cette Probe.")
        return
    if not trajectories:
        st.info(
            "Les représentations sont définies, mais aucune donnée n’est encore disponible."
        )
    if probe.results is not None and trajectories:
        projection = evaluate_results(probe, trajectories)
        st.markdown(f"### {projection.title}")
        if projection.intro:
            st.write(projection.intro)
        for block in projection.blocks:
            with st.container(border=True):
                if block.kind == "narrative":
                    st.write(block.narrative)
                elif block.result is not None:
                    st.markdown(
                        f"**{block.representation_id.replace('_', ' ').title()}**"
                    )
                    with st.expander("Voir les données structurées"):
                        st.json(block.result.to_dict())
        return
    for representation in probe.representations:
        with st.container(border=True):
            st.markdown(f"**{(representation.title or representation.id.replace('_', ' ').title())}**")
            st.caption(f"{representation.type.value} · {representation.scope.value}")
            if trajectories:
                population = trajectories[:1] if representation.scope.value == "participant" else trajectories
                try:
                    result = evaluate_representation(probe, representation, population)
                except Exception as exc:
                    st.caption("Cette représentation canonique n’est pas encore disponible.")
                    with st.sidebar.expander(
                        f"Developer · representation {representation.id}"
                    ):
                        st.exception(exc)
                else:
                    st.write(f"{len(population)} contribution(s) intégrée(s)")
                    with st.expander("Voir les données structurées"):
                        st.json(result.to_dict())


def _synthetic_value(probe: Any, field: Any, index: int) -> Any:
    single = {InputType.SINGLE, InputType.SINGLE_WITH_OTHER}
    multiple = {InputType.MULTIPLE, InputType.GROUPED_MULTIPLE, InputType.MULTIPLE_WITH_OTHER}
    repeatable = {InputType.REPEATABLE, InputType.REPEATABLE_GROUP}
    options = probe.taxonomy(field.taxonomy_id).options if field.taxonomy_id else field.options
    if field.input_type in single:
        return options[index % len(options)].value if options else None
    if field.input_type in multiple:
        return [options[index % len(options)].value] if options else None
    if field.input_type in {InputType.TEXT, InputType.TEXT_WITH_SUGGESTIONS}:
        return f"Réponse synthétique {index + 1}"
    if field.input_type == InputType.URL:
        return f"https://example.test/synthetic/{index + 1}"
    if field.input_type == InputType.LOCATION:
        return {
            "display_label": "Montréal, Québec, Canada",
            "locality": "Montréal",
            "region": "Québec",
            "country": "Canada",
            "country_code": "CA",
            "place_id": "synthetic:montreal",
            "latitude": 45.5019,
            "longitude": -73.5674,
        }
    if field.input_type in repeatable:
        row = {"id": f"synthetic-{index + 1}"}
        for nested in field.item_fields:
            value = _synthetic_value(probe, nested, index)
            if value not in (None, "", []):
                row[nested.id] = value
        return [row]
    if field.input_type == InputType.BOOLEAN:
        return True
    if field.input_type == InputType.NUMBER:
        return index + 1
    return None


def _synthetic_trajectories(probe: Any, scope_id: str, count: int = 8) -> tuple[Any, ...]:
    trajectories = []
    for index in range(count):
        runtime = ProbeRuntime(
            probe,
            participant_id=f"synthetic-{index + 1}",
            participation_id=f"synthetic-{index + 1}",
            scope_id=scope_id,
        )
        for field in probe.questions:
            value = _synthetic_value(probe, field, index)
            if value is None:
                continue
            try:
                runtime.answer(field.id, value)
            except Exception:
                # Eligibility and validation remain exclusively Probe Engine decisions.
                continue
        trajectories.append(runtime.trajectory)
    return tuple(trajectories)


def _render_host(event: RegisteredEvent, *, test_mode: bool) -> None:
    st.title(f"{event.title} · Host")
    st.caption("How the event is operating · operational surface")
    if not event.host_enabled:
        st.warning("Host is disabled for this event.")
        return
    mode = "shared-test-database" if test_mode else repository_mode()
    st.metric("Registered probe variants", len(event.probes))
    st.metric("Persistence mode", mode)
    for probe in event.probes:
        with st.container(border=True):
            st.markdown(f"**{probe.variant}** · `{probe.probe_id}`")
            st.caption(f"Session namespace: {probe.session_code}")
    st.info(
        "Participation totals and coordination controls will appear when the shared "
        "repository exposes event-scoped operational queries."
    )


def render_event(event: RegisteredEvent) -> None:
    test_mode = _test_mode()
    view = str(st.query_params.get("view") or event.default_view).lower()
    if test_mode:
        st.error("TEST MODE · writes go to the shared test database only")
    try:
        repository = get_test_repository() if test_mode else get_repository()
    except RuntimeError as exc:
        st.error("La base de test partagée n’est pas configurée sur cette instance.")
        with st.sidebar.expander("Developer · test repository", expanded=True):
            st.exception(exc)
        return
    _surface_links(event)
    if view == "results":
        _render_results(event, test_mode=test_mode, repository=repository)
        return
    if view == "host":
        _render_host(event, test_mode=test_mode)
        return
    if view != "probe":
        st.error(f"Unknown event view: {view}")
        return
    variant = _variant(event)
    try:
        registration = resolve_probe(event_slug=event.slug, variant=variant)
        probe = registration.load()
    except ValueError as exc:
        st.error(f"The `{variant}` Probe variant is not registered for this event.")
        with st.sidebar.expander("Developer · routing", expanded=True):
            st.code(str(exc))
        return
    except Exception as exc:
        st.error("The canonical Probe definition could not be loaded.")
        with st.sidebar.expander("Developer · routing", expanded=True):
            st.exception(exc)
        return
    draft_repository = repository if test_mode else _draft_repository(event.id)
    render_registered_probe(
        registration=registration,
        probe=probe,
        repository=repository,
        draft_repository=draft_repository,
        test_mode=test_mode,
    )
