from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CLIEvent:
    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class CLISessionState:
    thread_id: str = ""
    cli_session_id: str = ""
    debug: bool = False
    page_context: dict[str, Any] = field(
        default_factory=lambda: {"type": "unknown"}
    )
    latest_trace: dict[str, Any] = field(default_factory=dict)
    should_quit: bool = False
    model: str = ""
