#!/usr/bin/env python3
"""Operate the Git-backed NOUS coordination claim board."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.nous.backend_git import GitBackend, GitBackendConfig
from scripts.nous.backend_local import (
    LocalBackend,
    remove_remote_required_sentinel,
    write_remote_required_sentinel,
)
from scripts.nous.coordination import (
    BackendUnavailable,
    Claim,
    ClaimLost,
    CombinedBackend,
    Conflict,
    ValidationError,
)
from scripts.nous.gitio import GitIO
from scripts.nous.preflight import RuntimeConfig, load_runtime_config
from scripts.nous.schema import SchemaError, validate_agent, validate_run_id

DEFAULT_TTL_SECONDS = 10_800


def _files(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _claim_json(claim: Claim) -> dict[str, object]:
    return {
        "claim_id": claim.claim_id,
        "run_id": claim.run_id,
        "agent": claim.agent,
        "machine_id": claim.machine_id,
        "branch": claim.branch,
        "area": claim.area,
        "files": list(claim.files),
        "expires_at": claim.expires_at,
        "renewed_at": claim.renewed_at,
    }


def _require_coordinate(args: argparse.Namespace) -> None:
    if "coordinate" not in (args.authorize or []):
        raise ValidationError(
            SchemaError("coordinate authorization is required"),
            message="coordinate authorization is required",
        )


def _run_id(agent: str) -> str:
    slug = "-".join(
        filter(None, (part.lower() for part in agent.replace("_", "-").split("-")))
    )
    slug = "".join(
        character for character in slug if character.isalnum() or character == "-"
    )[:32]
    slug = slug or "agent"
    value = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        + slug
        + "-"
        + secrets.token_hex(3)
    )
    return validate_run_id(value)


def _config(repo_root: Path) -> RuntimeConfig:
    return load_runtime_config(os.environ, repo_root=repo_root)


def _remote(config: RuntimeConfig, repo_root: Path) -> GitBackend:
    return GitBackend(
        GitBackendConfig(
            remote=config.git_remote,
            branch=config.coordination_branch,
            mode="remote-required",
            machine_id=config.machine_id,
            repo_slug=config.github_repository,
        ),
        GitIO(repo_root),
    )


def _record_held_in_error(receipt_root: Path, claim: Claim) -> None:
    """Persist and report the fencing values needed to release a stranded claim."""

    run_dir = receipt_root / claim.run_id
    receipt = run_dir / "held-in-error.json"
    recovery: dict[str, object] = {
        "state": "held-in-error",
        "run_id": claim.run_id,
        "claim_id": claim.claim_id,
        "receipt": str(receipt),
    }
    record = recovery | {
        "schema": 1,
        "agent": claim.agent,
        "machine_id": claim.machine_id,
        "branch": claim.branch,
        "area": claim.area,
        "expires_at": claim.expires_at,
    }
    temp = run_dir / f"held-in-error.{secrets.token_hex(6)}.tmp"
    try:
        missing = []
        directory = run_dir
        while not directory.exists():
            missing.append(directory)
            directory = directory.parent
        for directory in reversed(missing):
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                pass
            parent = os.open(directory.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, receipt)
        directory_descriptor = os.open(run_dir, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError:
        recovery["receipt"] = None
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    print(json.dumps(recovery, sort_keys=True), file=sys.stderr)


def _combined(config: RuntimeConfig, repo_root: Path) -> CombinedBackend:
    if config.coord_mode != "remote-required":
        raise ValidationError(
            SchemaError("remote-required mode is not enabled"),
            message="set NOUS_COORD_MODE=remote-required for Git coordination",
        )
    if config.loop_bridge_dir is None:
        raise ValidationError(
            SchemaError("LOOP_BRIDGE_DIR is required"),
            message="LOOP_BRIDGE_DIR is required for the same-host mutex",
        )
    return CombinedBackend(
        _remote(config, repo_root),
        LocalBackend(config.loop_bridge_dir),
        on_compensation_pending=lambda claim: _record_held_in_error(
            config.receipt_dir, claim
        ),
    )


def _base_sha(config: RuntimeConfig, repo_root: Path) -> str:
    io = GitIO(repo_root)
    temp_ref = f"refs/nous/tmp/develop-{secrets.token_hex(6)}"
    try:
        base = io.fetch_branch(config.git_remote, "develop", temp_ref)
        assert base is not None
        return base
    finally:
        io.delete_local_ref(temp_ref)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nous_run.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument(
        "--mode", choices=("remote-required",), default="remote-required"
    )
    bootstrap.add_argument("--authorize", action="append")

    cutover = commands.add_parser("cutover")
    cutover.add_argument("--write-sentinel", action="store_true", required=True)
    cutover.add_argument("--authorize", action="append")

    rollback = commands.add_parser("rollback")
    rollback.add_argument("--remove-sentinel", action="store_true", required=True)
    rollback.add_argument("--authorize", action="append")

    claim = commands.add_parser("claim")
    claim.add_argument("--agent", required=True)
    claim.add_argument("--branch", required=True)
    claim.add_argument("--area", required=True)
    claim.add_argument("--files")
    claim.add_argument("--run-id")
    claim.add_argument("--claim-id")
    claim.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    claim.add_argument("--authorize", action="append")

    renew = commands.add_parser("renew")
    renew.add_argument("--run-id", required=True)
    renew.add_argument("--claim-id", required=True)
    renew.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    renew.add_argument("--authorize", action="append")

    release = commands.add_parser("release")
    release.add_argument("--run-id", required=True)
    release.add_argument("--claim-id", required=True)
    release.add_argument("--reason", default="done")
    release.add_argument("--remove-run", action="store_true")
    release.add_argument("--authorize", action="append")

    listing = commands.add_parser("list")
    listing.add_argument("--json", action="store_true")

    check = commands.add_parser("check")
    check.add_argument("--area", required=True)
    check.add_argument("--files")
    check.add_argument("--json", action="store_true")
    return parser


def _dispatch(args: argparse.Namespace, repo_root: Path) -> int:
    config = _config(repo_root)
    if args.command == "bootstrap":
        _require_coordinate(args)
        tip = _remote(config, repo_root).bootstrap(mode=args.mode)
        print(
            json.dumps(
                {"branch": config.coordination_branch, "tip": tip}, sort_keys=True
            )
        )
        return 0
    if args.command == "cutover":
        _require_coordinate(args)
        if config.loop_bridge_dir is None:
            raise BackendUnavailable("LOOP_BRIDGE_DIR is required for cutover")
        _remote(config, repo_root).list()
        sentinel = write_remote_required_sentinel(config.loop_bridge_dir)
        print(json.dumps({"sentinel": str(sentinel)}, sort_keys=True))
        return 0
    if args.command == "rollback":
        _require_coordinate(args)
        if config.coord_mode != "local":
            raise ValidationError(
                SchemaError("rollback requires local mode"),
                message="set NOUS_COORD_MODE=local before removing the sentinel",
            )
        if config.loop_bridge_dir is None:
            raise BackendUnavailable("LOOP_BRIDGE_DIR is required for rollback")
        removed = remove_remote_required_sentinel(config.loop_bridge_dir)
        print(json.dumps({"sentinel_removed": removed}, sort_keys=True))
        return 0

    backend = _combined(config, repo_root)
    if args.command == "claim":
        _require_coordinate(args)
        agent = validate_agent(args.agent)
        base = _base_sha(config, repo_root)
        claim = backend.claim(
            run_id=args.run_id or _run_id(agent),
            agent=agent,
            machine_id=config.machine_id,
            branch=args.branch,
            area=args.area,
            files=_files(args.files),
            candidate=None,
            pr=None,
            ttl_seconds=args.ttl,
            claim_id=args.claim_id,
            base_sha=base,
            evidence_head_sha=base,
        )
        print(json.dumps(_claim_json(claim), sort_keys=True))
        return 0
    if args.command == "renew":
        _require_coordinate(args)
        claim = backend.renew(
            run_id=args.run_id, claim_id=args.claim_id, ttl_seconds=args.ttl
        )
        print(json.dumps(_claim_json(claim), sort_keys=True))
        return 0
    if args.command == "release":
        _require_coordinate(args)
        backend.release(
            run_id=args.run_id,
            claim_id=args.claim_id,
            reason=args.reason,
            remove_run=args.remove_run,
        )
        print(json.dumps({"released": args.run_id}, sort_keys=True))
        return 0
    if args.command == "list":
        view = backend.view()
        payload = {
            "remote": [_claim_json(item) for item in view.remote],
            "local": list(view.local),
        }
        print(json.dumps(payload, indent=2 if args.json else None, sort_keys=True))
        return 0
    if args.command == "check":
        remote = backend.check(area=args.area, files=_files(args.files))
        local = backend.local.check_legacy(args.area, _files(args.files))
        payload = {
            "clear": not remote and not local,
            "remote": [_claim_json(item) for item in remote],
            "local": local,
        }
        print(json.dumps(payload, indent=2 if args.json else None, sort_keys=True))
        return 0 if payload["clear"] else 2
    raise RuntimeError("unknown command")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return _dispatch(args, repo_root)
    except (Conflict, ClaimLost) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except BackendUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except SchemaError:
        print("coordination validation failed", file=sys.stderr)
        return 4
    except Exception:
        print("NOUS coordination command failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
