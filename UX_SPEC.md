# Trajectory planner UX specification

## Complete page flow

The separate `Sketch a new plan` route reveals Plan → Now → Goal → Landing →
Time → Ready. The Ready screen states that the endpoints are clear and the curve
is provisional. The field then reveals the complete move vocabulary. A move is
defined in this order: primitive → temporal position → title → influence →
direction → topology → optional branch names → optional details → place.
Editing Goal or Time re-enters onboarding and preserves placed geometry.
Landing and Time initially allow no selection, but Continue remains disabled
until the user makes a valid choice. Guided landing reveals a unit followed
immediately by the required question “Approximately how many?”.

## Control states

Every actionable control exposes enabled, hover, pressed, selected and disabled
states. Disabled controls are readable, do not respond, and are paired with a
reason where progression is gated. Enabled primary actions use the accent surface;
selected move objects retain an outline and stronger colour; press feedback lasts
about 70–100 ms. Focus and expanded states must remain visible.

Hovering a primitive raises and brightens its material card without changing its
selection. The selected primitive keeps its semantic colour and gains a high-
contrast outline. Influence, direction and topology are separate segmented
controls. Structural, Gradually and Continuation are the defaults, so a first-time
tester does not accidentally create a branch.

## Visual hierarchy and typography

The trajectory is the dominant object. Time and Energy form the initial
projection; Uncertainty is depth. The preview uses the full horizontal extent and the
camera persists across every Streamlit rerun.

- Hero or step question: `clamp(42px, 5.2vw, 72px)`, 700–800 weight.
- Secondary page title: `clamp(32px, 3.5vw, 48px)`.
- Section title: `clamp(24px, 2.2vw, 32px)`.
- Control-group question: 20 px; option and button labels: 17–18 px.
- Body: `clamp(15px, 1.1vw, 17px)` with 1.5 line height.
- Helper text: 14 px; option explanation: 13 px; metadata: 11–12 px.

Below 900 px the hero caps at 48 px, controls remain at least 16 px, helper
text remains at least 13 px, and buttons remain at least 52 px high. Disabled
controls change opacity and contrast without shrinking text. The same scale is
used by onboarding, benchmark and trajectory pages. Large type introduces the
question, medium type carries the decision, and small type only supports it.

## Colour and contrast tokens

The semantic tokens are page background, raised surface, selected surface, hover
surface, primary text, secondary text, muted text, border, accent, danger and
success. Expanders remain dark with a visible chevron, hover surface and focus
ring. Disabled controls use an opaque muted surface rather than low opacity.
Placeholder text, inactive tabs, progress steps and Plotly labels must remain
readable against their immediate surface.

The optional-details expander uses the same near-black surface as the move rail.
Its header, chevron, label, placeholder and entered text remain readable at rest,
on hover and on focus; no white header surface is permitted.

## Branch preview and editing

Continuation shows no branch configuration. Selecting Bifurcation progressively
reveals a fixed branch count of two and two name fields with Option A and Option
B defaults; they are persisted only as `branching` topology.
The placed result shows one common incoming line and two differently coloured,
labelled outgoing stems. Gradually previews a smooth separation; Abruptly previews
an immediate directional split. Both stems remain visible through reruns, save,
reload and YAML round trips. RC0 keeps later moves common to both futures;
branch-specific move assignment and merging are deferred.

## Navigation and plan lifecycle

The active-plan menu contains overview, Edit goal, Edit time, Save locally,
Export YAML, Duplicate, Start another plan, and Return to my plans. Starting a
blank plan opens Save and continue, Export and continue, Discard, and Cancel.
Autosave is local and visible. Imports and recovery never replace the active plan
until validation succeeds.

## Saving, integration and error states

`Integrate trajectory`, `Save locally`, and `Export YAML` are distinct actions.
Integration accepts the current meaning; it does not claim persistence. The
status vocabulary is Unsaved changes, Saving, Saved on this device, Exported and
Save failed. The current browser implementation normally settles immediately on
Saved on this device; import and storage failures must show a readable in-theme
error while retaining the in-memory plan.

## Shared goals and explicit sharing

`/shared-goals` is a public experimental index backed by the shared repository.
An open goal card shows its title, objective, creator agent and contribution
count. Opening a goal reveals Trajectories, Compare and Overlay. “Sketch my
trajectory” enters the existing onboarding and individual planner with only a
separate `goal_id` session context; it never opens a collaborative editor.

Local save and social sharing are different actions. Autosave, Save locally and
Export YAML never write to a shared goal. The planner writes a contribution only
after the participant explicitly chooses “Share trajectory with this goal”. A
shared contribution can later be edited in the same individual planner and
published with “Update shared trajectory”; its trajectory ID, goal ID, agent ID
and creation time remain stable while its canonical payload, update time and
revision advance.

There is no separate Join action. Contribution is the only RC0.2 participation
act. Duplicate active contributions for the same `goal_id + agent_id` fail
visibly unless the participant explicitly updates the existing trajectory.
Different temporal languages, landing modes and dates remain native to each
trajectory. Compare and Overlay use only the intrinsic normalized Now → Landing
coordinate and expose native temporal metadata on inspection or hover. They do
not score consensus, average geometry or synthesize a path.

## Camera and responsive behaviour

The camera begins in the Time–Energy projection with Uncertainty as depth. It is
restored after add, edit, undo, uncertainty, integration and rerender. Bounds
expand but do not contract in-session. Below 760 px, titles clamp, progress wraps,
the main container loses excess padding, and the field retains at least 470 px of
height. No primary decision may become visually minor on a narrow screen.
