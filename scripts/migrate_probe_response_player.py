#!/usr/bin/env python3
"""Migrate one legacy Probe Response into the Player + Response contract."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protocol.probe_store import migrate_legacy_submission_envelope
from storage.notion import DEFAULT_MANIFEST, NotionRepository


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--participation-id", required=True)
    cli.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    cli.add_argument("--token-env", default="NOTION_TOKEN")
    cli.add_argument("--apply", action="store_true")
    return cli


def main() -> None:
    args = parser().parse_args()
    token = str(os.getenv(args.token_env, "") or "").strip()
    if not token:
        raise RuntimeError(f"{args.token_env} is required.")
    repository = NotionRepository(token=token, manifest_path=args.manifest)
    existing = repository.get_probe_trajectory(args.participation_id)
    if existing is None:
        raise RuntimeError("The requested Probe submission was not found.")
    migrated = migrate_legacy_submission_envelope(existing)
    summary = {
        "participation_id": migrated["participation_id"],
        "participant_id": migrated["participant_id"],
        "identity_fields": sorted(
            key
            for key, value in (migrated.get("player") or {}).items()
            if value not in (None, "", {}, [])
        ),
        "apply": bool(args.apply),
    }
    print(json.dumps(summary, indent=2))
    if not args.apply:
        print("dry run; pass --apply to write")
        return
    receipt = repository.commit_probe_submission(migrated)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
