"""Human-facing representations of the anonymous participant return key."""

from __future__ import annotations

import hashlib
import uuid


EMOJI_ALPHABET = (
    "◆",
    "✨",
    "🌋",
    "🏅",
    "🌊",
    "🌱",
    "🧭",
    "🪨",
    "🌙",
    "☀️",
    "🌀",
    "🔶",
)


def normalize_access_key(value: str) -> str:
    """Return the canonical UUID form or raise a participant-safe error."""

    try:
        return str(uuid.UUID(str(value or "").strip()))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Enter the complete textual access key.") from exc


def access_key_hash(access_key: str) -> str:
    canonical = normalize_access_key(access_key)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def access_key_emoji(access_key: str, *, symbols: int = 4) -> str:
    digest = hashlib.sha256(normalize_access_key(access_key).encode("utf-8")).digest()
    return "".join(EMOJI_ALPHABET[value % len(EMOJI_ALPHABET)] for value in digest[:symbols])
