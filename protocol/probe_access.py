"""Participant return codes for persistent Probe trajectories.

The flow follows IceIceBaby Prediction: the full random key remains the source
credential, while a four-emoji suffix is the human-facing selector used to
recover a stored participant record.  Collision checks happen before a code is
shown to the participant.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Callable, Iterable

from .access_keys import access_key_emoji, access_key_hash, normalize_access_key


@dataclass(frozen=True)
class ProbeAccessCode:
    full_key: str
    selector: str
    verifier: str


def normalize_emoji_selector(value: str) -> str:
    """Normalize the copy/paste form used by the four-emoji login field."""

    return "".join(str(value or "").split())


def access_code_from_key(full_key: str) -> ProbeAccessCode:
    canonical = normalize_access_key(full_key)
    selector = access_key_emoji(canonical, symbols=4)
    return ProbeAccessCode(
        full_key=canonical,
        selector=selector,
        verifier=access_key_hash(canonical),
    )


def resolve_probe_access_input(value: str) -> tuple[str, str | None]:
    """Resolve either a full Prediction token or its four-emoji shorthand."""

    raw = str(value or "").strip()
    try:
        code = access_code_from_key(raw)
    except ValueError:
        selector = normalize_emoji_selector(raw)
        if not selector:
            raise ValueError("Saisissez votre code d’accès.")
        return selector, None
    return code.selector, code.verifier


def mint_probe_access_code(
    existing_selectors: Callable[[str], Iterable[object]],
    *,
    attempts: int = 32,
) -> ProbeAccessCode:
    """Mint a collision-free Prediction-style short code."""

    for _ in range(attempts):
        code = access_code_from_key(str(uuid.uuid4()))
        if not tuple(existing_selectors(code.selector)):
            return code
    raise RuntimeError("Impossible de créer un code d’accès unique pour le moment.")
