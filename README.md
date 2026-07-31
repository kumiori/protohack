# Protocol Hack · Questioning the Commons

Protocol Hack is a one-scenario strategic mapping experiment. The pilot asks a participant to make one first move, explain it in one sentence, review it, save a return key, and explicitly integrate the resulting anonymous trajectory into a Commons Map.

Every normal question systematically provides `Continue`, `Flag`, and `Skip`. Flagging uses the feedback vocabulary and an optional note. Skipping opens a dialog and requires a reason. A successful integration always triggers balloons; opening the confirmation dialog alone never writes anything.

After integration, a separate coordination step asks only:

- `Yes` or `Not now`;
- email, optionally, after `Yes`.

`Yes` without email records anonymous interest. `Not now` creates no contact record.

## Run locally

```shell
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
.venv/bin/streamlit run app.py
```

Without a database token, the app enters preview storage mode. Its records last only for the running process. To force that mode:

```shell
PROTOHACK_DEMO_MODE=true PROTOHACK_HOST_CODE=demo .venv/bin/streamlit run app.py
```

Set `MOSAIC_STATEMENT_URL` to the published Google Doc URL to expose the
“Read the statement of intent” link inside its question card.

## Surfaces

- `/` — Commons Simulator landing page and entry point;
- `/commons` — refined participant simulation, review, integration, and optional coordination;
- `/capacity` — YAML-driven needs, resources, contributions, time horizon, and coordination track;
- `/strategy` — YAML-driven scenario, priority, actors, capacities, action, rationale, and review track;
- `/mosaic` — independent YAML-driven Mosaic contribution and consortium-joining track;
- `/commons-map` — public strategic distribution and participant-theme graph;
- `/commons-host` — access-code-protected strategic, coordination, and diagnostic views;
- `/test-timeline-benchmarks` — scenario-first onboarding laboratory with eight game-like levels, challenge cards, a hidden impossible benchmark, and sidebar experiment briefs that hand selected horizons into the trajectory game;
- `/test-timeline-game` — session-only 3D trajectory sandbox using twelve event and planning primitives as hard piecewise-Hermite nodes, a continuous time/date preview slider, Smooth/Kink geometry, separate local uncertainty envelopes that never move the centreline, preserved camera orientation, simulated convergence traces, and a three-move integration gate without record writes;
- `/test-timeline-style-lab` — visual-only comparison of Instrument, Playground, and Gallery treatments over the exact same trajectory game, with oversized event objects, subtle motion, and a trajectory-first scene;
- `/test-landing-primitives` — landing-page study composed from native Streamlit primitives and scoped styled containers, without authored HTML markup;
- `/test-smokegun` — preserved first local smoke-test interface, grouped under `Tests` in navigation.
- `/ui-lab` — functional dark-theme interface study inspired by the Commons Simulator mockup, including a cumulative event-signal timeline; all controls are native Streamlit elements wrapped in scoped styled containers.

The application root introduces the Commons Simulator and links into `/commons`. The refined participant page keeps the smoke-test behavior and data contracts while giving the scenario, choice, rationale, and review a quieter visual hierarchy.

The host view does not send messages or make introductions. Coordination policy is deliberately marked open pending discussion with Nathalie.

## Content contract

The provisional smoke scenario and initial interaction contract live in [`protocol/specs/commons_smoke_v1.yaml`](protocol/specs/commons_smoke_v1.yaml). The contract requires Continue/Flag/Skip, reasoned skipping, confirmation before integration, a complete textual return key and verification hash, and balloons after successful integration. Replace scenario wording and authored action tags there; no application code change is required. The app does not automatically classify the rationale.

## Privacy boundary

- `protohack_Responses` stores anonymous strategic profiles.
- `protohack_Players` stores explicit coordination interest and optional email.
- `protohack_Events` stores anonymous question flags and skips.
- `participant_uuid` is the only bridge.
- There is a database relation from a strategic response to a player/contact row.
- Contact deletion trashes only the coordination row; the anonymous strategic profile remains.
- Both databases remain under the a database parent for this pilot, so the separation is logical and application-enforced, not a restricted-vault permission boundary.

See [`docs/privacy_contract.md`](docs/privacy_contract.md) for the exact pilot contract and [`docs/notion_bootstrap.md`](docs/notion_bootstrap.md) for database setup.

## Verification

```shell
.venv/bin/python -m pytest
NOTION_TOKEN=... .venv/bin/python scripts/bootstrap_protohack_notion.py verify
```

The focused suite covers the interaction contract, key/hash generation, required skip reasons, anonymous feedback storage, protocol loading, authored tags, idempotent integration, anonymous interest, contact-only deletion, and the absence of a strategy-to-contact relation.
