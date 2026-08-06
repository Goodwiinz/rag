from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from src.cli.types import CLIEvent


def parse_sse_lines(lines: Iterable[str]) -> Iterator[CLIEvent]:
    event_type = ""
    payload_parts: list[str] = []

    def flush() -> Iterator[CLIEvent]:
        nonlocal event_type, payload_parts
        if event_type and payload_parts:
            yield CLIEvent(type=event_type, data=json.loads("\n".join(payload_parts)))
        event_type = ""
        payload_parts = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line:
            yield from flush()
            continue

        if line.startswith("event:"):
            event_type = line[6:].strip()
            continue

        if line.startswith("data:"):
            payload_parts.append(line[5:].lstrip())

    yield from flush()

