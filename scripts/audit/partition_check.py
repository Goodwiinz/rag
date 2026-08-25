from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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


def _load(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("error: partition.json must contain an object")

    raw_scopes = data.get("scopes")
    if not isinstance(raw_scopes, list) or not raw_scopes:
        raise SystemExit("error: partition.json must contain a non-empty 'scopes' list")
    scopes: list[dict[str, object]] = []
    for raw in raw_scopes:
        if not isinstance(raw, dict):
            raise SystemExit("error: every scope must be an object")
        scopes.append(raw)

    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise SystemExit("error: partition.json must contain a non-empty 'files' list")
    return scopes, [str(pattern) for pattern in files]


def _patterns(raw: dict[str, object], key: str) -> list[str]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise SystemExit(f"error: scope field '{key}' must be a list")
    return [str(p) for p in value]


def check(partition_path: Path, repo: Path) -> int:
    scopes, file_patterns = _load(partition_path)
    scoped_files = _expand(repo, file_patterns)
    owners: dict[str, list[str]] = {}
    contracts: dict[str, list[str]] = {}
    empty_scopes: list[str] = []

    for raw in scopes:
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
    missing_owners = scoped_files - owners.keys()
    out_of_scope = owners.keys() - scoped_files
    unowned_contracts = contracts.keys() - owners.keys()
    rc = 0

    if overlaps:
        rc = 1
        print(f"FAIL: {len(overlaps)} file(s) claimed by multiple owners:")
        for f in sorted(overlaps):
            print(f"  {f}: {', '.join(overlaps[f])}")
    if missing_owners:
        rc = 1
        print(f"FAIL: {len(missing_owners)} scoped file(s) have no owner:")
        for f in sorted(missing_owners):
            print(f"  {f}")

    if out_of_scope:
        rc = 1
        print(
            f"FAIL: {len(out_of_scope)} owned file(s) are outside the scoped manifest:"
        )
        for f in sorted(out_of_scope):
            print(f"  {f}")

    if unowned_contracts:
        rc = 1
        print(f"FAIL: {len(unowned_contracts)} contract file(s) have no owner:")
        for f in sorted(unowned_contracts):
            print(f"  {f}")

    if empty_scopes:
        rc = 1
        print(f"FAIL: scope(s) with zero owned files: {', '.join(empty_scopes)}")

    if rc == 0:
        print(
            f"OK: {len(owners)} scoped files, complete non-overlapping ownership "
            f"across {len(scopes)} scopes"
        )

    shared_contracts = {f: n for f, n in contracts.items() if len(n) > 1}
    if shared_contracts:
        print(f"contracts shared across scopes ({len(shared_contracts)}):")
        for f in sorted(shared_contracts):
            print(f"  {f}: {', '.join(shared_contracts[f])}")

    print("\nownership summary:")
    per_scope: dict[str, int] = {}
    for f, names in owners.items():
        per_scope[names[0]] = per_scope.get(names[0], 0) + 1
    for scope in (str(s.get("name", "<unnamed>")) for s in scopes):
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
    return check(args.partition, args.repo.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
