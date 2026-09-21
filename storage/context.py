"""Select real Notion storage or an explicit, visible demo repository."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

from .base import Repository
from .memory import InMemoryRepository
from .notion import NotionRepository


def _secret(section: str, key: str) -> str:
    try:
        value: Any = st.secrets.get(section, {}).get(key, "")
    except Exception:
        value = ""
    return str(value or "").strip()


def notion_token() -> str:
    """Return the configured Notion integration credential.

    ``notion.api_key`` is the established secret name in this application.
    The Protocol Hack-specific and generic token aliases remain supported for
    environment-specific deployments.
    """

    return (
        os.getenv("PROTOHACK_NOTION_TOKEN", "").strip()
        or os.getenv("NOTION_TOKEN", "").strip()
        or _secret("notion", "protohack_token")
        or _secret("notion", "token")
        or _secret("notion", "api_key")
    )


def repository_mode() -> str:
    forced_demo = os.getenv("PROTOHACK_DEMO_MODE", "").lower() in {"1", "true", "yes"}
    token = notion_token()
    return "demo" if forced_demo or not token else "notion"


@st.cache_resource
def _memory_repository() -> InMemoryRepository:
    return InMemoryRepository()


@st.cache_resource
def _notion_repository(token: str) -> NotionRepository:
    return NotionRepository(
        token=token,
        notion_version=os.getenv("NOTION_VERSION", "2025-09-03"),
    )


def get_repository() -> Repository:
    if repository_mode() == "demo":
        return _memory_repository()
    return _notion_repository(notion_token())
