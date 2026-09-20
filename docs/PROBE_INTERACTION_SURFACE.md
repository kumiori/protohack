# Probe interaction surface

Protocol Hack renders these mechanics without changing Probe Engine answer
semantics.

## Standard interaction grammar

Single-question steps use one responsive action row:

`Continuer · Signaler · Passer`

Multi-question steps keep a compact per-question menu for independent Answer or
Skip resolution and optional flags. Skip and Flag are separate controls. The step CTA succeeds only after every
visible question has an explicit answer or Skip event. Flags are supplementary
events and never resolve a question.

Review edits append a new canonical Answered or Skipped event and checkpoint the
trajectory. Earlier events remain in the trajectory.

## Subordinate value rule

A companion is supplementary and optional unless its canonical field explicitly
sets `required: true`; an empty optional companion is omitted from the composed
answer. A `free_text` field associated with Other is a conditional subordinate
value. Either form becomes mandatory only through an explicit authored
requirement. Protocol Hack submits the canonical composed shape and leaves final
validation to `ProbeRuntime`.

Canonical grouped taxonomies retain their authored option groups. Taxonomy group
headings render as collapsed expanders so functions and commons/AI domains remain
usable on narrow screens; opening a group reveals its pills.

## Location capability audit

The IceIceBaby reference is
`conference/location_lookup.py::render_location_lookup`, with orchestration in
`conference/questionnaire.py`. It does **not** use `navigator.geolocation` or
silently request browser GPS permission. It performs an OpenCage geocoding query
from participant-entered text and asks the participant to select/confirm a
result.

Its canonical value contains the display label, locality, region, country,
country code, stable place id, latitude and longitude. The richer WG2 variant
also preserves raw input, lookup source/status and explicit coordinate consent.
Lookup failure keeps manual text available and shows a non-blocking warning or
empty-result message.

The reusable implementation now lives at the Protocol Hack field-rendering
boundary. Probe Engine `location` fields retain the canonical structured value;
Protocol Hack supplies the explicitly triggered OpenCage lookup and durable
manual-entry fallback.

No IceIceBaby source contains `navigator.geolocation`, `getCurrentPosition`, or
an equivalent browser-GPS component. A “Utiliser ma position” control therefore
requires both a new explicitly triggered browser component and an upstream
canonical location value; it cannot be extracted from the reference.

## Current upstream gates

- Probe Engine `0.3.0.dev2` at commit `5bd7d7dd04c2d294c9421d6f48923fcd3266e7fe` supplies canonical composed
  Other answers and representation definitions/results.
- Structured location is a canonical field primitive in the pinned release.
- Probe Engine exposes `independently_answerable`, but the Montréal fixture still
  marks its top-level optional example fields as independently answerable. The
  renderer follows that contract and does not infer relationships from IDs or
  layout.
- Probe Engine can append Flagged events but has no inverse/unflag event, so a
  prior flag cannot yet be removed truthfully.

## Action suggestion audit

The pinned Montréal action field currently authors three suggestions:
Concertation, coalition formation/expansion, and prototype/experimentation. The
renderer now treats a selected suggestion as the complete canonical action value;
free text is an alternative or refinement.

Trajectory Lab contains scenario-specific `suggested_moves`, parsed as an event
type plus a title. These are examples tied to individual benchmark stories, not a
stable action taxonomy. IceIceBaby likewise provides interaction mechanics but no
general action taxonomy suitable for direct reuse. Expanding Montréal's action
catalogue therefore belongs in the upstream Probe definition rather than a local
Protocol Hack list.
