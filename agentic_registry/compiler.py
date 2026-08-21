"""Compile the source YAML into renderer-neutral protocol-map artifacts.

This module is the sole semantic owner for the two protocol-map renderers.  UI
code must consume its JSON contracts and must not interpret the YAML directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import yaml


ARTIFACT_CONTRACT_VERSION = "agentic_protocol_map_v2"
COLLECTIONS_WITH_IDS = (
    "actors",
    "protocols",
    "protocol_versions",
    "protocol_events",
    "actor_protocol_relations",
    "protocol_protocol_relations",
    "protocol_regimes",
    "protocol_transitions",
    "frontier_candidates",
    "evidence_sources",
)
DATE_PRECISIONS = {"day", "month", "year", "unknown"}
REGIME_TYPES = {
    "stewardship",
    "governance",
    "repository_control",
    "technical_maintenance",
}
REGIME_STATUSES = {"verified", "announced", "unknown", "disputed"}
PARTICIPANT_ROLES = {
    "institutional_home",
    "governing_project",
    "governing_body",
    "repository_controller",
    "technical_maintainer",
    "originator_custodian",
    "project_custodian",
    "unknown",
}
TRANSITION_KINDS = {
    "stewardship_transfer",
    "governance_adoption",
    "protocol_merger",
    "regime_termination",
}
TRANSITION_MECHANISMS = {
    "donation",
    "contribution",
    "charter_adoption",
    "committee_formation",
    "merger",
    "archival",
    "other_declared",
}
ASSET_EFFECTS = {
    "transferred",
    "retained_by_originator",
    "unchanged",
    "unresolved",
}
CONFIDENCE_VALUES = {"high", "medium", "low"}
DEFAULT_GRAPH_RELATIONS = {
    "ORIGINATED",
    "CO_DEVELOPED",
    "STEWARDED_BY",
    "GOVERNED_BY",
    "HOLDS_VOTING_SEAT",
    "MAINTAINS",
    "REFERENCE_IMPLEMENTS",
    "INDEPENDENTLY_IMPLEMENTS",
    "INTEGRATES",
    "DEPLOYS_IN_PRODUCTION",
}
RELATION_LAYERS = {
    "ORIGINATED": "authorship",
    "CO_DEVELOPED": "authorship",
    "DONATED_TO": "governance",
    "STEWARDED_BY": "governance",
    "MEMBER_OF_STEWARD": "convening",
    "FUNDS": "funding",
    "GOVERNED_BY": "governance",
    "HOLDS_VOTING_SEAT": "governance",
    "CHAIRS": "governance",
    "MAINTAINS": "maintenance",
    "CONTRIBUTES_CODE": "implementation",
    "PUBLISHES_SDK": "implementation",
    "REFERENCE_IMPLEMENTS": "implementation",
    "INDEPENDENTLY_IMPLEMENTS": "implementation",
    "INTEGRATES": "adoption",
    "DEPLOYS_IN_PRODUCTION": "adoption",
    "EXTENDS": "implementation",
    "ENDORSES": "endorsement",
    "ANNOUNCES_SUPPORT_FOR": "endorsement",
}
TIMELINE_SHAPES = {
    "public_launch": "diamond",
    "governance_adoption": "hexagon",
    "stewardship_transfer": "triangle",
    "specification_release": "circle",
    "merger": "bowtie",
    "archival": "square",
    "production_deployment": "star",
}
TIMELINE_PROTOCOL_ORDER = (
    "protocol_mcp",
    "protocol_a2a",
    "protocol_acp",
    "protocol_ap2",
    "protocol_ucp",
    "protocol_x402",
)
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class StrictDuplicateKeyError(ValueError):
    """Raised before semantic validation when a YAML mapping repeats a key."""


class RegistryValidationError(ValueError):
    """Raised when the registry cannot satisfy the compiler contract."""

    def __init__(self, report: Mapping[str, Any]):
        self.report = dict(report)
        messages = "; ".join(item["message"] for item in report.get("errors", []))
        super().__init__(messages or "registry validation failed")


class StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader with duplicate-key rejection."""


def _construct_mapping(
    loader: StrictSafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise StrictDuplicateKeyError(
                f"unhashable YAML key at line {key_node.start_mark.line + 1}"
            ) from error
        if duplicate:
            raise StrictDuplicateKeyError(
                f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


@dataclass(frozen=True)
class RegistryCompilation:
    timeline: dict[str, Any]
    graph: dict[str, Any]
    transition_cards: dict[str, Any]
    validation: dict[str, Any]


def default_registry_path() -> Path:
    return Path(__file__).with_name("data") / "agentic_protocol_certification_registry.yaml"


def load_registry_strict(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = yaml.load(source.read_text(encoding="utf-8"), Loader=StrictSafeLoader)
    except yaml.YAMLError as error:
        raise RegistryValidationError(
            {
                "valid": False,
                "errors": [{"code": "invalid_yaml", "message": str(error)}],
                "warnings": [],
            }
        ) from error
    if not isinstance(raw, dict):
        raise RegistryValidationError(
            {
                "valid": False,
                "errors": [
                    {"code": "invalid_root", "message": "registry root must be a mapping"}
                ],
                "warnings": [],
            }
        )
    return raw


def _rows(raw: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    value = raw.get(name)
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _source_hash(source: Path) -> str:
    return sha256(source.read_bytes()).hexdigest()


def _issue(
    bucket: list[dict[str, str]], code: str, message: str, record_id: str = ""
) -> None:
    item = {"code": code, "message": message}
    if record_id:
        item["record_id"] = record_id
    bucket.append(item)


def _index(
    rows: Iterable[Mapping[str, Any]],
    collection: str,
    errors: list[dict[str, str]],
    global_ids: dict[str, str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        record_id = _text(row.get("id"))
        if not record_id:
            _issue(errors, "missing_id", f"{collection} contains a record without an id")
            continue
        if not ID_PATTERN.fullmatch(record_id):
            _issue(
                errors,
                "invalid_id",
                f"{collection} id {record_id!r} is not a canonical identifier",
                record_id,
            )
        if record_id in result:
            _issue(
                errors,
                "duplicate_id",
                f"{collection} repeats id {record_id}",
                record_id,
            )
        if record_id in global_ids:
            _issue(
                errors,
                "duplicate_global_id",
                f"{record_id} is used in both {global_ids[record_id]} and {collection}",
                record_id,
            )
        result[record_id] = dict(row)
        global_ids[record_id] = collection
    return result


def _date_precision(value: Any, declared: Any) -> tuple[str | None, str]:
    if value is None or value == "":
        return None, _text(declared) or "unknown"
    if isinstance(value, date):
        return value.isoformat(), _text(declared) or "day"
    if isinstance(value, int) and 1000 <= value <= 9999:
        return str(value), _text(declared) or "year"
    text = _text(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
        except ValueError:
            return text, "invalid"
        return text, _text(declared) or "day"
    if re.fullmatch(r"\d{4}-\d{2}", text):
        month = int(text[-2:])
        return text, (_text(declared) or "month") if 1 <= month <= 12 else "invalid"
    if re.fullmatch(r"\d{4}", text):
        return text, _text(declared) or "year"
    return text, "invalid"


def _normalise_date(
    value: Any,
    declared_precision: Any,
    *,
    record_id: str,
    field: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    authored, precision = _date_precision(value, declared_precision)
    if precision not in DATE_PRECISIONS:
        _issue(
            errors,
            "invalid_date",
            f"{record_id}.{field} is not a valid date or precision",
            record_id,
        )
        return {"value": authored, "precision": "unknown", "start": None, "end": None}
    if authored is not None and precision in {"month", "year"} and not declared_precision:
        _issue(
            errors,
            "undeclared_date_precision",
            f"{record_id}.{field} is partial but date_precision is not declared",
            record_id,
        )
    if authored is None:
        if precision != "unknown":
            _issue(
                errors,
                "null_date_precision",
                f"{record_id}.{field} is null and must use unknown precision",
                record_id,
            )
        return {"value": None, "precision": "unknown", "start": None, "end": None}
    if precision == "day":
        return {"value": authored, "precision": precision, "start": authored, "end": None}
    if precision == "month":
        year, month = (int(part) for part in authored.split("-"))
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        return {
            "value": authored,
            "precision": precision,
            "start": f"{year:04d}-{month:02d}-01",
            "end": f"{next_year:04d}-{next_month:02d}-01",
        }
    if precision == "year":
        year = int(authored)
        return {
            "value": authored,
            "precision": precision,
            "start": f"{year:04d}-01-01",
            "end": f"{year + 1:04d}-01-01",
        }
    return {"value": authored, "precision": precision, "start": None, "end": None}


def _evidence_cards(
    evidence_ids: Any,
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    claim: str,
    observed_at: str,
    evidence_state: str | None = None,
    confidence: str | None = None,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for evidence_id in evidence_ids if isinstance(evidence_ids, list) else []:
        source = evidence.get(_text(evidence_id), {})
        published, precision = _date_precision(source.get("published_at"), None)
        cards.append(
            {
                "id": _text(evidence_id),
                "claim": claim,
                "title": _text(source.get("title")),
                "publisher": _text(source.get("publisher")),
                "authority": _text(source.get("authority")),
                "published_at": published,
                "published_at_precision": precision,
                "observed_at": observed_at,
                "evidence_state": evidence_state,
                "confidence": confidence,
                "url": _text(source.get("url")),
            }
        )
    return cards


def _status_evidence(status: str) -> tuple[str, str]:
    """Map an authored regime status to graph evidence without upgrading it."""

    return {
        "verified": ("primary_verified", "high"),
        "announced": ("announced", "medium"),
        "disputed": ("inferred", "low"),
        "unknown": ("inferred", "low"),
    }.get(status, ("inferred", "low"))


def _compiled_regimes(
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Resolve institutional regimes into one renderer-neutral state contract."""

    observed_at, _ = _date_precision((raw.get("registry") or {}).get("observed_at"), None)
    records: list[dict[str, Any]] = []
    for regime in _rows(raw, "protocol_regimes"):
        record_id = _text(regime.get("id"))
        protocol = indexes["protocols"].get(_text(regime.get("protocol_id")), {})
        status = _text(regime.get("status"))
        evidence_state, confidence = _status_evidence(status)
        participants: list[dict[str, str]] = []
        for participant in regime.get("participants") or []:
            if not isinstance(participant, Mapping):
                continue
            actor = indexes["actors"].get(_text(participant.get("actor_id")), {})
            participants.append(
                {
                    "actor_id": _text(actor.get("id")),
                    "label": _text(actor.get("name")),
                    "role": _text(participant.get("role")),
                }
            )
        claim = _text(regime.get("claim")) or (
            f"{_text(protocol.get('acronym'))} {_text(regime.get('regime_type')).replace('_', ' ')} regime"
        )
        records.append(
            {
                "id": record_id,
                "protocol_id": _text(protocol.get("id")),
                "protocol_acronym": _text(protocol.get("acronym")),
                "regime_type": _text(regime.get("regime_type")),
                "status": status,
                "participants": participants,
                "valid_from": _normalise_date(
                    regime.get("valid_from"),
                    regime.get("date_precision"),
                    record_id=record_id,
                    field="valid_from",
                    errors=errors,
                ),
                "valid_to": _normalise_date(
                    regime.get("valid_to"),
                    "unknown"
                    if regime.get("valid_to") is None
                    else regime.get("valid_to_precision") or regime.get("date_precision"),
                    record_id=record_id,
                    field="valid_to",
                    errors=errors,
                ),
                "asset_scope": sorted({_text(value) for value in regime.get("asset_scope") or [] if _text(value)}),
                "governance_instrument": regime.get("governance_instrument"),
                "decision_rules": regime.get("decision_rules"),
                "participation_conditions": regime.get("participation_conditions"),
                "access_conditions": regime.get("access_conditions"),
                "claim": claim,
                "evidence_state": evidence_state,
                "confidence": confidence,
                "evidence": _evidence_cards(
                    regime.get("evidence_ids"),
                    indexes["evidence_sources"],
                    claim=claim,
                    observed_at=observed_at or "",
                    evidence_state=evidence_state,
                    confidence=confidence,
                ),
            }
        )
    records.sort(
        key=lambda row: (
            row["protocol_id"],
            row["regime_type"],
            row["valid_from"]["start"] or "9999",
            row["id"],
        )
    )
    return records


def _transition_window(
    transition: Mapping[str, Any],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    """Compile point-effective, interval-censored, or unresolved transitions."""

    record_id = _text(transition.get("id"))
    effective = transition.get("effective_date")
    interval = transition.get("effective_interval")
    if effective not in (None, ""):
        normalised = _normalise_date(
            effective,
            transition.get("date_precision") if transition.get("date_precision") != "interval" else "day",
            record_id=record_id,
            field="effective_date",
            errors=errors,
        )
        return {"mode": "point", **normalised}
    if isinstance(interval, Mapping):
        start = _normalise_date(
            interval.get("from"),
            interval.get("from_precision") or "day",
            record_id=record_id,
            field="effective_interval.from",
            errors=errors,
        )
        end = _normalise_date(
            interval.get("to"),
            interval.get("to_precision") or "day",
            record_id=record_id,
            field="effective_interval.to",
            errors=errors,
        )
        return {
            "mode": "interval",
            "value": None,
            "precision": "interval",
            "start": start.get("start"),
            "end": end.get("start"),
        }
    return {"mode": "unknown", "value": None, "precision": "unknown", "start": None, "end": None}


def _compiled_transitions(
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    regimes: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Resolve state-change records without asking a renderer to join identities."""

    observed_at, _ = _date_precision((raw.get("registry") or {}).get("observed_at"), None)
    compiled_regimes = {row["id"]: row for row in regimes}
    records: list[dict[str, Any]] = []
    for transition in _rows(raw, "protocol_transitions"):
        record_id = _text(transition.get("id"))
        event = indexes["protocol_events"].get(_text(transition.get("event_id")), {})
        before = [
            compiled_regimes[regime_id]
            for regime_id in (_text(value) for value in transition.get("from_regime_ids") or [])
            if regime_id in compiled_regimes
        ]
        after = [
            compiled_regimes[regime_id]
            for regime_id in (_text(value) for value in transition.get("to_regime_ids") or [])
            if regime_id in compiled_regimes
        ]
        source_protocols = [
            indexes["protocols"].get(_text(value), {})
            for value in transition.get("source_protocol_ids") or []
        ]
        target_protocol = indexes["protocols"].get(
            _text(transition.get("target_protocol_id")), {}
        )
        affected_protocol_ids = {
            row["protocol_id"] for row in (*before, *after) if row.get("protocol_id")
        }
        affected_protocol_ids.update(
            _text(row.get("id")) for row in source_protocols if row.get("id")
        )
        if target_protocol.get("id"):
            affected_protocol_ids.add(_text(target_protocol.get("id")))
        if event.get("protocol_id"):
            affected_protocol_ids.add(_text(event.get("protocol_id")))
        claim = _text(event.get("summary")) or _text(transition.get("summary"))
        transfer_effect = [
            {"asset": _text(item.get("asset")), "effect": _text(item.get("effect"))}
            for item in transition.get("transfer_effect") or []
            if isinstance(item, Mapping)
        ]
        fields_for_gaps = (
            "governance_instrument",
            "decision_rules",
            "participation_conditions",
            "access_conditions",
            "continuities",
            "discontinuities",
        )
        missing_fields = [
            field
            for field in fields_for_gaps
            if transition.get(field) is None or transition.get(field) == []
        ]
        records.append(
            {
                "id": record_id,
                "event_id": _text(event.get("id")),
                "kind": _text(transition.get("kind")),
                "summary": claim,
                "affected_protocol_ids": sorted(affected_protocol_ids),
                "before": before,
                "after": after,
                "announced_at": _normalise_date(
                    transition.get("announced_at"),
                    "unknown" if transition.get("announced_at") is None else "day",
                    record_id=record_id,
                    field="announced_at",
                    errors=errors,
                ),
                "effective": _transition_window(transition, errors),
                "completion_confirmed_at": _normalise_date(
                    transition.get("completion_confirmed_at"),
                    "unknown" if transition.get("completion_confirmed_at") is None else "day",
                    record_id=record_id,
                    field="completion_confirmed_at",
                    errors=errors,
                ),
                "mechanism": _text(transition.get("mechanism")),
                "transfer_effect": transfer_effect,
                "governance_instrument": transition.get("governance_instrument"),
                "decision_rules": transition.get("decision_rules"),
                "participation_conditions": transition.get("participation_conditions"),
                "access_conditions": transition.get("access_conditions"),
                "continuities": transition.get("continuities") or [],
                "discontinuities": transition.get("discontinuities") or [],
                "missing_fields": missing_fields,
                "source_protocols": [
                    {
                        "id": _text(row.get("id")),
                        "acronym": _text(row.get("acronym")),
                        "name": _text(row.get("name")),
                    }
                    for row in source_protocols
                ],
                "target_protocol": None
                if not target_protocol
                else {
                    "id": _text(target_protocol.get("id")),
                    "acronym": _text(target_protocol.get("acronym")),
                    "name": _text(target_protocol.get("name")),
                },
                "genealogy_relation_id": _text(transition.get("genealogy_relation_id")) or None,
                "migration_path": transition.get("migration_path"),
                "source_status_after": transition.get("source_status_after"),
                "compatibility_effect": transition.get("compatibility_effect"),
                "evidence": _evidence_cards(
                    transition.get("evidence_ids"),
                    indexes["evidence_sources"],
                    claim=claim,
                    observed_at=observed_at or "",
                ),
            }
        )
    records.sort(
        key=lambda row: (
            row["effective"]["start"] or row["announced_at"]["start"] or "9999",
            row["id"],
        )
    )
    return records


def _protocol_governance_surface(
    protocol: Mapping[str, Any],
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
    regimes: Iterable[Mapping[str, Any]] = (),
    transitions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Expose only governance assertions explicitly encoded in typed records.

    Empty arrays and null values are deliberate data gaps.  In particular, a
    governance source URL is not interpreted as a named committee, person,
    appointment, maintainer interval, or decision procedure.
    """

    protocol_id = _text(protocol.get("id"))
    evidence = indexes["evidence_sources"]
    observed_at, _ = _date_precision((raw.get("registry") or {}).get("observed_at"), None)
    relevant = [
        row
        for row in _rows(raw, "actor_protocol_relations")
        if row.get("protocol_id") == protocol_id
    ]

    def actor_relation(row: Mapping[str, Any]) -> dict[str, Any]:
        actor = indexes["actors"].get(_text(row.get("actor_id")), {})
        record_id = _text(row.get("id"))
        relation_type = _text(row.get("relation_type"))
        claim = f"{_text(actor.get('name'))} — {relation_type} — {_text(protocol.get('name'))}"
        return {
            "relation_id": record_id,
            "actor": {"id": _text(actor.get("id")), "label": _text(actor.get("name"))},
            "valid_from": _normalise_date(
                row.get("valid_from"),
                row.get("date_precision"),
                record_id=record_id,
                field="valid_from",
                errors=errors,
            ),
            "valid_to": _normalise_date(
                row.get("valid_to"),
                "unknown"
                if row.get("valid_to") is None
                else row.get("valid_to_precision") or row.get("date_precision"),
                record_id=record_id,
                field="valid_to",
                errors=errors,
            ),
            "evidence": _evidence_cards(
                row.get("evidence_ids"),
                evidence,
                claim=claim,
                observed_at=observed_at or "",
                evidence_state=_text(row.get("evidence_state")) or None,
                confidence=_text(row.get("confidence")) or None,
            ),
        }

    protocol_regimes = [
        row for row in regimes if row.get("protocol_id") == protocol_id
    ]

    def regime_participant(
        regime: Mapping[str, Any], participant: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {
            "regime_id": _text(regime.get("id")),
            "actor": {
                "id": _text(participant.get("actor_id")),
                "label": _text(participant.get("label")),
            },
            "role": _text(participant.get("role")),
            "valid_from": regime.get("valid_from"),
            "valid_to": regime.get("valid_to"),
            "asset_scope": list(regime.get("asset_scope") or []),
            "evidence": list(regime.get("evidence") or []),
        }

    governing_body = [
        regime_participant(regime, participant)
        for regime in protocol_regimes
        if regime.get("regime_type") == "governance"
        for participant in regime.get("participants") or []
    ]
    voting_organisations = [
        actor_relation(row)
        for row in relevant
        if row.get("relation_type") == "HOLDS_VOTING_SEAT"
    ]
    maintainer_intervals = [
        actor_relation(row) for row in relevant if row.get("relation_type") == "MAINTAINS"
    ]
    transfer_events: list[dict[str, Any]] = []
    for transition in transitions:
        if (
            transition.get("kind") != "stewardship_transfer"
            or protocol_id not in (transition.get("affected_protocol_ids") or [])
        ):
            continue
        transfer_events.append(
            {
                "transition_id": _text(transition.get("id")),
                "event_id": _text(transition.get("event_id")),
                "date": transition.get("effective"),
                "summary": _text(transition.get("summary")),
                "before": list(transition.get("before") or []),
                "after": list(transition.get("after") or []),
                "transfer_effect": list(transition.get("transfer_effect") or []),
                "evidence": list(transition.get("evidence") or []),
            }
        )

    decision_procedures = [
        regime.get("decision_rules")
        for regime in protocol_regimes
        if regime.get("regime_type") == "governance"
        and regime.get("decision_rules") not in (None, "", [])
    ]

    governance_gate = (protocol.get("certification") or {}).get("governance_surface") or {}
    governance_evidence = _evidence_cards(
        governance_gate.get("evidence_ids"),
        evidence,
        claim=f"{_text(protocol.get('name'))} has a published governance surface",
        observed_at=observed_at or "",
    )
    result: dict[str, Any] = {
        "governing_body": governing_body,
        "technical_steering_committee": [],
        "voting_organisations": voting_organisations,
        "named_representatives": [],
        "appointment_intervals": [],
        "maintainer_intervals": maintainer_intervals,
        "decision_procedure": decision_procedures[0] if decision_procedures else None,
        "transfer_of_stewardship": transfer_events,
        "governance_evidence": governance_evidence,
        "gaps": [],
    }
    gap_fields = (
        "governing_body",
        "technical_steering_committee",
        "voting_organisations",
        "named_representatives",
        "appointment_intervals",
        "maintainer_intervals",
        "decision_procedure",
        "transfer_of_stewardship",
    )
    result["gaps"] = [
        field for field in gap_fields if result[field] is None or result[field] == []
    ]
    return result


def _protocol_lifeline(
    protocol: Mapping[str, Any],
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
    observed_at: str,
) -> dict[str, Any]:
    """Compile the visible lifetime without asking a renderer to infer it."""

    protocol_id = _text(protocol.get("id"))
    start = _normalise_date(
        protocol.get("first_public_date"),
        protocol.get("date_precision"),
        record_id=protocol_id,
        field="first_public_date",
        errors=errors,
    )
    end = _normalise_date(
        observed_at,
        "day",
        record_id=protocol_id,
        field="observation_end",
        errors=errors,
    )
    end_reason = "observation_date"
    target_protocol: dict[str, str] | None = None

    closing_relations = sorted(
        (
            row
            for row in _rows(raw, "protocol_protocol_relations")
            if row.get("source_protocol_id") == protocol_id
            and row.get("relation_type") in {"MERGED_INTO", "SUPERSEDES"}
        ),
        key=lambda row: _text(row.get("valid_from")),
    )
    if protocol.get("status") == "superseded" and closing_relations:
        closing = closing_relations[0]
        end = _normalise_date(
            closing.get("valid_from"),
            closing.get("date_precision"),
            record_id=_text(closing.get("id")),
            field="valid_from",
            errors=errors,
        )
        end_reason = _text(closing.get("relation_type")).lower()
        target = indexes["protocols"].get(
            _text(closing.get("target_protocol_id")), {}
        )
        target_protocol = {
            "id": _text(target.get("id")),
            "acronym": _text(target.get("acronym")),
            "name": _text(target.get("name")),
        }

    return {
        "start": start,
        "end": end,
        "end_reason": end_reason,
        "target_protocol": target_protocol,
    }


def _validate_references(
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
) -> None:
    actors = indexes["actors"]
    protocols = indexes["protocols"]
    versions = indexes["protocol_versions"]
    events = indexes["protocol_events"]
    regimes = indexes["protocol_regimes"]
    genealogy = indexes["protocol_protocol_relations"]
    evidence = indexes["evidence_sources"]

    def refs(
        rows: Iterable[Mapping[str, Any]],
        field: str,
        targets: Mapping[str, Any],
        target_label: str,
    ) -> None:
        for row in rows:
            record_id = _text(row.get("id"))
            values = row.get(field)
            values = values if isinstance(values, list) else [values]
            for value in values:
                ref = _text(value)
                if ref and ref not in targets:
                    _issue(
                        errors,
                        "unresolved_reference",
                        f"{record_id}.{field} references missing {target_label} {ref}",
                        record_id,
                    )

    protocol_rows = _rows(raw, "protocols")
    refs(protocol_rows, "originator_ids", actors, "actor")
    refs(protocol_rows, "current_steward_ids", actors, "actor")
    refs(protocol_rows, "version_ids", versions, "version")
    refs(protocol_rows, "event_ids", events, "event")
    refs(protocol_rows, "superseded_by", protocols, "protocol")
    for row in protocol_rows:
        for gate in (row.get("certification") or {}).values():
            if isinstance(gate, dict):
                refs([{"id": row.get("id"), "evidence_ids": gate.get("evidence_ids")}], "evidence_ids", evidence, "evidence")

    version_rows = _rows(raw, "protocol_versions")
    refs(version_rows, "protocol_id", protocols, "protocol")
    refs(version_rows, "evidence_ids", evidence, "evidence")
    event_rows = _rows(raw, "protocol_events")
    refs(event_rows, "protocol_id", protocols, "protocol")
    refs(event_rows, "version_id", versions, "version")
    refs(event_rows, "actor_ids", actors, "actor")
    refs(event_rows, "evidence_ids", evidence, "evidence")
    relation_rows = _rows(raw, "actor_protocol_relations")
    refs(relation_rows, "actor_id", actors, "actor")
    refs(relation_rows, "protocol_id", protocols, "protocol")
    refs(relation_rows, "evidence_ids", evidence, "evidence")
    genealogy_rows = _rows(raw, "protocol_protocol_relations")
    refs(genealogy_rows, "source_protocol_id", protocols, "protocol")
    refs(genealogy_rows, "target_protocol_id", protocols, "protocol")
    refs(genealogy_rows, "evidence_ids", evidence, "evidence")
    regime_rows = _rows(raw, "protocol_regimes")
    refs(regime_rows, "protocol_id", protocols, "protocol")
    refs(regime_rows, "evidence_ids", evidence, "evidence")
    for regime in regime_rows:
        participant_rows = [
            {"id": regime.get("id"), "actor_id": item.get("actor_id")}
            for item in regime.get("participants") or []
            if isinstance(item, Mapping)
        ]
        refs(participant_rows, "actor_id", actors, "actor")
    transition_rows = _rows(raw, "protocol_transitions")
    refs(transition_rows, "event_id", events, "event")
    refs(transition_rows, "from_regime_ids", regimes, "regime")
    refs(transition_rows, "to_regime_ids", regimes, "regime")
    refs(transition_rows, "source_protocol_ids", protocols, "protocol")
    refs(transition_rows, "target_protocol_id", protocols, "protocol")
    refs(transition_rows, "genealogy_relation_id", genealogy, "genealogy relation")
    refs(transition_rows, "evidence_ids", evidence, "evidence")
    refs(_rows(raw, "frontier_candidates"), "evidence_ids", evidence, "evidence")

    for protocol in protocol_rows:
        protocol_id = _text(protocol.get("id"))
        for version_id in protocol.get("version_ids") or []:
            version = versions.get(_text(version_id))
            if version and version.get("protocol_id") != protocol_id:
                _issue(errors, "wrong_protocol_owner", f"{version_id} does not belong to {protocol_id}", protocol_id)
        # Events can be cross-listed by another affected protocol (for example,
        # a merger).  Their canonical protocol_id still has to resolve, but a
        # protocol's event_ids list is not an ownership assertion.


def _build_indexes(
    raw: Mapping[str, Any], errors: list[dict[str, str]]
) -> dict[str, dict[str, dict[str, Any]]]:
    global_ids: dict[str, str] = {}
    registry_meta = raw.get("registry") if isinstance(raw.get("registry"), dict) else {}
    registry_id = _text(registry_meta.get("id"))
    if not registry_id:
        _issue(errors, "missing_id", "registry metadata must declare an id")
    elif not ID_PATTERN.fullmatch(registry_id):
        _issue(
            errors,
            "invalid_id",
            f"registry id {registry_id!r} is not a canonical identifier",
            registry_id,
        )
    else:
        global_ids[registry_id] = "registry"
    return {
        collection: _index(_rows(raw, collection), collection, errors, global_ids)
        for collection in COLLECTIONS_WITH_IDS
    }


def _validate_structure(
    raw: Mapping[str, Any], errors: list[dict[str, str]]
) -> None:
    for name in (
        "registry",
        "certification_policy",
        "date_semantics",
        "controlled_vocabularies",
        "artifact_generation",
    ):
        if not isinstance(raw.get(name), dict):
            _issue(errors, "invalid_collection", f"{name} must be a mapping")
    for name in COLLECTIONS_WITH_IDS:
        value = raw.get(name)
        if not isinstance(value, list):
            _issue(errors, "invalid_collection", f"{name} must be a list")
            continue
        for index, row in enumerate(value):
            if not isinstance(row, dict):
                _issue(
                    errors,
                    "invalid_record",
                    f"{name}[{index}] must be a mapping",
                )


def _vocabulary_values(controlled: Mapping[str, Any], name: str) -> set[str]:
    value = controlled.get(name)
    if isinstance(value, Mapping):
        return {_text(item) for item in value.keys() if _text(item)}
    if isinstance(value, list):
        return {_text(item) for item in value if _text(item)}
    return set()


def _validate_regime_intervals(
    raw: Mapping[str, Any],
    errors: list[dict[str, str]],
) -> None:
    """Reject scope collisions and unrepresented gaps in institutional state."""

    observed_at, _ = _date_precision((raw.get("registry") or {}).get("observed_at"), None)
    closing_dates = {
        _text(row.get("source_protocol_id")): _date_precision(
            row.get("valid_from"), row.get("date_precision")
        )[0]
        for row in _rows(raw, "protocol_protocol_relations")
        if row.get("relation_type") in {"MERGED_INTO", "SUPERSEDES"}
    }
    grouped: dict[tuple[str, str, str], list[tuple[str, str, str | None]]] = {}
    for regime in _rows(raw, "protocol_regimes"):
        record_id = _text(regime.get("id"))
        start, _ = _date_precision(regime.get("valid_from"), regime.get("date_precision"))
        end, _ = _date_precision(
            regime.get("valid_to"),
            "unknown"
            if regime.get("valid_to") is None
            else regime.get("valid_to_precision") or regime.get("date_precision"),
        )
        if start and end and end <= start:
            _issue(errors, "invalid_regime_interval", f"{record_id} must satisfy valid_from < valid_to", record_id)
        for asset in {_text(value) for value in regime.get("asset_scope") or [] if _text(value)}:
            key = (_text(regime.get("protocol_id")), _text(regime.get("regime_type")), asset)
            grouped.setdefault(key, []).append((record_id, start or "", end))

    for key, intervals in grouped.items():
        ordered = sorted(intervals, key=lambda item: (item[1], item[0]))
        protocol_id, regime_type, asset = key
        for previous, current in zip(ordered, ordered[1:]):
            previous_id, _previous_start, previous_end = previous
            current_id, current_start, _current_end = current
            if previous_end is None:
                _issue(
                    errors,
                    "overlapping_regime_scope",
                    f"{previous_id} is open while {current_id} also covers {protocol_id}/{regime_type}/{asset}",
                    current_id,
                )
            elif current_start < previous_end:
                _issue(
                    errors,
                    "overlapping_regime_scope",
                    f"{previous_id} and {current_id} overlap for {protocol_id}/{regime_type}/{asset}",
                    current_id,
                )
            elif current_start > previous_end:
                _issue(
                    errors,
                    "unrepresented_regime_gap",
                    f"{protocol_id}/{regime_type}/{asset} has an unrepresented gap between {previous_end} and {current_start}",
                    current_id,
                )
        final_end = ordered[-1][2] if ordered else None
        closes_with_protocol = (
            final_end is not None
            and closing_dates.get(protocol_id) == final_end
        )
        if ordered and final_end is not None and final_end < (observed_at or "") and not closes_with_protocol:
            _issue(
                errors,
                "unrepresented_regime_gap",
                f"{protocol_id}/{regime_type}/{asset} has no regime from {ordered[-1][2]} to the observation date",
                ordered[-1][0],
            )


def _validate_semantics(
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> None:
    controlled = raw.get("controlled_vocabularies") or {}
    relation_types = set((controlled.get("relation_types") or {}).keys())
    event_types = set(controlled.get("event_types") or [])
    actor_types = set(controlled.get("actor_types") or [])
    protocol_layers = set((controlled.get("protocol_layers") or {}).keys())
    evidence_states = set(((raw.get("certification_policy") or {}).get("evidence_states") or {}).keys())
    regime_types = _vocabulary_values(controlled, "regime_types")
    regime_statuses = _vocabulary_values(controlled, "regime_statuses")
    participant_roles = _vocabulary_values(controlled, "participant_roles")
    transition_kinds = _vocabulary_values(controlled, "transition_kinds")
    transition_mechanisms = _vocabulary_values(controlled, "transition_mechanisms")
    asset_effects = _vocabulary_values(controlled, "asset_effects")

    required_vocabularies = {
        "regime_types": REGIME_TYPES,
        "regime_statuses": REGIME_STATUSES,
        "participant_roles": PARTICIPANT_ROLES,
        "transition_kinds": TRANSITION_KINDS,
        "transition_mechanisms": TRANSITION_MECHANISMS,
        "asset_effects": ASSET_EFFECTS,
    }
    authored_vocabularies = {
        "regime_types": regime_types,
        "regime_statuses": regime_statuses,
        "participant_roles": participant_roles,
        "transition_kinds": transition_kinds,
        "transition_mechanisms": transition_mechanisms,
        "asset_effects": asset_effects,
    }
    for name, required in required_vocabularies.items():
        missing = required - authored_vocabularies[name]
        if missing:
            _issue(
                errors,
                "incomplete_controlled_vocabulary",
                f"controlled_vocabularies.{name} is missing {', '.join(sorted(missing))}",
            )

    for actor in _rows(raw, "actors"):
        record_id = _text(actor.get("id"))
        if actor.get("type") not in actor_types:
            _issue(errors, "invalid_actor_type", f"{record_id} has unknown actor type {actor.get('type')}", record_id)
        parent_id = _text(actor.get("parent_id"))
        if parent_id and parent_id not in indexes["actors"]:
            _issue(errors, "unresolved_reference", f"{record_id}.parent_id references missing actor {parent_id}", record_id)

    for protocol in _rows(raw, "protocols"):
        record_id = _text(protocol.get("id"))
        if protocol.get("layer") not in protocol_layers:
            _issue(errors, "invalid_protocol_layer", f"{record_id} has unknown layer {protocol.get('layer')}", record_id)
        certification = protocol.get("certification")
        expected_gates = set(((raw.get("certification_policy") or {}).get("gates") or {}).keys())
        actual_gates = set(certification.keys()) if isinstance(certification, dict) else set()
        if actual_gates != expected_gates:
            _issue(errors, "invalid_certification_gates", f"{record_id} must have exactly the four declared certification gates", record_id)
        for gate_name, gate in (certification or {}).items():
            if not isinstance(gate, dict) or gate.get("result") != "pass":
                _issue(errors, "failed_certification_gate", f"{record_id}.{gate_name} is not passed", record_id)
        _normalise_date(protocol.get("first_public_date"), protocol.get("date_precision"), record_id=record_id, field="first_public_date", errors=errors)

    for version in _rows(raw, "protocol_versions"):
        record_id = _text(version.get("id"))
        _normalise_date(version.get("released_at"), version.get("date_precision"), record_id=record_id, field="released_at", errors=errors)
        if not version.get("evidence_ids"):
            _issue(errors, "missing_evidence", f"{record_id} has no evidence source", record_id)

    for event in _rows(raw, "protocol_events"):
        record_id = _text(event.get("id"))
        if event.get("event_type") not in event_types:
            _issue(errors, "invalid_event_type", f"{record_id} has unknown event type {event.get('event_type')}", record_id)
        _normalise_date(event.get("event_date"), event.get("date_precision"), record_id=record_id, field="event_date", errors=errors)
        if not event.get("evidence_ids"):
            _issue(errors, "missing_evidence", f"{record_id} has no evidence source", record_id)

    for relation in _rows(raw, "actor_protocol_relations"):
        record_id = _text(relation.get("id"))
        relation_type = _text(relation.get("relation_type"))
        if relation_type not in relation_types or relation_type not in RELATION_LAYERS:
            _issue(errors, "invalid_relation_type", f"{record_id} has unmapped relation type {relation_type}", record_id)
        if "valid_to" not in relation:
            _issue(errors, "missing_valid_to", f"{record_id} must declare valid_to: null when open", record_id)
        _normalise_date(relation.get("valid_from"), relation.get("date_precision"), record_id=record_id, field="valid_from", errors=errors)
        valid_to_precision = relation.get("valid_to_precision") or relation.get("date_precision")
        _normalise_date(relation.get("valid_to"), "unknown" if relation.get("valid_to") is None else valid_to_precision, record_id=record_id, field="valid_to", errors=errors)
        if relation.get("evidence_state") not in evidence_states:
            _issue(errors, "invalid_evidence_state", f"{record_id} has unknown evidence state", record_id)
        if relation.get("confidence") not in CONFIDENCE_VALUES:
            _issue(errors, "invalid_confidence", f"{record_id} has unknown confidence", record_id)
        if not relation.get("evidence_ids"):
            _issue(errors, "missing_evidence", f"{record_id} has no evidence source", record_id)

    for relation in _rows(raw, "protocol_protocol_relations"):
        record_id = _text(relation.get("id"))
        if relation.get("relation_type") not in relation_types:
            _issue(errors, "invalid_relation_type", f"{record_id} has unknown relation type", record_id)
        _normalise_date(relation.get("valid_from"), relation.get("date_precision"), record_id=record_id, field="valid_from", errors=errors)
        if not relation.get("evidence_ids"):
            _issue(errors, "missing_evidence", f"{record_id} has no evidence source", record_id)

    registry_version = _text((raw.get("registry") or {}).get("version"))
    compatibility_projection = bool(
        ((raw.get("registry") or {}).get("institutional_state_contract") or {}).get(
            "compatibility_note"
        )
    )
    if registry_version == "0.2.0":
        for protocol in _rows(raw, "protocols"):
            if "current_steward_ids" in protocol:
                _issue(
                    warnings if compatibility_projection else errors,
                    "duplicated_derived_stewardship",
                    f"{protocol.get('id')}.current_steward_ids must be compiler-derived in schema 0.2.0",
                    _text(protocol.get("id")),
                )
        for relation in _rows(raw, "actor_protocol_relations"):
            if relation.get("relation_type") in {"STEWARDED_BY", "GOVERNED_BY"}:
                _issue(
                    warnings if compatibility_projection else errors,
                    "duplicated_derived_institutional_edge",
                    f"{relation.get('id')} must be derived from protocol_regimes in schema 0.2.0",
                    _text(relation.get("id")),
                )

    for regime in _rows(raw, "protocol_regimes"):
        record_id = _text(regime.get("id"))
        regime_type = _text(regime.get("regime_type"))
        status = _text(regime.get("status"))
        if regime_type not in regime_types:
            _issue(errors, "invalid_regime_type", f"{record_id} has unknown regime type {regime_type}", record_id)
        if status not in regime_statuses:
            _issue(errors, "invalid_regime_status", f"{record_id} has unknown regime status {status}", record_id)
        if "valid_to" not in regime:
            _issue(errors, "missing_valid_to", f"{record_id} must declare valid_to: null when open", record_id)
        _normalise_date(
            regime.get("valid_from"),
            regime.get("date_precision"),
            record_id=record_id,
            field="valid_from",
            errors=errors,
        )
        _normalise_date(
            regime.get("valid_to"),
            "unknown" if regime.get("valid_to") is None else regime.get("valid_to_precision") or regime.get("date_precision"),
            record_id=record_id,
            field="valid_to",
            errors=errors,
        )
        participants = regime.get("participants")
        if not isinstance(participants, list):
            _issue(errors, "invalid_regime_participants", f"{record_id}.participants must be a list", record_id)
            participants = []
        if status not in {"unknown", "disputed"} and not participants:
            _issue(errors, "missing_regime_participants", f"{record_id} must name at least one participant", record_id)
        for participant in participants:
            role = _text(participant.get("role")) if isinstance(participant, Mapping) else ""
            if role not in participant_roles:
                _issue(errors, "invalid_participant_role", f"{record_id} has unknown participant role {role}", record_id)
        if not regime.get("asset_scope"):
            _issue(errors, "missing_asset_scope", f"{record_id} has no asset scope", record_id)
        if regime_type == "governance" and "governance_instrument" not in regime:
            _issue(errors, "missing_governance_instrument", f"{record_id} must name a governance instrument or explicitly use null", record_id)
        if not regime.get("evidence_ids"):
            _issue(errors, "missing_evidence", f"{record_id} has no evidence source", record_id)

    _validate_regime_intervals(raw, errors)

    for transition in _rows(raw, "protocol_transitions"):
        record_id = _text(transition.get("id"))
        kind = _text(transition.get("kind"))
        mechanism = _text(transition.get("mechanism"))
        if kind not in transition_kinds:
            _issue(errors, "invalid_transition_kind", f"{record_id} has unknown transition kind {kind}", record_id)
        if mechanism not in transition_mechanisms:
            _issue(errors, "invalid_transition_mechanism", f"{record_id} has unknown mechanism {mechanism}", record_id)
        if not transition.get("evidence_ids"):
            _issue(errors, "missing_evidence", f"{record_id} has no evidence source", record_id)
        effective = transition.get("effective_date")
        interval = transition.get("effective_interval")
        if effective not in (None, "") and interval not in (None, {}):
            _issue(errors, "ambiguous_transition_date", f"{record_id} cannot declare both effective_date and effective_interval", record_id)
        if effective in (None, "") and isinstance(interval, Mapping):
            if transition.get("date_precision") != "interval":
                _issue(errors, "invalid_transition_precision", f"{record_id} interval transition must declare date_precision: interval", record_id)
            interval_from, _ = _date_precision(interval.get("from"), interval.get("from_precision") or "day")
            interval_to, _ = _date_precision(interval.get("to"), interval.get("to_precision") or "day")
            if not interval_from or not interval_to or interval_to <= interval_from:
                _issue(errors, "invalid_transition_interval", f"{record_id} must satisfy effective_interval.from < effective_interval.to", record_id)
        elif effective not in (None, ""):
            _normalise_date(effective, transition.get("date_precision"), record_id=record_id, field="effective_date", errors=errors)
        else:
            _issue(errors, "missing_transition_date", f"{record_id} must declare an effective date or interval", record_id)
        effects = transition.get("transfer_effect") or []
        seen_assets: set[str] = set()
        for effect in effects:
            asset = _text(effect.get("asset")) if isinstance(effect, Mapping) else ""
            value = _text(effect.get("effect")) if isinstance(effect, Mapping) else ""
            if not asset:
                _issue(errors, "missing_transfer_asset", f"{record_id} has a transfer effect without an asset", record_id)
            elif asset in seen_assets:
                _issue(errors, "duplicate_transfer_asset", f"{record_id} repeats transfer asset {asset}", record_id)
            seen_assets.add(asset)
            if value not in asset_effects:
                _issue(errors, "invalid_asset_effect", f"{record_id} has unknown asset effect {value}", record_id)
        if kind == "stewardship_transfer" and not effects:
            _issue(errors, "missing_transfer_effect", f"{record_id} must state asset-level transfer effects", record_id)
        if kind == "stewardship_transfer" and effects:
            from_regimes = [
                indexes["protocol_regimes"].get(_text(value), {})
                for value in transition.get("from_regime_ids") or []
            ]
            to_regimes = [
                indexes["protocol_regimes"].get(_text(value), {})
                for value in transition.get("to_regime_ids") or []
            ]
            before_scope = {
                _text(asset)
                for regime in from_regimes
                if regime.get("regime_type") == "stewardship"
                for asset in regime.get("asset_scope") or []
            }
            after_scope = {
                _text(asset)
                for regime in to_regimes
                if regime.get("regime_type") == "stewardship"
                for asset in regime.get("asset_scope") or []
            }
            transferred_scope = {
                _text(effect.get("asset"))
                for effect in effects
                if isinstance(effect, Mapping)
                and effect.get("effect") == "transferred"
            }
            if before_scope != after_scope or transferred_scope != after_scope:
                _issue(
                    errors,
                    "incomplete_transfer_scope",
                    f"{record_id} transferred assets must match the closed and opened stewardship scopes",
                    record_id,
                )

        if kind == "protocol_merger":
            event = indexes["protocol_events"].get(_text(transition.get("event_id")), {})
            genealogy = indexes["protocol_protocol_relations"].get(_text(transition.get("genealogy_relation_id")), {})
            event_date, _ = _date_precision(event.get("event_date"), event.get("date_precision"))
            genealogy_date, _ = _date_precision(genealogy.get("valid_from"), genealogy.get("date_precision"))
            effective_date, _ = _date_precision(transition.get("effective_date"), transition.get("date_precision"))
            source_ids = {_text(value) for value in transition.get("source_protocol_ids") or []}
            target_id = _text(transition.get("target_protocol_id"))
            if not source_ids or not target_id or target_id in source_ids:
                _issue(errors, "invalid_merger_direction", f"{record_id} must identify distinct source and target protocols", record_id)
            if len({value for value in (event_date, genealogy_date, effective_date) if value}) > 1:
                _issue(errors, "merger_date_mismatch", f"{record_id} event, genealogy, and effective dates disagree", record_id)
            archive_dates = {
                _date_precision(row.get("event_date"), row.get("date_precision"))[0]
                for row in _rows(raw, "protocol_events")
                if row.get("event_type") == "archival" and row.get("protocol_id") in source_ids
            }
            if archive_dates and effective_date not in archive_dates:
                _issue(errors, "merger_archive_mismatch", f"{record_id} does not agree with source archival date", record_id)

    if RELATION_LAYERS["ANNOUNCES_SUPPORT_FOR"] != "endorsement":
        _issue(errors, "taxonomy_collapse", "announced support must remain in endorsement")
    if RELATION_LAYERS["MEMBER_OF_STEWARD"] != "convening":
        _issue(errors, "taxonomy_collapse", "foundation membership must remain convening, not governance")
    for source in _rows(raw, "evidence_sources"):
        record_id = _text(source.get("id"))
        if not source.get("url"):
            _issue(errors, "unresolvable_evidence", f"{record_id} has no direct URL", record_id)
    for candidate in _rows(raw, "frontier_candidates"):
        if not candidate.get("evidence_ids"):
            _issue(warnings, "frontier_without_evidence", f"{candidate.get('id')} is held outside displayed certified views", _text(candidate.get("id")))


def _timeline_artifact(
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
    metadata: Mapping[str, Any],
    regimes: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
) -> dict[str, Any]:
    protocols = indexes["protocols"]
    actors = indexes["actors"]
    versions = indexes["protocol_versions"]
    evidence = indexes["evidence_sources"]
    observed_at, _ = _date_precision((raw.get("registry") or {}).get("observed_at"), None)
    lane_ids = list((((raw.get("artifact_generation") or {}).get("timeline") or {}).get("lanes") or []))
    layer_labels = ((raw.get("controlled_vocabularies") or {}).get("protocol_layers") or {})
    show_events = set((((raw.get("artifact_generation") or {}).get("timeline") or {}).get("show_events") or TIMELINE_SHAPES))
    lanes = [
        {"id": lane, "label": _text(layer_labels.get(lane)), "order": order}
        for order, lane in enumerate(lane_ids)
    ]
    items: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    represented_versions: set[str] = set()
    transition_event_ids = {
        _text(item.get("event_id")) for item in transitions if item.get("event_id")
    }
    for event in _rows(raw, "protocol_events"):
        if event.get("event_type") not in show_events:
            continue
        if (
            _text(event.get("id")) in transition_event_ids
            and event.get("event_type")
            in {"governance_adoption", "stewardship_transfer", "merger"}
        ):
            continue
        protocol = protocols.get(_text(event.get("protocol_id")), {})
        event_date = _normalise_date(event.get("event_date"), event.get("date_precision"), record_id=_text(event.get("id")), field="event_date", errors=errors)
        actor_rows = [actors.get(_text(actor_id), {}) for actor_id in event.get("actor_ids") or []]
        version = versions.get(_text(event.get("version_id")))
        if version:
            represented_versions.add(_text(version.get("id")))
        item = {
            "id": _text(event.get("id")),
            "lane_id": _text(protocol.get("layer")),
            "protocol": {
                "id": _text(protocol.get("id")),
                "name": _text(protocol.get("name")),
                "acronym": _text(protocol.get("acronym")),
                "status": _text(protocol.get("status")),
            },
            "event_type": _text(event.get("event_type")),
            "mark_shape": TIMELINE_SHAPES.get(_text(event.get("event_type")), "circle"),
            "summary": _text(event.get("summary")),
            "date": event_date,
            "actors": [
                {"id": _text(actor.get("id")), "label": _text(actor.get("name"))}
                for actor in actor_rows
            ],
            "version": None
            if not version
            else {"id": _text(version.get("id")), "label": _text(version.get("version"))},
            "evidence_resolution": "resolvable"
            if all(card_id in evidence for card_id in (event.get("evidence_ids") or []))
            else "unresolved",
            "evidence_state": None,
            "confidence": None,
            "evidence": _evidence_cards(event.get("evidence_ids"), evidence, claim=_text(event.get("summary")), observed_at=observed_at or ""),
        }
        (unresolved if event_date["precision"] == "unknown" else items).append(item)
    items.sort(key=lambda item: (item["date"]["start"] or "9999", item["protocol"]["id"], item["event_type"], item["id"]))
    unresolved.sort(key=lambda item: item["id"])
    supplemental_versions: list[dict[str, Any]] = []
    for version in _rows(raw, "protocol_versions"):
        version_id = _text(version.get("id"))
        if version_id in represented_versions:
            continue
        protocol = protocols.get(_text(version.get("protocol_id")), {})
        released = _normalise_date(version.get("released_at"), version.get("date_precision"), record_id=version_id, field="released_at", errors=errors)
        supplemental_versions.append(
            {
                "id": version_id,
                "protocol_id": _text(protocol.get("id")),
                "protocol_acronym": _text(protocol.get("acronym")),
                "version": _text(version.get("version")),
                "stability": _text(version.get("stability")),
                "date": released,
                "evidence": _evidence_cards(version.get("evidence_ids"), evidence, claim=f"{_text(protocol.get('acronym'))} {_text(version.get('version'))} release", observed_at=observed_at or ""),
            }
        )
    supplemental_versions.sort(key=lambda item: (item["date"]["start"] or "9999", item["protocol_id"], item["id"]))
    protocol_order = {
        protocol_id: order
        for order, protocol_id in enumerate(TIMELINE_PROTOCOL_ORDER)
    }
    protocol_records = []
    for item in sorted(
        protocols.values(),
        key=lambda row: (
            protocol_order.get(_text(row.get("id")), len(protocol_order)),
            _text(row.get("id")),
        ),
    ):
        protocol_id = _text(item.get("id"))
        current_steward_regimes = [
            regime
            for regime in regimes
            if regime.get("protocol_id") == protocol_id
            and regime.get("regime_type") == "stewardship"
            and (regime.get("valid_from") or {}).get("start")
            and (regime.get("valid_from") or {}).get("start") <= (observed_at or "")
            and (
                not (regime.get("valid_to") or {}).get("start")
                or (observed_at or "") < (regime.get("valid_to") or {}).get("start")
            )
        ]
        current_stewards = [
            participant
            for regime in current_steward_regimes
            for participant in regime.get("participants") or []
        ]
        protocol_records.append(
            {
                "id": protocol_id,
                "name": _text(item.get("name")),
                "acronym": _text(item.get("acronym")),
                "layer": _text(item.get("layer")),
                "status": _text(item.get("status")),
                "display_order": protocol_order.get(
                    protocol_id, len(protocol_order)
                ),
                "current_steward_ids": sorted(
                    {_text(participant.get("actor_id")) for participant in current_stewards}
                ),
                "current_stewards": sorted(
                    (
                        {
                            "actor_id": _text(participant.get("actor_id")),
                            "label": _text(participant.get("label")),
                            "role": _text(participant.get("role")),
                        }
                        for participant in current_stewards
                    ),
                    key=lambda participant: (participant["label"], participant["actor_id"]),
                ),
                "lifeline": _protocol_lifeline(
                    item,
                    raw,
                    indexes,
                    errors,
                    observed_at or "",
                ),
                "governance_surface": _protocol_governance_surface(
                    item, raw, indexes, errors, regimes, transitions
                ),
            }
        )
    return {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "metadata": dict(metadata),
        "lanes": lanes,
        "protocol_order": list(TIMELINE_PROTOCOL_ORDER),
        "protocols": protocol_records,
        "items": items,
        "regimes": regimes,
        "transitions": transitions,
        "unresolved_items": unresolved,
        "supplemental_versions": supplemental_versions,
    }


def _node_positions(
    actors: list[dict[str, Any]], protocols: list[dict[str, Any]], lane_order: Mapping[str, int]
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    companies = sorted((item for item in actors if item.get("type") == "company"), key=lambda item: (_text(item.get("name")).lower(), _text(item.get("id"))))
    institutions = sorted((item for item in actors if item.get("type") != "company"), key=lambda item: (_text(item.get("parent_id")), _text(item.get("name")).lower(), _text(item.get("id"))))
    actor_positions: dict[str, dict[str, int]] = {}
    for side, rows in ((-1, companies), (1, institutions)):
        offset = (len(rows) - 1) * 45
        for index, row in enumerate(rows):
            actor_positions[_text(row.get("id"))] = {"x": side * 520, "y": index * 90 - offset}
    protocol_positions: dict[str, dict[str, int]] = {}
    for index, row in enumerate(sorted(protocols, key=lambda item: (lane_order.get(_text(item.get("layer")), 99), _text(item.get("id"))))):
        protocol_positions[_text(row.get("id"))] = {"x": 0, "y": index * 180 - (len(protocols) - 1) * 90}
    return actor_positions, protocol_positions


def _graph_artifact(
    raw: Mapping[str, Any],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    errors: list[dict[str, str]],
    metadata: Mapping[str, Any],
    regimes: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
) -> dict[str, Any]:
    actor_rows = list(indexes["actors"].values())
    protocol_rows = list(indexes["protocols"].values())
    evidence = indexes["evidence_sources"]
    relation_descriptions = ((raw.get("controlled_vocabularies") or {}).get("relation_types") or {})
    observed_at, _ = _date_precision((raw.get("registry") or {}).get("observed_at"), None)
    lane_ids = list((((raw.get("artifact_generation") or {}).get("timeline") or {}).get("lanes") or []))
    lane_order = {lane: index for index, lane in enumerate(lane_ids)}
    actor_positions, protocol_positions = _node_positions(actor_rows, protocol_rows, lane_order)
    nodes: list[dict[str, Any]] = []
    for actor in sorted(actor_rows, key=lambda row: _text(row.get("id"))):
        nodes.append(
            {
                "id": _text(actor.get("id")),
                "kind": "actor",
                "label": _text(actor.get("name")),
                "actor_type": _text(actor.get("type")),
                "parent_id": _text(actor.get("parent_id")) or None,
                "column": "company" if actor.get("type") == "company" else "institution",
                "position": actor_positions[_text(actor.get("id"))],
            }
        )
    for protocol in sorted(protocol_rows, key=lambda row: _text(row.get("id"))):
        nodes.append(
            {
                "id": _text(protocol.get("id")),
                "kind": "protocol",
                "label": _text(protocol.get("acronym")),
                "name": _text(protocol.get("name")),
                "layer": _text(protocol.get("layer")),
                "status": _text(protocol.get("status")),
                "certification_verdict": _text(protocol.get("certification_verdict")),
                "governance_surface": _protocol_governance_surface(
                    protocol, raw, indexes, errors, regimes, transitions
                ),
                "column": "protocol",
                "position": protocol_positions[_text(protocol.get("id"))],
            }
        )
    edges: list[dict[str, Any]] = []
    for relation in _rows(raw, "actor_protocol_relations"):
        record_id = _text(relation.get("id"))
        actor = indexes["actors"].get(_text(relation.get("actor_id")), {})
        protocol = indexes["protocols"].get(_text(relation.get("protocol_id")), {})
        relation_type = _text(relation.get("relation_type"))
        valid_from = _normalise_date(relation.get("valid_from"), relation.get("date_precision"), record_id=record_id, field="valid_from", errors=errors)
        valid_to = _normalise_date(relation.get("valid_to"), "unknown" if relation.get("valid_to") is None else relation.get("valid_to_precision") or relation.get("date_precision"), record_id=record_id, field="valid_to", errors=errors)
        claim = f"{_text(actor.get('name'))} — {relation_type} — {_text(protocol.get('name'))}"
        edges.append(
            {
                "id": record_id,
                "source": _text(actor.get("id")),
                "target": _text(protocol.get("id")),
                "relation_type": relation_type,
                "relation_label": _text(relation_descriptions.get(relation_type)),
                "layer": RELATION_LAYERS.get(relation_type),
                "default_visible": relation_type in DEFAULT_GRAPH_RELATIONS,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "evidence_state": _text(relation.get("evidence_state")),
                "confidence": _text(relation.get("confidence")),
                "claim": claim,
                "evidence": _evidence_cards(
                    relation.get("evidence_ids"),
                    evidence,
                    claim=claim,
                    observed_at=observed_at or "",
                    evidence_state=_text(relation.get("evidence_state")) or None,
                    confidence=_text(relation.get("confidence")) or None,
                ),
            }
        )
    for regime in regimes:
        regime_type = _text(regime.get("regime_type"))
        relation_type = {
            "stewardship": "STEWARDED_BY",
            "governance": "GOVERNED_BY",
        }.get(regime_type)
        if relation_type is None:
            continue
        for participant in regime.get("participants") or []:
            actor_id = _text(participant.get("actor_id"))
            if not actor_id:
                continue
            protocol = indexes["protocols"].get(_text(regime.get("protocol_id")), {})
            claim = (
                f"{_text(participant.get('label'))} — {relation_type} — "
                f"{_text(protocol.get('name'))} ({_text(participant.get('role')).replace('_', ' ')})"
            )
            edges.append(
                {
                    "id": f"derived_{_text(regime.get('id'))}_{actor_id}",
                    "source": actor_id,
                    "target": _text(regime.get("protocol_id")),
                    "relation_type": relation_type,
                    "relation_label": _text(relation_descriptions.get(relation_type)),
                    "layer": "governance",
                    "default_visible": True,
                    "valid_from": regime.get("valid_from"),
                    "valid_to": regime.get("valid_to"),
                    "evidence_state": _text(regime.get("evidence_state")),
                    "confidence": _text(regime.get("confidence")),
                    "claim": claim,
                    "derived_from_regime_id": _text(regime.get("id")),
                    "participant_role": _text(participant.get("role")),
                    "asset_scope": list(regime.get("asset_scope") or []),
                    "evidence": [
                        {**card, "claim": claim}
                        for card in regime.get("evidence") or []
                    ],
                }
            )
    edges.sort(key=lambda item: (item["layer"] or "", item["source"], item["target"], item["relation_type"], item["id"]))
    genealogy: list[dict[str, Any]] = []
    for relation in _rows(raw, "protocol_protocol_relations"):
        record_id = _text(relation.get("id"))
        relation_type = _text(relation.get("relation_type"))
        valid_from = _normalise_date(relation.get("valid_from"), relation.get("date_precision"), record_id=record_id, field="valid_from", errors=errors)
        source = indexes["protocols"].get(_text(relation.get("source_protocol_id")), {})
        target = indexes["protocols"].get(_text(relation.get("target_protocol_id")), {})
        claim = f"{_text(source.get('name'))} — {relation_type} — {_text(target.get('name'))}"
        genealogy.append(
            {
                "id": record_id,
                "source": _text(source.get("id")),
                "target": _text(target.get("id")),
                "relation_type": relation_type,
                "valid_from": valid_from,
                "valid_to": None,
                "claim": claim,
                "evidence": _evidence_cards(relation.get("evidence_ids"), evidence, claim=claim, observed_at=observed_at or ""),
            }
        )
    genealogy.sort(key=lambda item: (item["valid_from"]["start"] or "9999", item["source"], item["target"], item["id"]))
    return {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "metadata": {
            **dict(metadata),
            "relation_layer_map": dict(sorted(RELATION_LAYERS.items())),
            "institutional_state_source": "protocol_regimes",
        },
        "layers": [
            {"id": layer, "label": layer.replace("_", " ").title()}
            for layer in (
                "authorship",
                "governance",
                "maintenance",
                "implementation",
                "adoption",
                "funding",
                "endorsement",
                "convening",
            )
        ],
        "nodes": nodes,
        "edges": edges,
        "genealogy_edges": genealogy,
        "time_semantics": "active when valid_from <= t < valid_to; null valid_to is open-ended",
    }


def _transition_card_artifact(
    metadata: Mapping[str, Any], transitions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Emit complete before/operation/after records for institutional selection."""

    return {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "metadata": dict(metadata),
        "cards": transitions,
    }


def compile_registry(path: str | Path | None = None) -> RegistryCompilation:
    source = Path(path) if path is not None else default_registry_path()
    raw = load_registry_strict(source)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    _validate_structure(raw, errors)
    indexes = _build_indexes(raw, errors)
    if errors:
        errors.sort(
            key=lambda item: (
                item.get("record_id", ""),
                item["code"],
                item["message"],
            )
        )
        raise RegistryValidationError(
            {
                "contract_version": ARTIFACT_CONTRACT_VERSION,
                "valid": False,
                "metadata": {},
                "counts": {
                    collection: len(indexes[collection])
                    for collection in COLLECTIONS_WITH_IDS
                },
                "errors": errors,
                "warnings": warnings,
            }
        )
    _validate_references(raw, indexes, errors)
    _validate_semantics(raw, indexes, errors, warnings)
    registry_meta = raw.get("registry") if isinstance(raw.get("registry"), dict) else {}
    source_hash = _source_hash(source)
    metadata = {
        "registry_id": _text(registry_meta.get("id")),
        "registry_version": _text(registry_meta.get("version")),
        "observed_at": _date_precision(registry_meta.get("observed_at"), None)[0],
        "source_sha256": source_hash,
    }
    regimes = _compiled_regimes(raw, indexes, errors)
    transitions = _compiled_transitions(raw, indexes, regimes, errors)
    timeline = _timeline_artifact(
        raw, indexes, errors, metadata, regimes, transitions
    )
    graph = _graph_artifact(raw, indexes, errors, metadata, regimes, transitions)
    transition_cards = _transition_card_artifact(metadata, transitions)
    errors.sort(key=lambda item: (item.get("record_id", ""), item["code"], item["message"]))
    warnings.sort(key=lambda item: (item.get("record_id", ""), item["code"], item["message"]))
    report = {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "valid": not errors,
        "metadata": metadata,
        "counts": {collection: len(indexes[collection]) for collection in COLLECTIONS_WITH_IDS},
        "derived_counts": {
            "timeline_items": len(timeline["items"]),
            "unresolved_timeline_items": len(timeline["unresolved_items"]),
            "supplemental_versions": len(timeline["supplemental_versions"]),
            "protocol_regimes": len(regimes),
            "protocol_transitions": len(transitions),
            "transition_cards": len(transition_cards["cards"]),
            "graph_nodes": len(graph["nodes"]),
            "graph_edges": len(graph["edges"]),
            "genealogy_edges": len(graph["genealogy_edges"]),
        },
        "errors": errors,
        "warnings": warnings,
        "safeguards": {
            "announced_support_layer": RELATION_LAYERS["ANNOUNCES_SUPPORT_FOR"],
            "foundation_membership_layer": RELATION_LAYERS["MEMBER_OF_STEWARD"],
            "superseded_protocols_retained": all(
                any(node["id"] == protocol["id"] for node in graph["nodes"])
                for protocol in indexes["protocols"].values()
                if protocol.get("status") == "superseded"
            ),
        },
    }
    if errors:
        raise RegistryValidationError(report)
    return RegistryCompilation(
        timeline=timeline,
        graph=graph,
        transition_cards=transition_cards,
        validation=report,
    )


def _compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def write_compiled_artifacts(
    compilation: RegistryCompilation, output_directory: str | Path
) -> dict[str, Path]:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "timeline": directory / "timeline.json",
        "graph": directory / "graph.json",
        "transition_cards": directory / "transition_cards.json",
        "validation": directory / "validation_report.json",
    }
    paths["timeline"].write_text(_compact_json(compilation.timeline), encoding="utf-8")
    paths["graph"].write_text(_compact_json(compilation.graph), encoding="utf-8")
    paths["transition_cards"].write_text(
        _compact_json(compilation.transition_cards), encoding="utf-8"
    )
    paths["validation"].write_text(_compact_json(compilation.validation), encoding="utf-8")
    return paths


def load_compiled_artifacts(
    directory: str | Path | None = None,
) -> RegistryCompilation:
    source = Path(directory) if directory is not None else Path(__file__).with_name("generated")
    timeline = json.loads((source / "timeline.json").read_text(encoding="utf-8"))
    graph = json.loads((source / "graph.json").read_text(encoding="utf-8"))
    transition_cards = json.loads(
        (source / "transition_cards.json").read_text(encoding="utf-8")
    )
    validation = json.loads((source / "validation_report.json").read_text(encoding="utf-8"))
    if not validation.get("valid"):
        raise RegistryValidationError(validation)
    for artifact in (timeline, graph, transition_cards, validation):
        if artifact.get("contract_version") != ARTIFACT_CONTRACT_VERSION:
            raise RegistryValidationError(
                {
                    "valid": False,
                    "errors": [{"code": "contract_mismatch", "message": "compiled artifact contract version does not match compiler"}],
                    "warnings": [],
                }
            )
    artifact_hashes = {
        timeline.get("metadata", {}).get("source_sha256"),
        graph.get("metadata", {}).get("source_sha256"),
        transition_cards.get("metadata", {}).get("source_sha256"),
        validation.get("metadata", {}).get("source_sha256"),
    }
    if len(artifact_hashes) != 1 or None in artifact_hashes:
        raise RegistryValidationError(
            {
                "valid": False,
                "errors": [{"code": "artifact_source_mismatch", "message": "timeline, graph, transition cards, and validation report were not compiled from the same YAML snapshot"}],
                "warnings": [],
            }
        )
    if directory is None and next(iter(artifact_hashes)) != _source_hash(
        default_registry_path()
    ):
        raise RegistryValidationError(
            {
                "valid": False,
                "errors": [{"code": "stale_artifacts", "message": "compiled artifacts do not match the checked-in YAML snapshot"}],
                "warnings": [],
            }
        )
    return RegistryCompilation(
        timeline=timeline,
        graph=graph,
        transition_cards=transition_cards,
        validation=validation,
    )
