# Pilot privacy and coordination contract

Status: implemented for `commons_pilot_2026`.

## What the participant is told

> Your strategy is stored under a random participant code, separately from any contact details. You may delete your contact details; your anonymous strategy remains part of the Commons Map. For this pilot, coordination only records interest. Future introductions are still being discussed with Nathalie, and no email is shared automatically.

## Output A — strategic mapping

Stored in `protohack_Responses`:

- random `participant_uuid` and derived public alias;
- scenario, decision, and selected action identifiers;
- the rationale as written;
- deterministic themes, capacities, and resource types authored on the action;
- protocol, tagger, privacy, integration, and revision metadata.

It stores no email and has no relation to `protohack_Players`. The public Commons Map shows aliases, selected moves, and authored themes only. It does not display rationales or UUIDs.

## Anonymous question feedback

Flags and skips are stored independently in `protohack_Events` with:

- anonymous `participant_uuid`;
- protocol, question, and event identifiers;
- selected feedback reasons and optional note;
- timestamp.

These events contain no email and do not create a coordination record. Skipping the smoking-gun decision creates no strategic profile. Skipping the rationale records its absence and may still lead to a strategic profile only after review and explicit confirmation.

## Return key and verification hash

Before integration, the private confirmation dialog shows the participant:

- a four-symbol emoji alias;
- the complete UUID textual return key;
- the complete SHA-256 verification hash.

The textual UUID is the actual resume key and is suitable for laptop copy/paste. The hash is for complete visual verification, not login. Neither is rendered on the public Commons Map or in public labels.

## Output B — optional coordination

Stored in `protohack_Players` only after `Yes`:

- the same random `participant_uuid`;
- coordination consent version and timestamp;
- `anonymous_interest` when email is blank;
- `reachable_interest` plus email when email is supplied.

`Not now` creates no contact record. Anonymous interest is counted but cannot become a matchable contact node.

## Deletion

The participant-facing deletion control removes the coordination row only. Tests verify that this operation cannot remove the strategic row. Strategic data remains anonymous and retained for the Commons Map, as confirmed for this pilot.

## Access boundary

The pilot keeps `protohack_Players` under the existing `Protocol Hack` Notion parent. This is not a separate restricted vault. The application enforces separation through distinct repository commands and distinct public/host views. The whole Notion parent should therefore remain limited to the smallest operating team.

## Explicitly open

The policy for future coordination remains undecided pending discussion with Nathalie. The pilot does not send email, reveal participant email to another participant, create automatic introductions, or claim that an expression of interest guarantees follow-up.
