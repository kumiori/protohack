"""Small deployment-surface decisions shared by the Streamlit entrypoint."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import streamlit as st


def is_local_runtime() -> bool:
    """Return whether this request is served from a local Streamlit address.

    ``PROTOHACK_ENVIRONMENT`` is the explicit deployment override. The request
    URL is the normal runtime signal, including on the landing page.
    """

    configured = str(os.getenv("PROTOHACK_ENVIRONMENT", "") or "").strip().lower()
    if configured in {"production", "prod", "deployed", "remote"}:
        return False
    if configured in {"local", "development", "dev", "test"}:
        return True
    try:
        hostname = str(urlparse(st.context.url).hostname or "").lower()
    except Exception:
        hostname = ""
    return hostname in {"", "localhost", "127.0.0.1", "::1"}


def developer_sidebar_enabled(query_params: object | None = None) -> bool:
    """Expose developer diagnostics locally or through an explicit URL opt-in."""

    if is_local_runtime():
        return True
    params = st.query_params if query_params is None else query_params
    try:
        raw = params.get("developer", "")  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        raw = ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}
