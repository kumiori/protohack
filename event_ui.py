"""Registry-driven event surfaces: Probe, Results, Host, and observability."""

from __future__ import annotations

from functools import partial
from typing import Any
from urllib.parse import urlencode

import streamlit as st
from probe_engine import InputType, ProbeRuntime, evaluate_representation, evaluate_results

from probe_ui import render_registered_probe
from protocol.probe_registry import RegisteredEvent, resolve_event, resolve_probe
from storage import get_repository, repository_mode
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
def _debug_repository(event_id: str) -> InMemoryRepository:
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


def _render_results(event: RegisteredEvent, *, test_mode: bool) -> None:
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
    trajectories = ()
    if test_mode:
        generate = st.toggle(
            "Generate ephemeral synthetic test data",
            value=False,
            help="Generated for this render only; never persisted.",
        )
        if generate:
            trajectories = _synthetic_trajectories(probe, registration.session_code)
            st.warning("SYNTHETIC TEST DATA · generated on this render · not persisted")
    st.subheader("Canonical representations")
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
    mode = "dry-run" if test_mode else repository_mode()
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
        st.error("TEST MODE · DRY RUN · no production database writes")
    _surface_links(event)
    if view == "results":
        _render_results(event, test_mode=test_mode)
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
    repository = _debug_repository(event.id) if test_mode else get_repository()
    render_registered_probe(
        registration=registration,
        probe=probe,
        repository=repository,
        test_mode=test_mode,
    )
