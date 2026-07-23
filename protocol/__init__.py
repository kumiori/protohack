"""Protocol definitions and deterministic profile construction."""

from .access_keys import access_key_emoji, access_key_hash, normalize_access_key
from .domain import build_strategic_profile, normalize_rationale, participant_alias
from .feedback import (
    QUESTION_FLAG_LABELS,
    QUESTION_FLAG_OPTIONS,
    build_question_feedback,
    normalize_question_feedback,
)
from .loader import load_protocol
from .models import Action, Decision, InteractionContract, Protocol, Scenario

__all__ = [
    "Action",
    "Decision",
    "InteractionContract",
    "Protocol",
    "Scenario",
    "QUESTION_FLAG_LABELS",
    "QUESTION_FLAG_OPTIONS",
    "access_key_emoji",
    "access_key_hash",
    "build_question_feedback",
    "build_strategic_profile",
    "load_protocol",
    "normalize_access_key",
    "normalize_question_feedback",
    "normalize_rationale",
    "participant_alias",
]
