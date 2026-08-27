#!/usr/bin/env python3
"""Coordination bridge for concurrent self-improvement loops (e.g. clawd + zcode).

Two agents run the same /nous-loop against one repo. The blind spot is the
pick -> open-PR window: `gh pr list` only shows work that already has a PR, so
both loops can pick the SAME bug before either opens one. This is a shared
claims board, guarded by an exclusive file lock, that each loop writes BEFORE
touching code and reads BEFORE picking a bug.

Storage (outside the git repo, on the shared filesystem both agents see):
  $LOOP_BRIDGE_DIR (default /home/clawdbot/.loop-bridge)
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
import fcntl
import json
import os
import socket
import sys
from contextlib import contextmanager
from pathlib import Path

DEFAULT_TTL_SECONDS = 45 * 60


def _bridge_dir() -> Path:
    return Path(os.environ.get("LOOP_BRIDGE_DIR", "/home/clawdbot/.loop-bridge"))


def _now() -> _dt.datetime:
    # tz-aware UTC; passed in via the environment is not needed here since this
    # runs live (not inside a replayable workflow).
    return _dt.datetime.now(_dt.timezone.utc)


def _iso(dt: _dt.datetime) -> str:
    return dt.isoformat()


def _parse(ts: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(ts)


def _default_agent() -> str:
    return (
        os.environ.get("LOOP_AGENT")
        or f"{os.environ.get('USER', 'unknown')}@{socket.gethostname()}"
    )


@contextmanager
def _locked():
    d = _bridge_dir()
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".lock"
    with open(lock_path, "w") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            yield d
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _read(d: Path) -> dict:
    p = d / "claims.json"
    if not p.exists():
        return {"claims": []}
    try:
        return _decode_state(p.read_text())
    except ValueError:
        # Corrupt board must not wedge every loop — start clean but keep a copy.
        p.rename(d / "claims.corrupt.json")
        return {"claims": []}


def _decode_state(raw: str) -> dict:
    """Decode and validate the complete on-disk claims-board schema."""
    if not raw.strip():
        raise ValueError("claims state is empty")
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"claims state is not valid JSON: {exc}") from exc
    if not isinstance(state, dict):
        raise ValueError("claims state root must be an object")

    claims = state.get("claims")
    if not isinstance(claims, list):
        raise ValueError("claims state must contain a claims list")

    for index, claim in enumerate(claims):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict):
            raise ValueError(f"{prefix} must be an object")
        for field in ("agent", "branch", "area", "status", "claimed_at", "expires_at"):
            value = claim.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{prefix}.{field} must be a non-empty string")
        if claim["status"] != "active":
            raise ValueError(f"{prefix}.status must be active")
        files = claim.get("files")
        if not isinstance(files, list) or not all(
            isinstance(path, str) and path for path in files
        ):
            raise ValueError(f"{prefix}.files must be a list of non-empty strings")
        pr = claim.get("pr")
        if pr is not None and (isinstance(pr, bool) or not isinstance(pr, (str, int))):
            raise ValueError(f"{prefix}.pr must be a string, integer, or null")
        for field in ("claimed_at", "expires_at"):
            try:
                parsed = _parse(claim[field])
            except ValueError as exc:
                raise ValueError(f"{prefix}.{field} must be an ISO timestamp") from exc
            if parsed.tzinfo is None:
                raise ValueError(f"{prefix}.{field} must include a timezone")
    return state


def _read_observational(d: Path) -> tuple[dict, str | None]:
    """Read claims without creating, locking, renaming, or repairing storage.

    Writers publish ``claims.json`` with an atomic rename, so an observational
    reader does not need the mutation lock. Corruption is reported instead of
    repaired because ``list`` is used during read-only preflight and audits.
    """
    p = d / "claims.json"
    if not p.exists():
        return {"claims": []}, None
    try:
        return _decode_state(p.read_text()), None
    except (OSError, ValueError) as exc:
        return {"claims": []}, f"invalid claims state in {p}: {exc}"


def _write(d: Path, state: dict) -> None:
    p = d / "claims.json"
    tmp = d / "claims.json.tmp"
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(p)  # atomic on the same filesystem


def _audit(d: Path, action: str, entry: dict) -> None:
    rec = {"ts": _iso(_now()), "action": action, **entry}
    with open(d / "log.jsonl", "a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _live(state: dict) -> list[dict]:
    now = _now()
    out = []
    for c in state.get("claims", []):
        try:
            if _parse(c["expires_at"]) > now and c.get("status") == "active":
                out.append(c)
        except (KeyError, ValueError):
            continue
    return out


def _files(arg: str | None) -> list[str]:
    if not arg:
        return []
    return [f.strip() for f in arg.split(",") if f.strip()]


def _overlap(a: dict, area: str, files: list[str]) -> str | None:
    if area and a.get("area", "").strip().lower() == area.strip().lower():
        return f"same area '{a['area']}'"
    shared = set(a.get("files", [])) & set(files)
    if shared:
        return f"shared files {sorted(shared)}"
    return None


def cmd_claim(args) -> int:
    agent = args.agent or _default_agent()
    area = args.area
    files = _files(args.files)
    with _locked() as d:
        state = _read(d)
        # Conflict against OTHER agents' live claims (same agent re-claiming its
        # own branch is an update, never a conflict).
        for c in _live(state):
            if c.get("branch") == args.branch and c.get("agent") == agent:
                continue
            why = _overlap(c, area, files)
            if why:
                print(
                    f"CONFLICT: {c.get('agent')} already holds '{c.get('area')}' "
                    f"(branch {c.get('branch')}, {why}). Pick something else.",
                    file=sys.stderr,
                )
                return 2
        now = _now()
        claim = {
            "agent": agent,
            "branch": args.branch,
            "area": area,
            "files": files,
            "pr": args.pr,
            "status": "active",
            "claimed_at": _iso(now),
            "expires_at": _iso(now + _dt.timedelta(seconds=args.ttl)),
        }
        # Replace any prior claim for this branch (idempotent re-claim/update).
        state["claims"] = [
            c for c in state.get("claims", []) if c.get("branch") != args.branch
        ]
        state["claims"].append(claim)
        _write(d, state)
        _audit(d, "claim", claim)
    print(f"CLAIMED '{area}' as {agent} on {args.branch} (ttl {args.ttl}s)")
    return 0


def cmd_heartbeat(args) -> int:
    with _locked() as d:
        state = _read(d)
        # Only extend claims that are STILL LIVE. Extending an already-expired
        # claim would resurrect it after another agent may have legitimately
        # taken the overlapping area (e.g. a tick that outran the TTL) —
        # recreating the very double-claim the board prevents. Expiry is final;
        # a lapsed claim must be re-acquired via `claim` (which re-runs the
        # conflict check), not silently revived by a heartbeat.
        live_branches = {c.get("branch") for c in _live(state)}
        if args.branch not in live_branches:
            print(
                f"no live claim for branch {args.branch} "
                f"(expired or released — re-run `claim`)",
                file=sys.stderr,
            )
            return 1
        for c in state.get("claims", []):
            if c.get("branch") == args.branch and c.get("status") == "active":
                c["expires_at"] = _iso(_now() + _dt.timedelta(seconds=args.ttl))
        _write(d, state)
        _audit(d, "heartbeat", {"branch": args.branch})
    print(f"HEARTBEAT {args.branch} (+{args.ttl}s)")
    return 0


def cmd_release(args) -> int:
    with _locked() as d:
        state = _read(d)
        before = len(state.get("claims", []))
        state["claims"] = [
            c for c in state.get("claims", []) if c.get("branch") != args.branch
        ]
        _write(d, state)
        _audit(d, "release", {"branch": args.branch, "reason": args.reason})
    print(
        f"RELEASED {args.branch} ({args.reason})"
        if before
        else f"no claim {args.branch}"
    )
    return 0


def cmd_list(args) -> int:
    state, error = _read_observational(_bridge_dir())
    if error is not None:
        print(error, file=sys.stderr)
        return 1
    live = _live(state)
    if args.json:
        print(json.dumps(live, indent=2, sort_keys=True))
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
    with _locked() as d:
        state = _read(d)
        for c in _live(state):
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
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
