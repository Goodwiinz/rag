from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO


def _expand(repo: Path, patterns: list[str]) -> set[str]:
    matched: set[str] = set()
    for pattern in patterns:
        hits = sorted(
            str(p.relative_to(repo)) for p in repo.glob(pattern) if p.is_file()
        )
        if not hits:
            print(f"error: pattern matched no files: {pattern}", file=sys.stderr)
            raise SystemExit(2)
        matched.update(hits)
    return matched


def _load(path: Path) -> dict[str, list[dict[str, object]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    scopes = data.get("scopes")
    if not isinstance(scopes, list) or not scopes:
        raise SystemExit("error: partition.json must contain a non-empty 'scopes' list")
    return {"scopes": scopes}


def _patterns(raw: dict[str, object], key: str) -> list[str]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise SystemExit(f"error: scope field '{key}' must be a list")
    return [str(p) for p in value]


def check(partition_path: Path, repo: Path) -> int:
    data = _load(partition_path)
    owners: dict[str, list[str]] = {}
    contracts: dict[str, list[str]] = {}
    empty_scopes: list[str] = []

    for raw in data["scopes"]:
        name = str(raw.get("name", "<unnamed>"))
        own_patterns = _patterns(raw, "own")
        contract_patterns = _patterns(raw, "contract_files")
        owned = _expand(repo, own_patterns)
        if not owned:
            empty_scopes.append(name)
        for f in owned:
            owners.setdefault(f, []).append(name)
        for f in _expand(repo, contract_patterns):
            contracts.setdefault(f, []).append(name)

    overlaps = {f: names for f, names in owners.items() if len(names) > 1}
    rc = 0

    if overlaps:
        rc = 1
        print(f"FAIL: {len(overlaps)} file(s) claimed by multiple owners:")
        for f in sorted(overlaps):
            print(f"  {f}: {', '.join(overlaps[f])}")
    else:
        print(
            f"OK: {len(owners)} files, no overlap across {len(data['scopes'])} scopes"
        )

    if empty_scopes:
        rc = max(rc, 1)
        print(f"WARN: scope(s) with zero owned files: {', '.join(empty_scopes)}")

    shared_contracts = {f: n for f, n in contracts.items() if len(n) > 1}
    if shared_contracts:
        print(f"contracts shared across scopes ({len(shared_contracts)}):")
        for f in sorted(shared_contracts):
            print(f"  {f}: {', '.join(shared_contracts[f])}")

    print("\nownership summary:")
    per_scope: dict[str, int] = {}
    for f, names in owners.items():
        per_scope[names[0]] = per_scope.get(names[0], 0) + 1
    for scope in (str(s.get("name", "<unnamed>")) for s in data["scopes"]):
        print(f"  {scope}: {per_scope.get(scope, 0)} files")

    total_bytes = sum((repo / f).stat().st_size for f in owners)
    print(f"\ntotal owned bytes: {total_bytes}")
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate non-overlapping audit scope ownership."
    )
    parser.add_argument("partition", type=Path, help="partition.json path")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repo root")
    args = parser.parse_args(argv)
    out: TextIO = sys.stdout
    rc = check(args.partition, args.repo.resolve())
    out.flush()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
