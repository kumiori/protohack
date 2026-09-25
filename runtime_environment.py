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
