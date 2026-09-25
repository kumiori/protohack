from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from storage.notion_smoking_gun import NotionSmokingGun


ROOT = Path(__file__).parent.parent
APP = ROOT / "app.py"
VIEW = ROOT / "views" / "test_probe_smoking_gun.py"


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "databases": {
                    "test_submissions": {
                        "title": "protohack_ProbeTestSubmissions",
                        "database_id": "database-test",
                        "data_source_id": "source-test",
                    },
                    "responses": {
                        "title": "protohack_Responses",
                        "database_id": "database-production",
                        "data_source_id": "source-production",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return path


class FakeUsers:
    @staticmethod
    def me():
        return {"name": "fuckthesystem"}


class FakeDataSources:
    def query(self, **arguments):
        assert arguments["page_size"] == 1
        return {"results": [], "has_more": False}

    @staticmethod
    def retrieve(**_arguments):
        return {
            "properties": {
                "Name": {"type": "title"},
                "payload": {"type": "rich_text"},
            }
        }


class FakePages:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.pages: dict[str, dict] = {}

    def create(self, **arguments):
        self.created.append(arguments)
        name = "".join(
            item["text"]["content"]
            for item in arguments["properties"]["Name"]["title"]
        )
        page = {
            "id": "smoke-page",
            "properties": {
                "Name": {"title": [{"plain_text": name}]},
            },
        }
        self.pages["smoke-page"] = page
        return page

    def retrieve(self, *, page_id: str):
        return self.pages[page_id]

    def update(self, *, page_id: str, **changes):
        self.updated.append({"page_id": page_id, **changes})
        self.pages[page_id].update(changes)
        return self.pages[page_id]


class FakeClient:
    def __init__(self) -> None:
        self.users = FakeUsers()
        self.data_sources = FakeDataSources()
        self.pages = FakePages()


def test_smoking_gun_uses_only_title_then_reads_exact_value(tmp_path: Path) -> None:
    client = FakeClient()
    gun = NotionSmokingGun(
        token="secret-token",
        environment="TEST",
        manifest_path=_manifest(tmp_path),
        client=client,
    )

    assert gun.run_all("smoke test 2026-09-24", run_id="8f13") is True

    created = client.pages.created[0]
    assert created["parent"] == {
        "type": "data_source_id",
        "data_source_id": "source-test",
    }
    assert set(created["properties"]) == {"Name"}
    assert gun.last_page_id == ""
    assert next(entry for entry in gun.trace if entry["step"] == "06 READ BACK")[
        "value_matches"
    ] is True
    assert gun.trace[-1]["result"] == "TEST SMOKE TEST: PASS"
    assert gun.trace[-1]["active_record_remains"] is False
    assert client.pages.updated == [{"page_id": "smoke-page", "in_trash": True}]
    assert "secret-token" not in json.dumps(gun.trace)


def test_delete_archives_only_current_smoke_page(tmp_path: Path) -> None:
    client = FakeClient()
    gun = NotionSmokingGun(
        token="secret-token",
        environment="TEST",
        manifest_path=_manifest(tmp_path),
        client=client,
    )
    gun.begin_run("8f13")
    gun.read_schema()
    page_id = gun.create_record("SMOKE TEST — 8f13")
    assert gun.archive(page_id) is True

    assert client.pages.updated == [{"page_id": "smoke-page", "in_trash": True}]


def test_target_metadata_comes_from_the_shared_manifest(tmp_path: Path) -> None:
    gun = NotionSmokingGun(
        token="secret-token",
        environment="PRODUCTION",
        manifest_path=_manifest(tmp_path),
        client=FakeClient(),
    )

    assert gun.target.database == "protohack_Responses"
    assert gun.target.database_id == "database-production"
    assert gun.target.data_source_id == "source-production"


def test_smoking_gun_page_is_visible_and_defaults_to_test() -> None:
    source = APP.read_text(encoding="utf-8")
    assert 'url_path="test_probe-smoking-gun"' in source
    assert 'visibility="hidden"' not in source

    app = AppTest.from_file(str(VIEW), default_timeout=10).run()

    assert not app.exception
    assert app.title[0].value == "Notion Smoking Gun"
    assert app.text_input[0].value == "smoke test 2026-09-24"
    assert app.radio[0].value == "TEST"
    assert next(button for button in app.button if button.label == "RUN SMOKE TEST")
    assert "NOTION SMOKING GUN" in [title.value for title in app.sidebar.title]


def test_production_smoke_write_requires_explicit_acknowledgement() -> None:
    app = AppTest.from_file(str(VIEW), default_timeout=10).run()

    app.radio[0].set_value("PRODUCTION").run()

    run = next(
        button for button in app.button if button.label == "RUN PRODUCTION SMOKE TEST"
    )
    assert run.disabled is True
    assert app.checkbox[0].label == "I understand this writes to production"

    app.checkbox[0].check().run()

    run = next(
        button for button in app.button if button.label == "RUN PRODUCTION SMOKE TEST"
    )
    assert run.disabled is False
