# Protocol Laboratory · Questioning the Commons

This repository houses two deliberately separate research instruments. The
Protocol Laboratory makes invisible negotiations inspectable; the Commons
questionnaire continues to map strategic choices without becoming a protocol
engine.

The laboratory's founding experiment is **Experiment 01 · Connection: TCP
Handshake**. TCP is content inside the fixed laboratory grammar—not the product
architecture. Experiment definitions, deterministic execution, rendering,
scenarios, reflection, replay, and Field Notes live in the independent
[`protocol_lab`](protocol_lab) package.

## Extracted engines

The reusable logic is now maintained as two independently installable and
independently versioned packages:

- [`packages/protocol-lab`](packages/protocol-lab) — deterministic protocol
  definitions, execution, invariant evaluation, replay, hashing, and evidence;
- [`packages/trajectory-engine`](packages/trajectory-engine) — portable
  trajectory schemas, time semantics, geometry, uncertainty, branching,
  append-only realisation, and independently authored contributions.

Protocol Hack remains the consumer and owns Streamlit pages, experimental
content, styling, storage integration, and application policy. Compatibility
adapters preserve existing application imports while new consumers can use the
package APIs directly.

Protocol Hack is a one-scenario strategic mapping experiment. The pilot asks a participant to make one first move, explain it in one sentence, review it, save a return key, and explicitly integrate the resulting anonymous trajectory into a Commons Map.

Every normal question systematically provides `Continue`, `Flag`, and `Skip`. Flagging uses the feedback vocabulary and an optional note. Skipping opens a dialog and requires a reason. A successful Probe integration triggers confetti only after a repository receipt; opening the confirmation dialog alone never writes anything. Legacy question-set experiences retain their authored completion animation.

Registered Probe events share a Prediction-style persistent identity flow. A
new participant receives no return code at entry. Review produces one canonical
`probe-submission/v1` payload; immediately before integration the participant
is shown a collision-checked four-emoji shorthand and its full credential and must acknowledge saving one of them.
Only a repository receipt unlocks the success screen and celebration. Returning
participants use either credential to hydrate the stored canonical trajectory.
In interactive test mode the same envelope is written to the shared physical,
schema-neutral `protohack_ProbeTestSubmissions` Notion data source, while
production routes the identical envelope to the configured production
repository. The process-local implementation remains available for unit tests.

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

- `/protocol-lab` — Atlas landing and the fixed Question → Need → Archaeology → Observe → Expand → Execute → Break → Understand → Field Notes → Join Us laboratory;
- `/protocol-lab-host` — access-code-protected contract, provenance, saved-note, and diagnostics console;
- `/` — Commons Simulator landing page and entry point;
- `/commons` — refined participant simulation, review, integration, and optional coordination;
- `/capacity` — YAML-driven needs, resources, contributions, time horizon, and coordination track;
- `/strategy` — YAML-driven scenario, priority, actors, capacities, action, rationale, and review track;
- `/mosaic` — independent YAML-driven Mosaic contribution and consortium-joining track;
- `/commons-map` — public strategic distribution and participant-theme graph;
- `/commons-host` — access-code-protected strategic, coordination, and diagnostic views;
- `/test-timeline-benchmarks` — scenario-first onboarding laboratory with eight game-like levels, challenge cards, a hidden impossible benchmark, and sidebar experiment briefs that hand selected horizons into the trajectory game;
- `/test-timeline-game` — session-only `(time, energy, uncertainty)` trajectory sandbox using event and planning primitives as hard piecewise-Hermite nodes, a continuous time/date preview slider, gradual/abrupt geometry, separate local uncertainty envelopes that never move the centreline, preserved camera orientation, simulated convergence traces, and a three-move integration gate without record writes;
- `/test-timeline-style-lab` — visual-only comparison of Instrument, Playground, and Gallery treatments over the exact same trajectory game, with oversized event objects, subtle motion, and a trajectory-first scene;
- `/test-probe-theme-lab` — developer-only Probe typography and palette calibration using the canonical theme tokens, responsive-width specimens, state and contrast checks, portable YAML export, and six first-viewport compositions;
- `/test-landing-primitives` — landing-page study composed from native Streamlit primitives and scoped styled containers, without authored HTML markup;
- `/test-smokegun` — preserved first local smoke-test interface, grouped under `Tests` in navigation.
- `/ui-lab` — functional dark-theme interface study inspired by the Commons Simulator mockup, including a cumulative event-signal timeline; all controls are native Streamlit elements wrapped in scoped styled containers.

The application root introduces the Commons Simulator and links into `/commons`. The refined participant page keeps the smoke-test behavior and data contracts while giving the scenario, choice, rationale, and review a quieter visual hierarchy.

The host view does not send messages or make introductions. Coordination policy is deliberately marked open pending discussion with Nathalie.

## Content contract

Protocol Laboratory definitions live in [`protocol_lab/specs`](protocol_lab/specs).
The loader validates the same versioned contract for the playable TCP experiment
and non-playable OAuth, Git, and MCP canaries. Adding a protocol begins with a
definition rather than a new application branch.

The provisional smoke scenario and initial interaction contract live in [`protocol/specs/commons_smoke_v1.yaml`](protocol/specs/commons_smoke_v1.yaml). The contract requires Continue/Flag/Skip, reasoned skipping, confirmation before integration, a complete textual return key and verification hash, and balloons after successful integration. Replace scenario wording and authored action tags there; no application code change is required. The app does not automatically classify the rationale.

## Privacy boundary

- `protohack_Responses` stores anonymous strategic profiles.
- `protohack_Players` stores explicit coordination interest and optional email.
- `protohack_Events` stores anonymous question flags and skips.
- Protocol Laboratory Field Notes use the events boundary and store an access-key owner hash, replay evidence, authored observations, and interpretation challenges—never a raw access key or email.
- `participant_uuid` is the only bridge.
- There is a database relation from a strategic response to a player/contact row.
- Contact deletion trashes only the coordination row; the anonymous strategic profile remains.
- Both databases remain under the a database parent for this pilot, so the separation is logical and application-enforced, not a restricted-vault permission boundary.

See [`docs/privacy_contract.md`](docs/privacy_contract.md) for the exact pilot contract and [`docs/notion_bootstrap.md`](docs/notion_bootstrap.md) for database setup.

## Verification

```shell
.venv/bin/python -m pytest
NOTION_TOKEN=... .venv/bin/python scripts/bootstrap_protohack_notion.py discover \
  --parent-page-id 3a58547ffe9a8104b382e2755d13f7c4
NOTION_TOKEN=... .venv/bin/python scripts/bootstrap_protohack_notion.py verify
```

The focused suite covers the interaction contract, key/hash generation, required skip reasons, anonymous feedback storage, protocol loading, authored tags, idempotent integration, anonymous interest, contact-only deletion, and the absence of a strategy-to-contact relation.
