"""Participant return codes for persistent Probe trajectories.

The flow follows IceIceBaby Prediction: the full random key remains the source
credential, while a four-emoji suffix is the human-facing selector used to
recover a stored participant record.  Collision checks happen before a code is
shown to the participant.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Any, Callable, Iterable, Mapping

from .access_keys import (
    access_key_full_emoji,
    access_key_hash,
    full_emoji_to_access_key,
    normalize_access_key,
    split_full_emoji,
)


@dataclass(frozen=True)
class ProbeAccessCode:
    full_key: str
    emoji: str
    selector: str
    selector_6: str
    verifier: str

    @property
    def emoji_symbols(self) -> tuple[str, ...]:
        return split_full_emoji(self.emoji) if self.emoji else ()


def normalize_emoji_selector(value: str) -> str:
    """Normalize the copy/paste form used by the four-emoji login field."""

    return "".join(str(value or "").split())


def access_code_from_key(full_key: str) -> ProbeAccessCode:
    canonical = normalize_access_key(full_key)
    emoji = access_key_full_emoji(canonical)
    symbols = split_full_emoji(emoji)
    return ProbeAccessCode(
        full_key=canonical.upper(),
        emoji=emoji,
        selector="".join(symbols[-4:]),
        selector_6="".join(symbols[-6:]),
        verifier=access_key_hash(canonical),
    )


def resolve_probe_access_input(value: str) -> tuple[str, str | None]:
    """Resolve either a full Prediction token or its four-emoji shorthand."""

    raw = str(value or "").strip()
    try:
        try:
            code = access_code_from_key(raw)
        except ValueError:
            code = access_code_from_key(full_emoji_to_access_key(raw))
    except ValueError:
        selector = normalize_emoji_selector(raw)
        if not selector:
            raise ValueError("Saisissez votre code d’accès.")
        return selector, None
    return code.selector, code.verifier


def credential_for_player(
    *,
    existing: Mapping[str, Any] | None,
    mint: Callable[[], ProbeAccessCode],
) -> ProbeAccessCode:
    """Return a Player's immutable credential, minting only for a new Player."""

    if existing is None:
        return mint()
    emoji = str(existing.get("emoji") or existing.get("access_code_emoji") or "")
    selector = str(existing.get("selector") or existing.get("access_code_selector") or "")
    selector_6 = str(
        existing.get("selector_6") or existing.get("access_code_selector_6") or ""
    )
    verifier = str(existing.get("verifier") or existing.get("access_code_verifier") or "")
    if emoji:
        code = access_code_from_key(full_emoji_to_access_key(emoji))
        if selector and selector != code.selector:
            raise ValueError("Stored Player selector does not match its credential.")
        if verifier and verifier != code.verifier:
            raise ValueError("Stored Player verifier does not match its credential.")
        return code
    if selector and verifier:
        # Read-only compatibility for pre-full-emoji Players. Never mint a new
        # identity merely because historical projection data is incomplete.
        return ProbeAccessCode(
            full_key="",
            emoji="",
            selector=selector,
            selector_6=selector_6,
            verifier=verifier,
        )
    raise ValueError("Stored Player credential is incomplete.")


def latest_returning_record(
    records: Iterable[Mapping[str, Any]], *, supplied_verifier: str | None
) -> dict[str, Any]:
    """Resolve one Player and its latest integrated Response revision."""

    matches = []
    for source in records:
        row = dict(source)
        player = dict(row.get("player") or {})
        credential = dict(player.get("credential") or {})
        verifier = str(
            credential.get("verifier") or row.get("access_code_verifier") or ""
        )
        if supplied_verifier is None or verifier == supplied_verifier:
            matches.append(row)
    participants = {str(row.get("participant_id") or "") for row in matches}
    participants.discard("")
    if len(participants) != 1:
        raise ValueError(
            "Ce code ne correspond pas à une participation unique dans cet environnement."
        )
    return max(
        matches,
        key=lambda row: (
            str(row.get("integrated_at") or row.get("updated_at") or ""),
            int(row.get("revision") or 0),
            str(row.get("submission_id") or ""),
        ),
    )


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
