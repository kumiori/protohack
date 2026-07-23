# Protocol Hack database bootstrap

The database family lives under the [ProtocolHack page](https://app.notion.com/p/ProtocolHack-3a554516e9e18023b1f4ef9fc0cad03c), beside `IceIceBaby` in the same workspace.

Created databases:

- `protohack_Sessions`
- `protohack_Statements`
- `protohack_Players`
- `protohack_Responses`
- `protohack_Questions`
- `protohack_ModerationVotes`
- `protohack_Decisions`
- `protohack_Events`

The non-secret database and data-source IDs are recorded in `config/protohack_notion.json`. The Notion token is never written by the bootstrap. The current schema is `protohack-notion-v2-mapping-coordination`.

The first database family was accidentally created through a connector bound to the `Science` workspace. Its IDs are retained only for provenance in `config/protohack_notion.science-orphaned.json`; the application never reads that archive.

## Commands

Install the client generation:

```shell
python -m pip install notion-client==3.0.0
```

Preview the database family without network access:

```shell
python scripts/bootstrap_protohack_notion.py plan
```

Verify the existing databases:

```shell
NOTION_TOKEN=... python scripts/bootstrap_protohack_notion.py verify
```

Emit the Streamlit configuration block from the manifest:

```shell
python scripts/bootstrap_protohack_notion.py emit-secrets
```

Create or resume a fresh database family under another Notion page:

```shell
NOTION_TOKEN=... python scripts/bootstrap_protohack_notion.py create \
  --parent-page-id NOTION_PAGE_ID \
  --manifest config/another_protohack_notion.json
```

The `create` command checkpoints each new database immediately. If relation creation or session seeding is interrupted, rerun the same command with the same manifest to resume without duplicating databases. It also reconciles missing v2 properties in an existing manifest and removes the prohibited `protohack_Responses.player` relation.

## Application mapping

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`, add the token and host access code locally, and keep the real secrets file out of version control. The application reads the data-source IDs from the checked-in manifest and never falls back to any `ice_*` database ID.

The initial session is `commons_pilot_2026`. The smoke protocol remains visibly marked draft until its final question wording is approved.

## Mapping and coordination fields

`protohack_Responses` is the anonymous strategic store. It contains `participant_uuid`, scenario/decision/action IDs, rationale, authored tags, the serialized strategic profile, version metadata, and integration timestamps. It deliberately has no relation to `protohack_Players`.

`protohack_Players` is retained in its current location for the pilot. It contains `participant_uuid`, opt-in, consent version/time, coordination status, and optional email. `anonymous_interest` means `Yes` without email; `reachable_interest` means `Yes` with email.
