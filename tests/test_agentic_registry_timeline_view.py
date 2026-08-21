from __future__ import annotations

from copy import deepcopy

import agentic_registry.timeline_view as timeline_view


def _evidence(source_id: str = "src_launch") -> list[dict[str, str]]:
    return [
        {
            "id": source_id,
            "claim": "Originator announced the protocol.",
            "authority": "originator_primary",
            "publisher": "Example Foundation",
            "title": "Launch announcement",
            "published_at": "2025-05",
            "published_at_precision": "month",
            "observed_at": "2026-08-07",
            "url": "https://example.test/launch",
        }
    ]


def _artifact() -> dict:
    return {
        "metadata": {"observed_at": "2027-08-07"},
        "lanes": [
            {
                "id": "tool_context",
                "label": "Agent-to-tool interaction.",
                "order": 0,
            },
            {
                "id": "agent_communication",
                "label": "Agent messaging.",
                "order": 1,
            },
        ],
        "protocols": [
            {
                "id": "protocol_live",
                "acronym": "LIVE",
                "name": "Live Protocol",
                "layer": "tool_context",
                "status": "active",
                "display_order": 0,
                "lifeline": {
                    "start": {"value": "2025-04-09", "precision": "day", "start": "2025-04-09", "end": None},
                    "end": {"value": "2027-08-07", "precision": "day", "start": "2027-08-07", "end": None},
                    "end_reason": "observation_date",
                    "target_protocol": None,
                },
            },
            {
                "id": "protocol_old",
                "acronym": "OLD",
                "name": "Old Protocol",
                "layer": "agent_communication",
                "status": "superseded",
                "display_order": 1,
                "lifeline": {
                    "start": {"value": "2025", "precision": "year", "start": "2025-01-01", "end": "2026-01-01"},
                    "end": {"value": "2026-06-01", "precision": "day", "start": "2026-06-01", "end": None},
                    "end_reason": "merged_into",
                    "target_protocol": {"id": "protocol_live", "acronym": "LIVE", "name": "Live Protocol"},
                },
            },
        ],
        "regimes": [
            {
                "id": "regime_live_unknown_stewardship",
                "protocol_id": "protocol_live",
                "protocol_acronym": "LIVE",
                "regime_type": "stewardship",
                "status": "unknown",
                "confidence": "low",
                "valid_from": {"value": "2025-04-09", "precision": "day", "start": "2025-04-09", "end": None},
                "valid_to": {"value": "2025-05-01", "precision": "day", "start": "2025-05-01", "end": None},
                "participants": [],
                "asset_scope": ["protocol_family"],
                "governance_instrument": None,
                "evidence": _evidence("src_unknown_steward"),
            },
            {
                "id": "regime_live_foundation_stewardship",
                "protocol_id": "protocol_live",
                "protocol_acronym": "LIVE",
                "regime_type": "stewardship",
                "status": "verified",
                "confidence": "high",
                "valid_from": {"value": "2025-05-01", "precision": "day", "start": "2025-05-01", "end": None},
                "valid_to": {"value": None, "precision": "unknown", "start": None, "end": None},
                "participants": [{"actor_id": "actor_foundation", "label": "Example Foundation", "role": "institutional_home"}],
                "asset_scope": ["protocol_family"],
                "governance_instrument": None,
                "evidence": _evidence("src_foundation_steward"),
            },
            {
                "id": "regime_live_governance",
                "protocol_id": "protocol_live",
                "protocol_acronym": "LIVE",
                "regime_type": "governance",
                "status": "verified",
                "confidence": "high",
                "valid_from": {"value": "2025-05-01", "precision": "day", "start": "2025-05-01", "end": None},
                "valid_to": {"value": None, "precision": "unknown", "start": None, "end": None},
                "participants": [{"actor_id": "body_steering", "label": "Technical Steering Committee", "role": "governing_body"}],
                "asset_scope": ["protocol_change_process"],
                "governance_instrument": "LIVE governance charter",
                "evidence": _evidence("src_governance"),
            },
            {
                "id": "regime_old_unknown_stewardship",
                "protocol_id": "protocol_old",
                "protocol_acronym": "OLD",
                "regime_type": "stewardship",
                "status": "disputed",
                "confidence": "low",
                "valid_from": {"value": "2025", "precision": "year", "start": "2025-01-01", "end": "2026-01-01"},
                "valid_to": {"value": "2026-06-01", "precision": "day", "start": "2026-06-01", "end": None},
                "participants": [],
                "asset_scope": ["protocol_family"],
                "governance_instrument": None,
                "evidence": _evidence("src_old_steward"),
            },
        ],
        "transitions": [
            {
                "id": "transition_live_foundation",
                "kind": "stewardship_transfer",
                "mechanism": "donation",
                "affected_protocol_ids": ["protocol_live"],
                "source_protocols": [],
                "target_protocol": None,
                "effective": {"value": "2025-05-01", "precision": "day", "mode": "point", "start": "2025-05-01", "end": None},
                "summary": "LIVE moved to Example Foundation.",
                "before": [{
                    "id": "regime_live_unknown_stewardship",
                    "protocol_acronym": "LIVE",
                    "regime_type": "stewardship",
                    "status": "unknown",
                    "confidence": "low",
                    "valid_from": {"value": "2025-04-09", "precision": "day", "start": "2025-04-09", "end": None},
                    "valid_to": {"value": "2025-05-01", "precision": "day", "start": "2025-05-01", "end": None},
                    "participants": [],
                    "asset_scope": ["protocol_family"],
                }],
                "after": [{
                    "id": "regime_live_foundation_stewardship",
                    "protocol_acronym": "LIVE",
                    "protocol_id": "protocol_live",
                    "regime_type": "stewardship",
                    "status": "verified",
                    "confidence": "high",
                    "valid_from": {"value": "2025-05-01", "precision": "day", "start": "2025-05-01", "end": None},
                    "valid_to": {"value": None, "precision": "unknown", "start": None, "end": None},
                    "participants": [{"actor_id": "actor_foundation", "label": "Example Foundation", "role": "institutional_home"}],
                    "asset_scope": ["protocol_family"],
                }],
                "transfer_effect": [{"asset": "protocol_family", "effect": "transferred"}],
                "continuities": ["LIVE remained the same protocol family."],
                "discontinuities": ["Example Foundation became the institutional home."],
                "missing_fields": ["access_conditions"],
                "evidence": _evidence("src_live_transition"),
            },
            {
                "id": "transition_live_governance",
                "kind": "governance_adoption",
                "mechanism": "charter_adoption",
                "affected_protocol_ids": ["protocol_live"],
                "source_protocols": [],
                "target_protocol": None,
                "effective": {"value": "2025-05-01", "precision": "day", "mode": "point", "start": "2025-05-01", "end": None},
                "summary": "LIVE adopted formal governance.",
                "before": [],
                "after": [{
                    "id": "regime_live_governance",
                    "protocol_acronym": "LIVE",
                    "protocol_id": "protocol_live",
                    "regime_type": "governance",
                    "status": "verified",
                    "confidence": "high",
                    "valid_from": {"value": "2025-05-01", "precision": "day", "start": "2025-05-01", "end": None},
                    "valid_to": {"value": None, "precision": "unknown", "start": None, "end": None},
                    "participants": [{"actor_id": "body_steering", "label": "Technical Steering Committee", "role": "governing_body"}],
                    "asset_scope": ["protocol_change_process"],
                    "governance_instrument": "LIVE governance charter",
                }],
                "transfer_effect": [],
                "continuities": [],
                "discontinuities": ["A formal charter took effect."],
                "missing_fields": [],
                "evidence": _evidence("src_governance_transition"),
            },
            {
                "id": "transition_live_window",
                "kind": "stewardship_transfer",
                "mechanism": "contribution",
                "affected_protocol_ids": ["protocol_live"],
                "source_protocols": [],
                "target_protocol": None,
                "effective": {"value": None, "precision": "interval", "mode": "interval", "start": "2026-04-01", "end": "2026-07-01"},
                "summary": "The completion date is interval-censored.",
                "before": [],
                "after": [],
                "transfer_effect": [{"asset": "standards_process", "effect": "transferred"}],
                "continuities": [],
                "discontinuities": [],
                "missing_fields": [],
                "evidence": _evidence("src_interval"),
            },
            {
                "id": "transition_old_live_merger",
                "kind": "protocol_merger",
                "mechanism": "merger",
                "affected_protocol_ids": ["protocol_old", "protocol_live"],
                "source_protocols": [{"id": "protocol_old", "acronym": "OLD", "name": "Old Protocol"}],
                "target_protocol": {"id": "protocol_live", "acronym": "LIVE", "name": "Live Protocol"},
                "effective": {"value": "2026-06-01", "precision": "day", "mode": "point", "start": "2026-06-01", "end": None},
                "summary": "OLD development merged into LIVE.",
                "before": [],
                "after": [],
                "transfer_effect": [{"asset": "protocol_development", "effect": "transferred"}],
                "continuities": ["A migration path was published."],
                "discontinuities": ["OLD was archived."],
                "missing_fields": ["decision_rules"],
                "evidence": _evidence("src_merger"),
            },
        ],
        "items": [
            {
                "id": "evt_day",
                "protocol": {
                    "id": "protocol_live",
                    "acronym": "LIVE",
                    "name": "Live Protocol",
                    "status": "active",
                },
                "lane_id": "tool_context",
                "event_type": "public_launch",
                "summary": "Live Protocol launched.",
                "actors": [{"id": "actor_foundation", "label": "Example Foundation"}],
                "version": None,
                "evidence_state": "verified",
                "evidence": _evidence(),
                "date": {
                    "value": "2025-04-09",
                    "precision": "day",
                    "start": "2025-04-09",
                    "end": None,
                },
                "mark_shape": "diamond",
            },
            {
                "id": "evt_month",
                "protocol": {
                    "id": "protocol_live",
                    "acronym": "LIVE",
                    "name": "Live Protocol",
                    "status": "active",
                },
                "lane_id": "tool_context",
                "event_type": "specification_release",
                "summary": "Version 2.0 was released.",
                "actors": [{"id": "actor_foundation", "label": "Example Foundation"}],
                "version": {"id": "live_2_0", "label": "2.0"},
                "evidence_state": "verified",
                "evidence_resolution": "resolvable",
                "evidence": _evidence("src_transfer"),
                "date": {
                    "value": "2025-05",
                    "precision": "month",
                    "start": "2025-05-01",
                    "end": "2025-06-01",
                },
                "mark_shape": "circle",
            },
            {
                "id": "evt_year",
                "protocol": {
                    "id": "protocol_old",
                    "acronym": "OLD",
                    "name": "Old Protocol",
                    "status": "superseded",
                },
                "lane_id": "agent_communication",
                "event_type": "archival",
                "summary": "Old Protocol archived.",
                "actors": [],
                "version": None,
                "evidence_state": "verified",
                "evidence": _evidence("src_archive"),
                "date": {
                    "value": "2026",
                    "precision": "year",
                    "start": "2026-01-01",
                    "end": "2027-01-01",
                },
                "mark_shape": "square",
            },
        ],
        "supplemental_versions": [
            {
                "id": "live_patch",
                "protocol_id": "protocol_live",
                "protocol_acronym": "LIVE",
                "version": "2.0.1",
                "stability": "released",
                "date": {
                    "value": "2025-05-12",
                    "precision": "day",
                    "start": "2025-05-12",
                    "end": None,
                },
                "evidence": _evidence("src_patch"),
            },
            {
                "id": "live_unknown",
                "protocol_id": "protocol_live",
                "protocol_acronym": "LIVE",
                "version": "0.1",
                "stability": "historical",
                "date": {
                    "value": None,
                    "precision": "unknown",
                    "start": None,
                    "end": None,
                },
                "evidence": _evidence("src_unknown"),
            },
        ],
        "unresolved_items": [
            {
                "id": "evt_unresolved_old",
                "protocol": {"id": "protocol_old", "acronym": "OLD"},
                "event_type": "public_launch",
                "summary": "Launch date unresolved.",
                "date": {
                    "value": None,
                    "precision": "unknown",
                    "start": None,
                    "end": None,
                },
                "evidence": _evidence("src_unresolved"),
            }
        ],
    }


def test_loader_reads_only_the_timeline_compiler_artifact(monkeypatch) -> None:
    sentinel = _artifact()

    class CompilationBoundary:
        timeline = sentinel

        @property
        def graph(self):
            raise AssertionError("timeline renderer must not access graph")

        @property
        def validation(self):
            raise AssertionError("timeline renderer must not access validation")

    monkeypatch.setattr(
        timeline_view, "load_compiled_artifacts", lambda: CompilationBoundary()
    )

    assert timeline_view.load_timeline_artifact() is sentinel


def test_payload_preserves_partial_dates_as_ranges_and_mark_shapes() -> None:
    payload = timeline_view.build_timeline_payload(_artifact())
    items = {item["event_id"]: item for item in payload.items if "event_id" in item}

    assert items["evt_day"]["type"] == "point"
    assert "end" not in items["evt_day"]
    assert items["evt_month"] == {
        **items["evt_month"],
        "start": "2025-05-01",
        "end": "2025-06-01",
        "type": "range",
    }
    assert items["evt_year"]["start"] == "2026-01-01"
    assert items["evt_year"]["end"] == "2027-01-01"
    assert "protocol-date-precision-month" in items["evt_month"]["className"]
    assert "opacity:0.74" in items["evt_month"]["style"]
    assert "protocol-date-precision-year" in items["evt_year"]["className"]
    assert "border-style:dashed" in items["evt_year"]["style"]
    assert "◆" in items["evt_day"]["content"]
    assert "●" in items["evt_month"]["content"]
    assert items["evt_day"]["style"] != items["evt_month"]["style"]


def test_filter_keeps_superseded_history_and_separates_supplemental_versions() -> None:
    timeline = _artifact()
    options = dict(timeline_view.protocol_options(timeline))
    payload = timeline_view.build_timeline_payload(timeline, ["protocol_old"])

    assert options["protocol_old"].endswith("(superseded)")
    assert [item["event_id"] for item in payload.items if "event_id" in item] == [
        "evt_year"
    ]
    assert payload.item_index["1"]["protocol"]["status"] == "superseded"
    assert payload.supplemental_versions == ()
    assert [item["id"] for item in payload.unresolved_items] == [
        "evt_unresolved_old"
    ]


def test_unknown_supplemental_date_is_kept_off_axis() -> None:
    payload = timeline_view.build_timeline_payload(_artifact(), ["protocol_live"])

    assert "live_unknown" not in {
        item["event_id"] for item in payload.items if "event_id" in item
    }
    assert [item["id"] for item in payload.supplemental_versions] == [
        "live_patch",
        "live_unknown",
    ]
    assert [item["id"] for item in payload.unresolved_items] == ["live_unknown"]


def test_evidence_card_contains_complete_source_provenance() -> None:
    item = _artifact()["items"][1]

    card = timeline_view.evidence_card(item)

    assert card["date"] == "May 2025"
    assert card["date_precision"] == "month"
    assert card["actors"] == ("Example Foundation",)
    assert card["version"] == "2.0"
    assert card["evidence_state"] == "verified"
    assert card["evidence_resolution"] == "resolvable"
    assert card["evidence"] == (
        {
            "id": "src_transfer",
            "claim": "Originator announced the protocol.",
            "authority": "originator_primary",
            "publisher": "Example Foundation",
            "title": "Launch announcement",
            "published_at": "May 2025",
            "observed_at": "2026-08-07",
            "url": "https://example.test/launch",
        },
    )


def test_selection_id_accepts_component_return_variants() -> None:
    assert timeline_view.selected_item_id({"id": "evt_day"}) == "evt_day"
    assert timeline_view.selected_item_id({"item": {"id": "evt_month"}}) == (
        "evt_month"
    )
    assert timeline_view.selected_item_id({"item": "evt_year"}) == "evt_year"
    assert timeline_view.selected_item_id(None) is None


def test_plot_selection_resolves_compiler_event_id() -> None:
    assert timeline_view.selected_plot_event_id(
        {"selection": {"points": [{"customdata": ["evt_month"]}]}}
    ) == "evt_month"
    assert timeline_view.selected_plot_event_id({"selection": {"points": []}}) is None


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.links = []
        self.tables = []
        self.writes = []
        self.session_state = {}

    def multiselect(self, *_args, **_kwargs):
        raise AssertionError("shared protocol selection should bypass a local widget")

    def caption(self, *_args, **_kwargs):
        pass

    def container(self, *_args, **_kwargs):
        return _Context()

    def expander(self, *_args, **_kwargs):
        return _Context()

    def subheader(self, *_args, **_kwargs):
        pass

    def markdown(self, *_args, **_kwargs):
        pass

    def link_button(self, label, url, **kwargs):
        self.links.append((label, url, kwargs))

    def dataframe(self, rows, **_kwargs):
        self.tables.append(rows)

    def write(self, value):
        self.writes.append(value)


def test_renderer_accepts_shared_protocol_filter_and_returns_selected_evidence() -> None:
    st_api = _FakeStreamlit()
    component_calls = []

    def component(figure, **kwargs):
        component_calls.append((figure, kwargs))
        return {"selection": {"points": [{"customdata": ["evt_month"]}]}}

    payload = timeline_view.render_protocol_timeline(
        timeline=_artifact(),
        protocol_ids=["protocol_live"],
        st_api=st_api,
        timeline_component=component,
    )

    assert payload.included_protocol_ids == ("protocol_live",)
    assert len(component_calls) == 1
    figure, call_options = component_calls[0]
    assert figure.layout.xaxis.range[1] == "2027-08-07"
    assert figure.layout.xaxis.fixedrange is True
    assert list(figure.layout.yaxis.ticktext) == ["<b>LIVE</b><br>Tool context"]
    assert call_options["on_select"] == "rerun"
    assert call_options["selection_mode"] == "points"
    assert st_api.links[0][1] == "https://example.test/launch"
    assert st_api.tables[0][0]["Version"] == "2.0.1"
    assert "LIVE · 0.1" in st_api.writes


def test_protocol_lanes_ticks_and_lifelines_share_one_ordered_field() -> None:
    payload = timeline_view.build_timeline_payload(_artifact())

    assert ["LIVE" in group["content"] for group in payload.groups] == [True, False]
    assert [group["order"] for group in payload.groups] == [0, 1]
    assert payload.observation_date == "2027-08-07"
    ticks = [item for item in payload.items if item.get("release_id")]
    assert [(item["release_id"], item["content"], item["selectable"]) for item in ticks] == [
        ("live_patch", "", False)
    ]
    old_lifeline = next(
        item
        for item in payload.items
        if item.get("className") == "protocol-lifeline protocol-lifeline-closed"
    )
    assert old_lifeline["end"] == "2026-06-01"
    assert "merged into LIVE" in old_lifeline["title"]


def test_single_figure_encodes_event_shapes_minor_ticks_and_observation_end() -> None:
    payload = timeline_view.build_timeline_payload(_artifact())
    figure = timeline_view.build_timeline_figure(payload)

    event_traces = {trace.name: trace for trace in figure.data if trace.name}
    assert event_traces["Public Launch"].marker.symbol == "diamond"
    assert event_traces["Specification Release"].marker.symbol == "circle"
    assert event_traces["Archival"].marker.symbol == "square"
    assert "Stewardship Transfer" not in event_traces
    assert "Merger" not in event_traces
    assert figure.layout.xaxis.range[1] == "2027-08-07"
    assert figure.layout.xaxis.fixedrange is True
    assert list(figure.layout.yaxis.ticktext) == [
        "<b>LIVE</b><br>Tool context",
        "<b>OLD</b><br>Agent communication",
    ]
    vertical_shapes = [
        shape
        for shape in figure.layout.shapes
        if shape.type == "line" and shape.x0 == shape.x1
    ]
    assert any(shape.x0 == "2025-05-12" for shape in vertical_shapes)


def test_institutional_regimes_have_distinct_rails_certainty_and_markers() -> None:
    figure = timeline_view.build_timeline_figure(
        timeline_view.build_timeline_payload(_artifact())
    )

    stewardship = [trace for trace in figure.data if trace.name == "Stewardship regime"]
    governance = [trace for trace in figure.data if trace.name == "Governance regime"]
    assert {trace.line.dash for trace in stewardship} == {"solid", "dot"}
    assert all(trace.line.width == 6 for trace in stewardship)
    assert governance[0].line.width == 2.5
    assert governance[0].y[0] != stewardship[0].y[0]
    assert any(
        tuple(trace.text or ()) == ("Example Foundation",)
        for trace in figure.data
    )

    transition_marks = [
        trace
        for trace in figure.data
        if trace.customdata
        and str(trace.customdata[0][0]).startswith("transition_")
    ]
    symbols = {trace.marker.symbol for trace in transition_marks}
    assert "triangle-right" in symbols
    assert "triangle-right-open" in symbols
    assert "hexagon-open" in symbols
    assert "square" in symbols
    assert "bowtie" not in symbols

    interval_band = next(
        shape
        for shape in figure.layout.shapes
        if shape.type == "rect"
        and shape.x0 == "2026-04-01"
        and shape.x1 == "2026-07-01"
    )
    assert interval_band.line.dash == "dot"
    assert any(annotation.text == "OLD → LIVE" for annotation in figure.layout.annotations)
    archive = next(trace for trace in transition_marks if trace.marker.symbol == "square")
    assert archive.customdata[0][0] == "transition_old_live_merger"
    assert archive.text[0] == "OLD archived"


def test_transition_card_is_before_operation_after_and_hides_actor_ids() -> None:
    card = timeline_view.transition_card(_artifact()["transitions"][0])

    assert set(card) == {
        "id",
        "title",
        "protocols",
        "before",
        "operation",
        "after",
        "missing_fields",
        "evidence",
    }
    assert card["before"][0]["status"] == "Unknown"
    assert card["after"][0]["participants"] == (
        {"label": "Example Foundation", "role": "Institutional Home"},
    )
    assert card["operation"]["effects"] == (
        {"asset": "Protocol Family", "effect": "Transferred"},
    )
    assert card["missing_fields"] == ("Access Conditions",)
    assert card["evidence"][0]["url"] == "https://example.test/launch"
    assert "actor_foundation" not in repr(card)


def test_interval_transition_card_keeps_censoring_visible() -> None:
    card = timeline_view.transition_card(_artifact()["transitions"][2])

    assert card["operation"]["date_mode"] == "interval"
    assert card["operation"]["effective"] == (
        "2026-04-01 → 2026-07-01 (interval-censored)"
    )


def test_optional_transition_card_artifact_overrides_timeline_card() -> None:
    override = deepcopy(_artifact()["transitions"][0])
    override["summary"] = "Compiler card summary."
    payload = timeline_view.build_timeline_payload(
        _artifact(),
        transition_cards={"cards": [override]},
    )

    assert payload.transition_cards["transition_live_foundation"]["summary"] == (
        "Compiler card summary."
    )
    assert "transition_old_live_merger" in payload.transition_cards


def test_legacy_timeline_without_institutional_stream_still_renders() -> None:
    legacy = deepcopy(_artifact())
    legacy.pop("regimes")
    legacy.pop("transitions")

    payload = timeline_view.build_timeline_payload(legacy)
    figure = timeline_view.build_timeline_figure(payload)

    assert payload.regimes == ()
    assert payload.transitions == ()
    assert payload.transition_cards == {}
    assert any(trace.name == "Specification Release" for trace in figure.data)


def test_renderer_resolves_institutional_selection_to_transition_card() -> None:
    st_api = _FakeStreamlit()

    def component(_figure, **_kwargs):
        return {
            "selection": {
                "points": [{"customdata": ["transition_live_foundation"]}]
            }
        }

    timeline_view.render_protocol_timeline(
        timeline=_artifact(),
        protocol_ids=["protocol_live"],
        st_api=st_api,
        timeline_component=component,
    )

    assert "LIVE moved to Example Foundation." in st_api.writes
    assert "Protocol Family: Transferred" in st_api.writes
    assert st_api.links[-1][1] == "https://example.test/launch"
