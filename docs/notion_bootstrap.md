# Protocol Hack database bootstrap

The authoritative database family lives under the [Protocol Hack page](https://app.notion.com/p/Protocol-Hack-3a58547ffe9a8104b382e2755d13f7c4) in the Science workspace.

Expected databases:

- `protohack_Statements`
- `protohack_Sessions`
- `protohack_Responses`
- `protohack_Questions`
- `protohack_Players`
- `protohack_Decisions`
- `protohack_ModerationVotes`
- `protohack_Events`
- `protohack_Goals`
- `protohack_GoalTrajectories`
- `protohack_TimelineRooms`
- `protohack_TimelineMembers`
- `protohack_TimelineEvents`
- `protohack_ProbeTestSubmissions`

The non-secret database and data-source IDs, plus a property-type snapshot for each data source, are recorded in `config/protohack_notion.json`. The Notion token is never written by the bootstrap. The current schema is `protohack-notion-v7-player-credential`.

Probe access credentials belong exclusively to `protohack_Players`: the complete
emoji sequence, its four- and six-symbol selectors, and the verifier are stored
once with the Player. Response revisions contain a Player relation but never a
copy of credential material.

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

Discover the configured integration's existing database family:

```shell
export NOTION_TOKEN="…"
python scripts/bootstrap_protohack_notion.py discover \
  --parent-page-id 3a58547ffe9a8104b382e2755d13f7c4
python scripts/bootstrap_protohack_notion.py verify
python scripts/bootstrap_protohack_notion.py emit-secrets
```

`discover` first retrieves an explicitly configured parent ID. Otherwise it
tries the manifest's parent and, if that stored ID is no longer accessible,
searches for exactly one accessible `ProtocolHack` page. It enumerates only direct child databases,
matches all expected names exactly, records both IDs and schema snapshots,
resolves the canonical `commons_pilot_2026` session from the discovered
Sessions data source, verifies every object before and after the atomic manifest write, then prints
the exact Streamlit configuration block. It performs no Notion writes. Use
`--parent-title` or `--parent-page-id` to disambiguate a differently named
parent. The CLI reads only the environment variable selected by `--token-env`
(default `NOTION_TOKEN`); it does not import Streamlit secrets or
`storage.context`.

Verify the existing databases:

```shell
NOTION_TOKEN=... .venv/bin/python scripts/bootstrap_protohack_notion.py verify
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

The hidden `/test_probe-smoking-gun` page reads that same manifest. Both TEST
and explicitly acknowledged PRODUCTION full runs create one uniquely named
row, read it by page ID, compare the exact value, archive that exact page, and
read it once more to verify its archived state. A passing run leaves no active
diagnostic row.

The initial session is `commons_pilot_2026`. The smoke protocol remains visibly marked draft until its final question wording is approved.

## Mapping and coordination fields

`protohack_Responses` is the anonymous strategic store. It contains `participant_uuid`, scenario/decision/action IDs, rationale, authored tags, the serialized strategic profile, version metadata, and integration timestamps. It deliberately has no relation to `protohack_Players`.

`protohack_Players` is retained in its current location for the pilot. It contains `participant_uuid`, opt-in, consent version/time, coordination status, and optional email. `anonymous_interest` means `Yes` without email; `reachable_interest` means `Yes` with email.

Final Probe integration uses an explicit two-object contract. Stable identity
and profile data plus the credential selector/verifier are upserted into
`protohack_Players` by the internal participant ID. The substantive envelope
is written to `protohack_Responses` and linked through its `player` relation.
Email is an attribute, never an identity key. A successful receipt requires
read-back verification of both pages and their relation.

One legacy response can be repaired explicitly with:

```shell
NOTION_TOKEN=... python scripts/migrate_probe_response_player.py \
  --participation-id PARTICIPATION_ID --apply
```

Without `--apply`, the command reports only non-sensitive IDs and populated
field names and performs no write.

## Shared trajectory coordination

`protohack_Goals` stores public objective identity, creator attribution and
open/closed state. It contains no owner, common time language, common landing
mode, dates, geometry or primitives.

`protohack_GoalTrajectories` stores one contribution per goal and agent. Its
`trajectory_payload` field is the canonical serialized `trajectory-plan/v2`
document. The relation to `protohack_Goals` is the synchronization boundary;
the trajectory schema remains authoritative. Duplicate active contributions
are rejected unless an explicit revision update preserves trajectory, goal,
agent and creation identities.
