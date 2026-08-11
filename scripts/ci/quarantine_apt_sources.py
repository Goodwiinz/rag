#!/usr/bin/env python3
"""Quarantine apt sources that reference an unrelated package host."""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Sequence
from pathlib import Path

DEFAULT_SOURCES_DIR = Path("/etc/apt/sources.list.d")
DEFAULT_QUARANTINE_DIR = Path("/tmp/playwright-disabled-apt-sources")
DEFAULT_HOST = "packages.microsoft.com"


def quarantine_matching_sources(
    source_dir: Path, quarantine_dir: Path, host: str
) -> list[Path]:
    """Move apt source files containing the host into the quarantine directory."""
    matches = [
        source
        for source in sorted(source_dir.iterdir())
        if source.is_file()
        and host in source.read_text(encoding="utf-8", errors="replace")
    ]
    if not matches:
        return []

    quarantine_dir.mkdir(parents=True, exist_ok=True)
    for source in matches:
        target = quarantine_dir / source.name
        shutil.move(str(source), str(target))
        print(f"Quarantined apt source: {source} -> {target}")
    return matches


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-dir", type=Path, default=DEFAULT_SOURCES_DIR)
    parser.add_argument("--quarantine-dir", type=Path, default=DEFAULT_QUARANTINE_DIR)
    parser.add_argument("--host", default=DEFAULT_HOST)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    quarantine_matching_sources(args.sources_dir, args.quarantine_dir, args.host)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
