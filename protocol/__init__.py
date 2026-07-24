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
from .question_sets import (
    BundleValidation,
    QuestionDefinition,
    QuestionSetBundle,
    QuestionSetCatalog,
    load_question_set,
    load_question_set_catalog,
)
from .submissions import build_question_set_submission

__all__ = [
    "Action",
    "Decision",
    "InteractionContract",
    "Protocol",
    "Scenario",
    "QUESTION_FLAG_LABELS",
    "QUESTION_FLAG_OPTIONS",
    "BundleValidation",
    "QuestionDefinition",
    "QuestionSetBundle",
    "QuestionSetCatalog",
    "access_key_emoji",
    "access_key_hash",
    "build_question_feedback",
    "build_question_set_submission",
    "build_strategic_profile",
    "load_protocol",
    "load_question_set",
    "load_question_set_catalog",
    "normalize_access_key",
    "normalize_question_feedback",
    "normalize_rationale",
    "participant_alias",
]
