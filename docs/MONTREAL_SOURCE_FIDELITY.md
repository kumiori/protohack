# Montréal source-fidelity audit

This audit follows the participant surface boundary:

`authored source → Probe Engine → ProbeDefinition → Protocol Hack renderer`

The executable authored sources are Protocol Hack's local
`question_sets/montreal_communs_2026/short.yaml` and
`question_sets/montreal_communs_2026/initial_conditions_v0.yaml`. Probe Engine at
commit `f5bb61a121cd498fde97886c2d226a014d5d4255` (package `0.3.0.dev6`) parses and
validates them but is not their content store. The supplied
`V2-DOC_QuestionnaireMapping.md` is reference prose, not executable YAML.

## Boundary accounting

| Source construct | ProbeDefinition | Protocol Hack presentation | Status |
|---|---|---|---|
| Probe id, revision, title, status, language | Canonical probe fields and metadata | Title plus sidebar identity | Preserved |
| Ordered sections | `SectionDefinition` | Section caption above each step | Preserved |
| Ordered interaction steps | `StepDefinition` | One screen per step | Preserved |
| Step title, body and CTA | Canonical step fields | Heading, explanatory body and primary action | Preserved |
| Ordered top-level fields | `QuestionDefinition` references from each step | Colocated in authored order | Preserved |
| Field prompt and context | Canonical field text | Heading and caption | Preserved |
| Required state | `required` | Enforced by `ProbeRuntime`; explicit Skip remains separate | Preserved |
| Single, multiple and text values | Canonical input types | Radio, pills and text controls | Preserved |
| Taxonomy values and labels | Canonical `Taxonomy` | Stable values submitted; labels displayed | Preserved |
| Taxonomy groups and presentation | Canonical `OptionGroup` plus `presentation.groups` | Collapsed expanders with selected counts where authored | Preserved |
| Conditions | Canonical equality `Condition` | Visibility evaluated from prior canonical answers | Preserved |
| Selection and item constraints | Canonical min/max values | Display hints plus `ProbeRuntime.answer()` validation | Preserved |
| Suggestions | Canonical options attached to text | Suggestion selector plus arbitrary text | Preserved |
| Repeatable action/actors | Recursive item fields with stable row id | Add/edit/remove rows; structured list submitted | Preserved |
| Question revision | Canonical revision | Recorded on every answer/skip event | Preserved |
| Answer, Skip and Flag | Canonical trajectory events | Compact per-question actions menu | Preserved |
| Checkpoints and sync points | Canonical section process and checkpoint capabilities | Private draft checkpoint surface; separate sync-arrival event | Preserved |
| Other + associated text | Canonical composed `{selected, other: {value}}` answer | Inline text control, including grouped and nested repeatable selections | Preserved |
| Welcome and Done | Canonical `StepDefinition` nodes with authored title, body and CTA | Rendered directly from the canonical steps | Preserved |
| Review | Canonical structured answer state | Application navigation and structured recomposition; no authored answer shape is flattened | **Application flow over canonical state** |
| `representations` and `results` source blocks | Canonical representation and results definitions | Results surface consumes the definitions | Preserved at boundary |

## Reference-document differences

The prose mapping may contain material that is not present in the executable local
source and therefore cannot appear in the UI without changing that authored
definition. Examples requiring an authored-source decision include:

- the long registration introduction and full research/retention information;
- named research contacts;
- longer contextual explanations for participation, portrait and future vision;
- substantially larger option catalogues for availability, sectors, functions,
  shared/researched knowledge and fictional roles;
- several questions described as open text in the prose but represented as
  constrained multiple-choice fields in the canonical fixture;
- the prose numbering and section labels, which do not map one-to-one to the
  canonical interaction steps.

These differences are reported rather than reconstructed in the renderer. The
local authored Probe source must be updated if the prose is intended to be
participant-visible; Probe Engine remains the parser and semantic authority.

## URL and persistence identity

The canonical public root is `/commons-montreal`. Its three perspectives are
selected without changing the event identity:

- `/commons-montreal` — Probe;
- `/commons-montreal?view=results` — public representations;
- `/commons-montreal?view=host` — operational state.

`version` is optional and selects a registered canonical Probe variant (`short`
today). It is required only when an event has multiple participant variants.

The older identifiers have these contracts:

| Identifier | Meaning | Lifetime | Navigation | Resume | Exposure |
|---|---|---|---|---|---|
| `session` | Persistence namespace for an event run | Event/session lifetime | No; the event slug now resolves it | Indirectly, through the registry | Do not expose in new URLs |
| `run` | Stable pseudonymous participant/recovery key | Participant journey | No | Yes, until a deliberate recovery token replaces it | Client-visible but bearer-like; share privately |
| `participation` | Probe Engine trajectory identity | One Probe participation | No | No for new links; derived from event/session + Probe + `run` | Internal; legacy links remain readable |

New resumable participant links therefore need only
`/commons-montreal?run=<recovery-key>`. The route supplies event identity and the
registry supplies the session namespace and Probe. `?test=1` selects an explicit
dry-run repository: intended upserts and acknowledgements are observable, but no
production database query is executed.
