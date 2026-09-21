"""Reusable OpenCage location adapter, ported from IceIceBaby.

Provenance:
- app_iceicebaby/conference/semantic_fields.py
- app_iceicebaby/conference/location_lookup.py
- app_iceicebaby/conference/questionnaire.py::_lookup_location_options

This module is application integration, not Probe semantics. It can be wired to
a canonical location field once the pinned Probe Engine exposes that primitive.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from typing import Any, Mapping

import requests
import streamlit as st


OPENCAGE_ENDPOINT = "https://api.opencagedata.com/geocode/v1/json"


@dataclass(frozen=True)
class LocationValue:
    display_label: str
    locality: str = ""
    region: str = ""
    country: str = ""
    country_code: str = ""
    place_id: str = ""
    latitude: float | None = None
    longitude: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value not in ("", None)
        }


def opencage_location_options(payload: Any) -> list[LocationValue]:
    """Normalize OpenCage results using the established IceIceBaby shape."""
    results = payload.get("results") if isinstance(payload, Mapping) else []
    options: list[LocationValue] = []
    for raw in results or []:
        if not isinstance(raw, Mapping):
            continue
        components = (
            raw.get("components")
            if isinstance(raw.get("components"), Mapping)
            else {}
        )
        geometry = (
            raw.get("geometry") if isinstance(raw.get("geometry"), Mapping) else {}
        )
        label = str(raw.get("formatted") or "").strip()
        if not label:
            continue
        annotations = (
            raw.get("annotations")
            if isinstance(raw.get("annotations"), Mapping)
            else {}
        )
        place_id = str(annotations.get("geohash") or "").strip()
        if not place_id:
            identity = f"{label}:{geometry.get('lat')}:{geometry.get('lng')}"
            place_id = "opencage:" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        options.append(
            LocationValue(
                display_label=label,
                locality=str(
                    components.get("city")
                    or components.get("town")
                    or components.get("village")
                    or components.get("municipality")
                    or ""
                ).strip(),
                region=str(
                    components.get("state") or components.get("region") or ""
                ).strip(),
                country=str(components.get("country") or "").strip(),
                country_code=str(components.get("country_code") or "").strip().upper(),
                place_id=place_id,
                latitude=(
                    float(geometry["lat"])
                    if geometry.get("lat") is not None
                    else None
                ),
                longitude=(
                    float(geometry["lng"])
                    if geometry.get("lng") is not None
                    else None
                ),
            )
        )
    return options


def manual_location_value(query: str) -> dict[str, Any]:
    """Preserve manual entry without pretending coordinates were resolved."""
    label = str(query or "").strip()
    if not label:
        return {}
    place_id = "manual:" + hashlib.sha256(label.casefold().encode()).hexdigest()[:20]
    return LocationValue(display_label=label, place_id=place_id).as_dict()


def opencage_api_key() -> str:
    try:
        config = st.secrets.get("opencage", {})
    except Exception:
        config = {}
    return (
        os.getenv("OPENCAGE_KEY", "").strip()
        or str(config.get("OPENCAGE_KEY", "") or "").strip()
    )


def lookup_locations(query: str, *, api_key: str) -> list[LocationValue]:
    token = str(query or "").strip()
    if len(token) < 3:
        return []
    response = requests.get(
        OPENCAGE_ENDPOINT,
        params={"q": token, "key": api_key, "limit": 5, "language": "fr"},
        timeout=8,
    )
    response.raise_for_status()
    return opencage_location_options(response.json())


def render_location_lookup(
    *, label: str, value: Any, key: str, automatic: bool = False
) -> dict[str, Any]:
    """Suggest interpreted locations after typing; preserve manual input until confirmation."""
    current = dict(value) if isinstance(value, Mapping) else {}
    query = st.text_input(
        label,
        value=str(current.get("display_label") or ""),
        placeholder="Ville ou lieu",
        label_visibility="collapsed",
        key=f"{key}_query",
    )
    token = str(query or "").strip()
    state_key = f"{key}_options"
    lookup_query_key = f"{key}_lookup_query"
    api_key = opencage_api_key()
    lookup_requested = automatic and len(token) >= 3
    if not automatic:
        lookup_requested = st.button(
            "Rechercher ce lieu",
            key=f"{key}_lookup",
            disabled=len(token) < 3 or not api_key,
        )
    if api_key and lookup_requested and st.session_state.get(lookup_query_key) != token:
        st.session_state[lookup_query_key] = token
        try:
            st.session_state[state_key] = lookup_locations(token, api_key=api_key)
        except Exception:
            st.session_state[state_key] = []
            st.warning(
                "La recherche de lieu est indisponible. Votre saisie manuelle reste utilisable."
            )
    if not api_key:
        st.caption("Recherche indisponible; la saisie manuelle reste possible.")
    options = list(st.session_state.get(state_key, []))[:5]
    selected = None
    if options:
        st.markdown("**Est-ce bien ce lieu ?**")
        selected = st.pills(
            "Est-ce bien ce lieu ?",
            options=options,
            format_func=lambda item: item.display_label,
            selection_mode="single",
            label_visibility="collapsed",
            key=f"{key}_choice",
        )
        if st.button("Modifier ma recherche", key=f"{key}_modify"):
            st.session_state[state_key] = []
            st.session_state.pop(lookup_query_key, None)
            st.rerun()
    if isinstance(selected, LocationValue):
        return selected.as_dict()
    if token == str(current.get("display_label") or "") and current.get("place_id"):
        return current
    return manual_location_value(token)
