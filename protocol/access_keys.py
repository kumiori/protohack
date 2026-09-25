"""Human-facing representations of the anonymous participant return key."""

from __future__ import annotations

import hashlib
import math
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

# Prediction's complete credential projection: 128 bits expressed losslessly
# in a curated 64-symbol alphabet. Short codes are suffixes of this value.
FULL_EMOJI_ALPHABET = (
    "🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘",
    "⭐", "🌟", "✨", "⚡", "🔥", "💧", "🌊", "🌬️",
    "🌀", "🌈", "❄️", "☄️", "🌋", "💎", "🧊", "🪐",
    "🌌", "🎇", "🎆", "🎈", "🎉", "🎯", "🎲", "🧠",
    "🫧", "🧬", "🔮", "🪄", "🛰️", "🚀", "🛸", "🛠️",
    "⚙️", "📡", "🔑", "🗝️", "📀", "💾", "🧲", "🪙",
    "🥇", "🎖️", "🔰", "♾️", "🪬", "🔺", "🔻", "🔷",
    "🔶", "⬛", "⬜", "🟥", "🟩", "🟦", "🟨",
)
FULL_EMOJI_SYMBOLS = math.ceil(128 / math.log2(len(FULL_EMOJI_ALPHABET)))


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


def access_key_full_emoji(access_key: str) -> str:
    """Return the lossless Prediction-style emoji projection of a UUID key."""

    value = uuid.UUID(normalize_access_key(access_key)).int
    digits: list[str] = []
    base = len(FULL_EMOJI_ALPHABET)
    while value:
        value, remainder = divmod(value, base)
        digits.append(FULL_EMOJI_ALPHABET[remainder])
    while len(digits) < FULL_EMOJI_SYMBOLS:
        digits.append(FULL_EMOJI_ALPHABET[0])
    return "".join(reversed(digits))


def split_full_emoji(value: str) -> tuple[str, ...]:
    compact = "".join(str(value or "").split())
    symbols: list[str] = []
    offset = 0
    candidates = sorted(FULL_EMOJI_ALPHABET, key=len, reverse=True)
    while offset < len(compact):
        symbol = next(
            (item for item in candidates if compact.startswith(item, offset)),
            None,
        )
        if symbol is None:
            raise ValueError("Unknown emoji in access credential.")
        symbols.append(symbol)
        offset += len(symbol)
    return tuple(symbols)


def full_emoji_to_access_key(value: str) -> str:
    symbols = split_full_emoji(value)
    if len(symbols) != FULL_EMOJI_SYMBOLS:
        raise ValueError("Complete emoji credential has an invalid length.")
    index = {symbol: position for position, symbol in enumerate(FULL_EMOJI_ALPHABET)}
    number = 0
    for symbol in symbols:
        number = number * len(FULL_EMOJI_ALPHABET) + index[symbol]
    if number >= 2**128:
        raise ValueError("Complete emoji credential is outside the valid range.")
    return str(uuid.UUID(int=number))
