#!/usr/bin/env python3
"""Coordination bridge for concurrent self-improvement loops (e.g. clawd + zcode).

Two agents run the same /nous-loop against one repo. The blind spot is the
pick -> open-PR window: `gh pr list` only shows work that already has a PR, so
both loops can pick the SAME bug before either opens one. This is a shared
claims board, guarded by an exclusive file lock, that each loop writes BEFORE
touching code and reads BEFORE picking a bug.

Storage (outside the git repo, on the shared filesystem both agents see):
  $LOOP_BRIDGE_DIR (required unless an established legacy board exists)
    claims.json   current state {"claims": [ ... ]}
    log.jsonl     append-only audit of every action
    .lock         flock target for atomic read-modify-write

A claim is keyed by branch and carries an `area` (free-text bug/subsystem id)
and optional `files`. `claim` REFUSES (exit 2) if a live claim from another
agent overlaps by area or by any file path — so the loser picks something else.
Claims carry a TTL (default 45m); a crashed loop's claims expire so they stop
blocking. `heartbeat` extends the TTL each tick.

Usage:
  loop_bridge.py claim   --agent A --branch B --area "..." [--files a.py,b.py] [--pr N]
  loop_bridge.py heartbeat --branch B
  loop_bridge.py release --branch B [--reason merged|abandoned]
  loop_bridge.py list    [--json]
  loop_bridge.py check   --area "..." [--files a.py,b.py]   # exit 2 if conflict

Identity: --agent, else $LOOP_AGENT, else "$USER@$HOSTNAME".
Exit codes: 0 ok / 2 conflict / 1 usage-or-error.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import socket
import sys
from contextlib import contextmanager
from json import dumps as _json_dumps
from pathlib import Path

try:
    from scripts.nous import backend_local
except ModuleNotFoundError:
    # Preserve direct ``python scripts/loop_bridge.py`` execution, where the
    # script directory (rather than the repository root) is first on sys.path.
    from nous import backend_local


LocalBackend = backend_local.LocalBackend
BackendUnavailable = backend_local.BackendUnavailable
Conflict = backend_local.Conflict
ValidationError = backend_local.ValidationError

DEFAULT_TTL_SECONDS = backend_local.DEFAULT_TTL_SECONDS
DEFAULT_BRIDGE_DIR = Path("/home/clawdbot/.loop-bridge")


class BridgeError(Exception):
    """Expected configuration or state failure reported without a traceback."""


def _bridge_dir() -> Path:
    try:
        return backend_local.resolve_bridge_dir(
            os.environ.get("LOOP_BRIDGE_DIR"), DEFAULT_BRIDGE_DIR
        )
    except (BackendUnavailable, ValidationError) as exc:
        raise BridgeError(str(exc)) from exc


def _now() -> _dt.datetime:
    return backend_local._now()


def _iso(dt: _dt.datetime) -> str:
    return backend_local._iso(dt)


def _parse(ts: str) -> _dt.datetime:
    return backend_local._parse(ts)


def _default_agent() -> str:
    return (
        os.environ.get("LOOP_AGENT")
        or f"{os.environ.get('USER', 'unknown')}@{socket.gethostname()}"
    )


@contextmanager
def _locked():
    try:
        with backend_local.locked(_bridge_dir()) as bridge_dir:
            yield bridge_dir
    except (BackendUnavailable, ValidationError) as exc:
        raise BridgeError(str(exc)) from exc


def _read(d: Path) -> dict:
    try:
        return backend_local.read_mutating(d)
    except (BackendUnavailable, ValidationError) as exc:
        raise BridgeError(str(exc)) from exc


def _decode_state(raw: str) -> dict:
    return backend_local.decode_state(raw)


def _read_observational(d: Path) -> tuple[dict, str | None]:
    return backend_local.read_observational(d)


def _write(d: Path, state: dict) -> None:
    try:
        backend_local.write_state(d, state)
    except (BackendUnavailable, ValidationError) as exc:
        raise BridgeError(str(exc)) from exc


def _audit(d: Path, action: str, entry: dict) -> None:
    try:
        backend_local.audit(d, action, entry, now=_now)
    except (BackendUnavailable, ValidationError) as exc:
        raise BridgeError(str(exc)) from exc


def _live(state: dict) -> list[dict]:
    return backend_local.live_claims(state, now=_now())


def _files(arg: str | None) -> list[str]:
    if not arg:
        return []
    return [f.strip() for f in arg.split(",") if f.strip()]


def _overlap(a: dict, area: str, files: list[str]) -> str | None:
    return backend_local.overlap(a, area, files)


def _backend() -> LocalBackend:
    return LocalBackend(_bridge_dir())


def _bridge_failure(exc: Exception) -> BridgeError:
    return BridgeError(str(exc))


def cmd_claim(args) -> int:
    agent = args.agent or _default_agent()
    area = args.area
    files = _files(args.files)
    try:
        _backend().claim_legacy(agent, args.branch, area, files, args.pr, args.ttl)
    except Conflict as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (BackendUnavailable, ValidationError) as exc:
        raise _bridge_failure(exc) from exc
    print(f"CLAIMED '{area}' as {agent} on {args.branch} (ttl {args.ttl}s)")
    return 0


def cmd_heartbeat(args) -> int:
    try:
        _backend().heartbeat_legacy(args.branch, args.ttl)
    except (BackendUnavailable, ValidationError) as exc:
        raise _bridge_failure(exc) from exc
    print(f"HEARTBEAT {args.branch} (+{args.ttl}s)")
    return 0


def cmd_release(args) -> int:
    bridge_dir = _bridge_dir()
    state, read_error = _read_observational(bridge_dir)
    before = (
        None
        if read_error is not None
        else any(
            claim.get("branch") == args.branch for claim in state.get("claims", [])
        )
    )
    try:
        LocalBackend(bridge_dir).release_legacy(args.branch, args.reason)
    except (BackendUnavailable, ValidationError) as exc:
        raise _bridge_failure(exc) from exc
    print(
        f"RELEASED {args.branch} ({args.reason})"
        if before is not False
        else f"no claim {args.branch}"
    )
    return 0


def cmd_list(args) -> int:
    try:
        live = _backend().list_legacy()
    except (BackendUnavailable, ValidationError) as exc:
        raise _bridge_failure(exc) from exc
    if args.json:
        print(_json_dumps(live, indent=2, sort_keys=True))
        return 0
    if not live:
        print("(no active claims)")
        return 0
    for c in live:
        pr = f" PR#{c['pr']}" if c.get("pr") else ""
        print(
            f"- [{c.get('agent')}] {c.get('area')}  "
            f"(branch {c.get('branch')}{pr}, expires {c.get('expires_at')})"
        )
        if c.get("files"):
            print(f"    files: {', '.join(c['files'])}")
    return 0


def cmd_check(args) -> int:
    area = args.area
    files = _files(args.files)
    try:
        conflicts = _backend().check_legacy(area, files)
    except Conflict as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (BackendUnavailable, ValidationError) as exc:
        raise _bridge_failure(exc) from exc
    for c in conflicts:
        why = _overlap(c, area, files)
        if why:
            print(
                f"CONFLICT: {c.get('agent')} holds '{c.get('area')}' "
                f"(branch {c.get('branch')}, {why}).",
                file=sys.stderr,
            )
            return 2
    print("CLEAR")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="loop_bridge.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("claim")
    c.add_argument("--agent")
    c.add_argument("--branch", required=True)
    c.add_argument("--area", required=True)
    c.add_argument("--files")
    c.add_argument("--pr")
    c.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    c.set_defaults(fn=cmd_claim)

    h = sub.add_parser("heartbeat")
    h.add_argument("--branch", required=True)
    h.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    h.set_defaults(fn=cmd_heartbeat)

    r = sub.add_parser("release")
    r.add_argument("--branch", required=True)
    r.add_argument("--reason", default="done")
    r.set_defaults(fn=cmd_release)

    le = sub.add_parser("list")
    le.add_argument("--json", action="store_true")
    le.set_defaults(fn=cmd_list)

    ck = sub.add_parser("check")
    ck.add_argument("--area", required=True)
    ck.add_argument("--files")
    ck.set_defaults(fn=cmd_check)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except (BridgeError, OSError) as exc:
        print(f"loop bridge error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
