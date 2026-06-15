"""Record golden-case replay cassettes from a LIVE agent run (B2, Phase 2).

For each ``GoldenCase`` in ``LOCAL_CASES`` this runs the real agent graph
against the live model + infra, captures every LLM decision (structured
outputs, tool-call messages, plain text) in call order via a transparent
recording proxy installed at the same six seams the replay fixture patches,
and writes ``cassettes/<case.name>.json`` (the format ``_replay_llm`` reads).

ANTI-MASKING (mandatory): a cassette is written ONLY if the live run's
``intent``/``tool_calls`` satisfy the committed ``expected_intent`` /
``expected_tools``. A live decision that violates the golden expectation is
REFUSED — recording is live validation, not blind capture, so a re-record
cannot silently absorb a regression introduced in the same change.

Usage (needs live creds + infra, run locally or on the creds-bearing runner):

    AZURE_OPENAI_CHAT_API_KEY=... AZURE_OPENAI_CHAT_ENDPOINT=... \\
    python -m tests.eval.record_golden_cassette            # all cases
    python -m tests.eval.record_golden_cassette greeting_hi writing_summarize
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

CASSETTE_DIR = Path(__file__).with_name("cassettes")


def _content_str(content: Any) -> Any:
    """Keep str content as-is; pass through list (multimodal) blocks."""
    return content


class _RecStructured:
    def __init__(self, real_chain: Any, sink: list, schema_name: str):
        self._real = real_chain
        self._sink = sink
        self._schema = schema_name

    def _record(self, res: Any) -> Any:
        payload = res.model_dump() if hasattr(res, "model_dump") else dict(res)
        self._sink.append(
            {"slot": len(self._sink), "kind": "structured",
             "schema": self._schema, "payload": payload}
        )
        return res

    async def ainvoke(self, messages: Any, *a: Any, **k: Any) -> Any:
        return self._record(await self._real.ainvoke(messages, *a, **k))

    def invoke(self, messages: Any, *a: Any, **k: Any) -> Any:
        return self._record(self._real.invoke(messages, *a, **k))


class _RecTools:
    def __init__(self, real_bound: Any, sink: list):
        self._real = real_bound
        self._sink = sink

    def _record(self, msg: Any) -> Any:
        tcs = []
        for tc in getattr(msg, "tool_calls", None) or []:
            tcs.append({"name": tc.get("name"), "args": tc.get("args", {}),
                        "id": tc.get("id", "")})
        self._sink.append(
            {"slot": len(self._sink), "kind": "tool",
             "message": {"content": _content_str(msg.content), "tool_calls": tcs}}
        )
        return msg

    async def ainvoke(self, messages: Any, *a: Any, **k: Any) -> Any:
        return self._record(await self._real.ainvoke(messages, *a, **k))

    def invoke(self, messages: Any, *a: Any, **k: Any) -> Any:
        return self._record(self._real.invoke(messages, *a, **k))


class RecordingChatModel:
    """Transparent proxy that records every decision of the wrapped real model."""

    def __init__(self, real: Any, sink: list):
        self._real = real
        self._sink = sink

    def with_structured_output(self, schema: Any, **kw: Any) -> _RecStructured:
        return _RecStructured(self._real.with_structured_output(schema, **kw), self._sink, schema.__name__)

    def bind_tools(self, tools: Any = None, **kw: Any) -> _RecTools:
        return _RecTools(self._real.bind_tools(tools, **kw), self._sink)

    def _record_text(self, msg: Any) -> Any:
        self._sink.append(
            {"slot": len(self._sink), "kind": "text",
             "message": {"content": _content_str(msg.content), "tool_calls": []}}
        )
        return msg

    async def ainvoke(self, messages: Any, *a: Any, **k: Any) -> Any:
        return self._record_text(await self._real.ainvoke(messages, *a, **k))

    def invoke(self, messages: Any, *a: Any, **k: Any) -> Any:
        return self._record_text(self._real.invoke(messages, *a, **k))

    def __getattr__(self, name: str) -> Any:  # passthrough for anything else
        return getattr(self._real, name)


def _install_recorder(sink: list):
    """Patch the six seams to wrap the real builders' output; return a restore fn."""
    from src.services.agent import (
        classifier, compactor, graph, llm_factory, planner, reflection,
    )

    # Reset every build + result cache so the recorder is actually constructed.
    llm_factory.reset_llm_caches()
    graph._LLM_CACHE.clear()
    classifier._CLASSIFIER_LLM = None
    reflection._REFLECTION_LLM = None
    compactor._COMPACTOR_LLM = None

    targets = [
        (llm_factory, "build_lightweight_llm"),
        (llm_factory, "build_synthesis_llm"),
        (graph, "_build_llm"),
        (reflection, "build_lightweight_llm"),
        (planner, "build_lightweight_llm"),
        (compactor, "build_lightweight_llm"),
    ]
    originals = [(m, n, getattr(m, n)) for m, n in targets]

    def make_wrapper(orig):
        def wrapper(*a: Any, **k: Any):
            return RecordingChatModel(orig(*a, **k), sink)
        return wrapper

    for module, name, orig in originals:
        setattr(module, name, make_wrapper(orig))

    def restore():
        for module, name, orig in originals:
            setattr(module, name, orig)

    return restore


async def record_case(case: Any) -> tuple[bool, str]:
    """Run one case live, validate against expectations, write cassette if OK."""
    from tests.eval.test_agent_regression import (
        _run_agent, intent_match, tool_subset_match,
    )

    sink: list = []
    restore = _install_recorder(sink)
    try:
        inputs: dict[str, Any] = {"page_context": case.page_context}
        if case.messages:
            inputs["messages"] = list(case.messages)
        else:
            inputs["question"] = case.question
        outputs = await _run_agent(inputs)
    finally:
        restore()

    # Anti-masking: refuse to write a cassette that violates the golden contract.
    im = intent_match(outputs, {"intent": case.expected_intent})
    tm = tool_subset_match(outputs, {"expected_tools": case.expected_tools})
    if im["score"] != 1 or tm["score"] != 1:
        return False, (
            f"REFUSED {case.name}: live decision violates expectation "
            f"(intent={outputs.get('intent')!r} vs {case.expected_intent!r}, "
            f"tools={outputs.get('tool_calls')} vs {list(case.expected_tools)})"
        )

    CASSETTE_DIR.mkdir(exist_ok=True)
    data = {
        "case": case.name,
        "expected_intent": case.expected_intent,
        "expected_tools": list(case.expected_tools),
        "calls": sink,
    }
    (CASSETTE_DIR / f"{case.name}.json").write_text(json.dumps(data, indent=2, default=str) + "\n")
    return True, f"  + {case.name} ({len(sink)} call(s))"


async def _main(names: list[str]) -> int:
    from tests.eval.golden_examples import LOCAL_CASES

    cases = [c for c in LOCAL_CASES if not names or c.name in names]
    written = refused = 0
    for case in cases:
        try:
            ok, msg = await record_case(case)
        except Exception as e:  # noqa: BLE001 - report and continue
            ok, msg = False, f"  ! {case.name} ERROR: {type(e).__name__}: {e}"
        print(msg)
        written += ok
        refused += not ok
    print(f"\nDone. written={written} refused/error={refused} of {len(cases)}")
    return 1 if refused else 0


def main() -> None:
    sys.exit(asyncio.run(_main(sys.argv[1:])))


if __name__ == "__main__":
    main()
