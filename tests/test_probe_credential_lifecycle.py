from protocol.probe_access import (
    access_code_from_key,
    credential_for_player,
    latest_returning_record,
    resolve_probe_access_input,
)


ACCESS_KEY = "12345678-1234-5678-1234-567812345678"


def test_complete_emoji_credential_and_suffixes_are_one_derivation() -> None:
    code = access_code_from_key(ACCESS_KEY)

    assert code.emoji == "🌑🌌🟥🎯🗝️♾️🌑🧊🔥⚡✨⬛🔻⬜🪙🔥💎🌊🌓⚡🛠️🔻"
    assert len(code.emoji_symbols) > 6
    assert code.selector == "".join(code.emoji_symbols[-4:])
    assert code.selector_6 == "".join(code.emoji_symbols[-6:])
    assert resolve_probe_access_input(code.emoji) == (code.selector, code.verifier)


def test_returning_player_keeps_credential_and_selects_latest_response() -> None:
    generated = []

    def mint():
        generated.append(ACCESS_KEY)
        return access_code_from_key(ACCESS_KEY)

    original = credential_for_player(existing=None, mint=mint)
    rows = [
        {
            "participant_id": "P1",
            "submission_id": "R1",
            "integrated_at": "2026-09-24T10:00:00+00:00",
            "access_code_emoji": original.emoji,
            "access_code_selector": original.selector,
            "access_code_verifier": original.verifier,
        },
        {
            "participant_id": "P1",
            "submission_id": "R2",
            "integrated_at": "2026-09-24T11:00:00+00:00",
            "access_code_emoji": original.emoji,
            "access_code_selector": original.selector,
            "access_code_verifier": original.verifier,
        },
    ]

    latest = latest_returning_record(rows, supplied_verifier=original.verifier)
    recovered = credential_for_player(existing=latest, mint=mint)

    assert latest["submission_id"] == "R2"
    assert recovered == original
    assert len(generated) == 1


def test_unchanged_returning_retry_never_invokes_generator() -> None:
    original = access_code_from_key(ACCESS_KEY)

    def forbidden():
        raise AssertionError("credential generator called for returning Player")

    recovered = credential_for_player(
        existing={
            "access_code_emoji": original.emoji,
            "access_code_selector": original.selector,
            "access_code_verifier": original.verifier,
        },
        mint=forbidden,
    )

    assert recovered == original
