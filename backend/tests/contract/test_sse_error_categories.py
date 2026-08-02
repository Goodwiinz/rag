"""Contract test for the SSE ``error`` frame's server-authored ``category`` (W2).

An ``error`` frame is flat: ``{"error": "<safe string>", "category": "<label>"}``
with ``schema_version`` unchanged at ``"1.0"``. ``error`` stays a STRING — the
category is a *sibling* key, because turning ``error`` into an object would break
every deployed consumer.

Two guarantees are pinned here:

1. The frozen category wire values (``AgentErrorCategory``), in order. Renaming
   one is a breaking change for the frontend mirror in
   ``frontend/src/services/agentStreamEvents.ts``.
2. Every ``AgentStreamEvent.ERROR`` emit in ``api/agent/streaming.py`` builds its
   payload through ``error_frame_payload(...)`` (or passes an explicit
   ``AgentErrorCategory`` member). A future bare ``{"error": ...}`` emit fails
   here — that is the whole point, and ``test_the_ast_guard_actually_catches_a_
   violation`` proves the check has teeth against a synthetic offender.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

import pytest

from src.shared.enums import AgentErrorCategory

# backend/tests/contract/<this file> -> parents[2] == backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_STREAMING_PY = _BACKEND_ROOT / "src" / "api" / "agent" / "streaming.py"

_PAYLOAD_BUILDER = "error_frame_payload"
_ENUM_NAME = "AgentErrorCategory"
_ENUM_MEMBER_NAMES = frozenset(AgentErrorCategory.__members__)

# The frozen wire contract. Changing any of these strings breaks every client
# that branches on the category; this ordered list is the deliberate tripwire.
_EXPECTED_CATEGORY_VALUES = [
    "upstream_timeout",
    "model_error",
    "tool_error",
    "checkpoint_unavailable",
    "rate_limited",
    "cancelled",
    "invalid_request",
    "conflict",
    "internal",
]


def _is_error_event_arg(arg: ast.expr) -> bool:
    """True when *arg* names the ``error`` SSE event (enum member or literal)."""
    if isinstance(arg, ast.Constant) and arg.value == "error":
        return True
    return (
        isinstance(arg, ast.Attribute)
        and isinstance(arg.value, ast.Name)
        and arg.value.id == "AgentStreamEvent"
        and arg.attr == "ERROR"
    )


def _mentions_category_enum(node: ast.expr) -> bool:
    """True when *node* contains an ``AgentErrorCategory.<MEMBER>`` reference."""
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Name)
            and sub.value.id == _ENUM_NAME
            and sub.attr in _ENUM_MEMBER_NAMES
        ):
            return True
    return False


def _collect_error_emit_offenders(source: str) -> Tuple[int, List[str]]:
    """Return ``(error-emit count, offender descriptions)`` for *source*.

    An ``AgentStreamEvent.ERROR`` emit is compliant when its payload argument is
    a call to ``error_frame_payload(...)``. Anything else — a dict display, a
    name, a helper that forgot the category — is an offender, because only the
    single builder can guarantee the key names and the presence of ``category``.
    A payload that is not an ``error_frame_payload`` call is tolerated ONLY if it
    is a dict literal that both carries an ``"error"`` key and references an
    ``AgentErrorCategory`` member (the explicit-category escape hatch).
    """
    tree = ast.parse(source)
    offenders: List[str] = []
    count = 0

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "emit"
            and node.args
            and _is_error_event_arg(node.args[0])
        ):
            continue
        count += 1
        if len(node.args) < 2:
            offenders.append(f"L{node.lineno}: error emit with no payload argument")
            continue
        payload = node.args[1]
        if (
            isinstance(payload, ast.Call)
            and isinstance(payload.func, ast.Name)
            and payload.func.id == _PAYLOAD_BUILDER
        ):
            continue
        if isinstance(payload, ast.Dict) and _mentions_category_enum(payload):
            keys = {
                k.value
                for k in payload.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            if "error" in keys and "category" in keys:
                continue
            offenders.append(
                f"L{node.lineno}: error-frame dict literal is missing "
                f"'error'/'category' (has {sorted(keys)})"
            )
            continue
        offenders.append(
            f"L{node.lineno}: error frame payload does not come from "
            f"{_PAYLOAD_BUILDER}() and carries no explicit {_ENUM_NAME} member "
            f"({type(payload).__name__})"
        )
    return count, offenders


@pytest.fixture(scope="module")
def _streaming_error_emits() -> Tuple[int, List[str]]:
    assert _STREAMING_PY.is_file(), f"cannot locate streaming.py at {_STREAMING_PY}"
    return _collect_error_emit_offenders(_STREAMING_PY.read_text())


@pytest.mark.unit
def test_enum_pins_the_frozen_category_wire_values() -> None:
    """The category strings are the wire contract — a rename must trip CI."""
    assert [c.value for c in AgentErrorCategory] == _EXPECTED_CATEGORY_VALUES


@pytest.mark.unit
def test_every_error_emit_builds_its_payload_through_the_single_builder(
    _streaming_error_emits: Tuple[int, List[str]],
) -> None:
    count, offenders = _streaming_error_emits
    assert count > 0, "no AgentStreamEvent.ERROR emit sites found — test is blind"
    assert not offenders, (
        "streaming.py emits error frames without a server-authored category:\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_the_ast_guard_actually_catches_a_violation() -> None:
    """Self-test: a bare ``{"error": ...}`` emit MUST be reported. Without this
    the guard above could pass by never matching anything."""
    violating = (
        "async def f():\n"
        "    await emitter.emit(AgentStreamEvent.ERROR, {'error': 'boom'})\n"
    )
    count, offenders = _collect_error_emit_offenders(violating)
    assert count == 1
    assert len(offenders) == 1 and "L2" in offenders[0]

    # ...and the two compliant shapes must NOT be reported.
    compliant_builder = (
        "async def f():\n"
        "    await emitter.emit(AgentStreamEvent.ERROR, error_frame_payload(e))\n"
    )
    assert _collect_error_emit_offenders(compliant_builder) == (1, [])

    compliant_explicit = (
        "async def f():\n"
        "    await emitter.emit(\n"
        "        AgentStreamEvent.ERROR,\n"
        "        {'error': 'x', 'category': AgentErrorCategory.CONFLICT.value},\n"
        "    )\n"
    )
    assert _collect_error_emit_offenders(compliant_explicit) == (1, [])

    # A dict that name-drops the enum but omits the key is still a violation.
    sneaky = (
        "async def f():\n"
        "    await emitter.emit(\n"
        "        AgentStreamEvent.ERROR,\n"
        "        {'error': AgentErrorCategory.CONFLICT.value},\n"
        "    )\n"
    )
    sneaky_count, sneaky_offenders = _collect_error_emit_offenders(sneaky)
    assert sneaky_count == 1 and len(sneaky_offenders) == 1


@pytest.mark.unit
def test_confirm_not_found_branches_cannot_oracle_thread_existence() -> None:
    """Anti-enumeration: /stream/confirm's not-found and ownership-mismatch
    branches must build their frame from the SAME two module constants, so the
    payloads are byte-identical and neither leaks whether the thread exists."""
    source = _STREAMING_PY.read_text()
    assert source.count("_CONFIRM_NOT_FOUND_MESSAGE") == 3, (
        "expected one definition + exactly two uses of _CONFIRM_NOT_FOUND_MESSAGE "
        "(not-found and ownership-mismatch branches)"
    )
    assert source.count("_CONFIRM_NOT_FOUND_CATEGORY") == 3
    assert '"Thread not found"' in source
