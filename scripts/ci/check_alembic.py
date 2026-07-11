#!/usr/bin/env python3
"""CI guard for the Alembic migration chain.

Runs offline (no database connection required) and enforces two invariants that
have each broken a deployment in the past:

1. **Exactly one head.** Multiple heads mean divergent migration branches that
   ``alembic upgrade head`` cannot apply without a merge revision. This has
   recurred repeatedly (see the ``merge_heads_*`` / ``merge_project_memory_*``
   revisions) and silently leaves the schema partially migrated.

2. **Revision ids <= 32 characters.** ``alembic_version.version_num`` is
   ``VARCHAR(32)``. A 33-char revision id once crash-looped a deploy because the
   id could not be written to the version table.

Both checks read only the revision scripts in ``alembic/versions`` via Alembic's
``ScriptDirectory`` — ``env.py`` is never executed and no engine is created, so
this is fast (<1s) and needs no DB, secrets, or app dependencies beyond Alembic
itself.

Exit code 0 on success, 1 on any violation (with a clear, actionable message).

Usage (from the ``backend/`` directory)::

    python ../scripts/ci/check_alembic.py

or with an explicit config path::

    python scripts/ci/check_alembic.py --config backend/alembic.ini
"""

from __future__ import annotations

import argparse
import os
import sys

# alembic_version.version_num is VARCHAR(32); ids longer than this cannot be
# persisted and crash-loop the deploy on first upgrade.
MAX_REVISION_ID_LENGTH = 32


def _resolve_config_path(explicit: str | None) -> str:
    """Locate alembic.ini, defaulting to backend/alembic.ini next to this repo."""
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", ".."))
    candidates = [
        os.path.join(os.getcwd(), "alembic.ini"),
        os.path.join(repo_root, "backend", "alembic.ini"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    # Fall back to the repo default so the error message is useful.
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=None,
        help="Path to alembic.ini (default: ./alembic.ini or backend/alembic.ini)",
    )
    args = parser.parse_args()

    config_path = _resolve_config_path(args.config)
    if not os.path.isfile(config_path):
        print(f"ERROR: alembic config not found at {config_path}", file=sys.stderr)
        return 1

    # Import lazily so the argparse/--help path works without alembic installed.
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    # ScriptDirectory is resolved relative to the config file's directory, so run
    # from there to make script_location = alembic resolve correctly.
    config_dir = os.path.dirname(os.path.abspath(config_path))
    prev_cwd = os.getcwd()
    os.chdir(config_dir)
    try:
        cfg = Config(os.path.basename(config_path))
        script = ScriptDirectory.from_config(cfg)
        heads = list(script.get_heads())
        revisions = list(script.walk_revisions())
    finally:
        os.chdir(prev_cwd)

    errors: list[str] = []

    # --- Check 1: exactly one head -----------------------------------------
    if len(heads) == 0:
        errors.append(
            "No migration heads found — the alembic/versions directory appears "
            "empty or unreadable."
        )
    elif len(heads) > 1:
        errors.append(
            "Multiple Alembic heads detected "
            f"({len(heads)}): {', '.join(sorted(heads))}\n"
            "  The migration chain has diverged. `alembic upgrade head` cannot "
            "apply divergent branches.\n"
            "  Fix: create a merge revision with "
            '`alembic merge -m "merge heads" <head1> <head2>` so there is '
            "exactly one head."
        )

    # --- Check 2: revision ids fit in VARCHAR(32) --------------------------
    too_long = [
        (rev.revision, len(rev.revision))
        for rev in revisions
        if len(rev.revision) > MAX_REVISION_ID_LENGTH
    ]
    if too_long:
        detail = "\n".join(
            f"    {rev} ({length} chars)" for rev, length in sorted(too_long)
        )
        errors.append(
            "Revision id(s) exceed the "
            f"{MAX_REVISION_ID_LENGTH}-char limit of alembic_version.version_num "
            "(VARCHAR(32)):\n"
            f"{detail}\n"
            "  A revision id longer than 32 chars cannot be written to the "
            "version table and crash-loops the deploy.\n"
            "  Fix: shorten the `revision = ...` id (and any `down_revision` that "
            "points at it) to <= 32 characters."
        )

    if errors:
        print("Alembic migration check FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"- {err}\n", file=sys.stderr)
        return 1

    head = heads[0]
    print(
        f"Alembic migration check passed: single head {head!r}, "
        f"{len(revisions)} revisions, all ids <= {MAX_REVISION_ID_LENGTH} chars."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
