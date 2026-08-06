# Changelog

## Unreleased

### Release Candidate 0.1

Walkthrough: [RC0 timeline planner screencast](https://www.loom.com/share/f229aac82b9f4d238ee27162379336c9).

- Made empty Landing and Time choices safe UI states, gated progression on a
  valid choice, and prevented `None` from crossing into trajectory payloads.
- Replaced Guided landing presets with a required positive value and unit whose
  duration sets the horizon.
- Separated non-uniform qualitative anchors from proportional calendar/elapsed
  linear ticks and placed every move title beside its plot marker.
- Hid binary branch controls under the Bifurcation choice while preserving the
  portable `branching` model and named children.
- Applied one responsive typography scale across onboarding, benchmark and
  trajectory pages, with readable control, helper and disabled states.

### Release Candidate 0

- Added Acquire resources and Delegate while preserving the complete event and
  planning-primitive panel.
- Replaced the legacy importance vocabulary with Local, Structural and Dominant
  influence; each level now controls deformation amplitude and temporal radius.
- Separated Gradually/Abruptly direction from Continuation/Branching topology,
  with Structural, Gradually and Continuation as safe defaults.
- Added genuine binary branch rendering with a shared past, two persistent named
  children and two visible outgoing stems.
- Added a dark, readable optional-details expander with a saved free-text
  description for every move.
- Upgraded trajectory YAML to v2 and added safe migration for v1 and unversioned
  plans, legacy scale/node names, missing topology and missing detail values.

- Added the separate guided `Sketch a new plan` route.
- Restored the complete event and planning-primitive vocabulary in the plan field.
- Added information gateways and local balanced, expanding or contracting
  uncertainty tubes while preserving a crisp centreline.
- Added local autosave, latest-plan recovery, YAML import/export, duplication,
  safe new-plan navigation, and editable Goal/Time re-entry.
- Distinguished trajectory integration from device saving and portable export.
- Changed the initial camera to the Horizon–Energy projection, tightened bounds,
  increased axis contrast, and made interactive states explicit.
- Freed the native sidebar resizer, repaired latest-plan recovery through a
  permitted plan tab, made expanding uncertainty monotonic, and corrected light
  action surfaces to use dark text.
- Promoted the Style Lab Playground move objects into the main timeline game,
  including oversized semantic glyphs, coloured material cards, hover motion,
  press feedback and selected-state outlines.
