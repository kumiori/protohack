# Portable trajectory schema

Schema version: `trajectory-plan/v2`.

```yaml
schema_version: trajectory-plan/v2
plan:
  id: stable-plan-id
  title: Human-readable identity
  initial_condition: What is true now
  goal_statement: Desired future condition
  landing_mode: open | guided | planned
  temporal_mode: qualitative | linear
  guided_value: 6
  guided_unit: Months
primitives:
  - id: stable-move-id
    type: release | event | gateway | action | update | milestone | merge | share_resources | acquire_resources | delegate | wait | prepare | get_intelligence | synchronise
    title: Short label
    time_parameter: 0.32
    temporal_position: 0.32
    date: 2026-08-06
    time_basis: relative | date
    influence_scale: Local | Structural | Dominant
    directional_mode: gradually | abruptly
    topology_mode: continuation | branching
    branch_parent: null
    branch_labels:
      - {id: stable-move-id:1, parent_id: stable-move-id, label: Option A}
      - {id: stable-move-id:2, parent_id: stable-move-id, label: Option B}
    energy_effect: 0.28
    entropy_effect: 0.0
    influence_radius: 0.14
    description: Optional free text
    intention: ""
    dependencies: []
    responsible_actors: []
    collaborators: []
    resources_needed: []
    completion_evidence: []
    visibility: Private
    tags: []
    notes: ""
    created_at: 2026-08-06T10:30:00+03:00
    modified_at: 2026-08-06T10:30:00+03:00
uncertainty:
  - id: stable-chunk-id
    start_parameter: 0.30
    end_parameter: 0.54
    center_parameter: 0.42
    strength: Light | Marked | Strong
    profile_mode: balanced | expands | contracts
    radius: 0.08
    opacity: 0.16
view:
  camera: {eye: {x: 0.08, y: -2.35, z: 0.42}, center: {x: 0, y: 0, z: 0}, up: {x: 0, y: 0, z: 1}}
```

`energy_offset`, `alignment_offset` and `influence_width` remain portable runtime
aliases for the trajectory engine. Optional arrays are always lists and never
null. Continuation moves have an empty `branch_labels` list. Branching moves have
exactly two branch children. `branch_parent` is null until branch-specific move
assignment is introduced.

`guided_value` and `guided_unit` are required together when `landing_mode` is
`guided`; the value is a positive integer and the unit is Hours, Days, Weeks,
Months or Years. They determine `horizon_days`. Empty onboarding controls are UI
state only and must never be serialised as model modes.

Imports accept v2, v1 and pre-versioned trajectory documents. Migration applies
these rules without changing stable IDs:

| Older value | RC0 value |
|---|---|
| Signal | Local |
| Lever | Structural |
| Threshold | Dominant |
| smooth | gradually |
| jump or kink | abruptly |
| bifurcation node mode | branching topology |
| missing topology | continuation |
| missing details | empty strings/lists and Private visibility |

Explicit dates remain authoritative when a horizon changes; relative moves retain
their normalised position. Out-of-range dated moves are flagged rather than
deleted. Unknown future schema versions or primitive types fail visibly, while
valid older YAML is migrated rather than crashing the editor.
