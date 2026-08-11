#!/usr/bin/env python3
"""Plain-script selftest for evals.harbor_common (not pytest-collected).

Run with: cd /root/rag-verify && python evals/harbor_common/selftest.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.harbor_common import judge as judge_module  # noqa: E402
from evals.harbor_common.envelope import (  # noqa: E402
    InfrastructureFailure,
    load_inputs,
    run_verifier_main,
)
from evals.harbor_common.judge import run_semantic_judge  # noqa: E402
from evals.harbor_common.serialization import json_safe, utc_now  # noqa: E402


def test_json_safe_nested_with_datetime() -> None:
    naive = datetime(2026, 8, 7, 12, 30, 45)
    aware = datetime(2026, 8, 7, 12, 30, 45, tzinfo=timezone.utc)
    payload = {
        "when": aware,
        "naive": naive,
        "id": UUID("00000000-0000-4000-8000-000000000101"),
        "nested": {"items": [1, "two", None, True, {"deep": aware}]},
        "tuple": (1, 2),
    }
    out = json_safe(payload)
    # Must round-trip through json without a custom encoder.
    json.dumps(out)
    assert out["when"] == "2026-08-07T12:30:45Z", out["when"]
    assert out["naive"] == "2026-08-07T12:30:45Z", out["naive"]
    assert out["id"] == "00000000-0000-4000-8000-000000000101", out["id"]
    assert out["nested"]["items"] == [
        1,
        "two",
        None,
        True,
        {"deep": "2026-08-07T12:30:45Z"},
    ]
    assert out["tuple"] == [1, 2], out["tuple"]
    # Unknown objects degrade to str, never explode.
    assert isinstance(json_safe(object()), str)


def test_utc_now() -> None:
    stamp = utc_now()
    assert stamp.endswith("Z"), stamp
    assert "+00:00" not in stamp, stamp
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_load_inputs_fixture_path(tmp: Path) -> None:
    fixture = tmp / "fixture.json"
    fixture.write_text(
        json.dumps({"evidence": {"a": 1}, "state": {"b": 2}}), encoding="utf-8"
    )
    os.environ["BENCHMARK_CALIBRATION_FIXTURE"] = str(fixture)
    try:
        inputs = load_inputs("/nonexistent/evidence.json")
        assert inputs["evidence"] == {"a": 1}, inputs
        assert inputs["state"] == {"b": 2}, inputs
        assert inputs["input_source"] == str(fixture), inputs

        # state defaults to {} when the fixture omits it
        fixture.write_text(json.dumps({"evidence": {"a": 1}}), encoding="utf-8")
        assert load_inputs("/nonexistent/evidence.json")["state"] == {}

        # missing 'evidence' key is an infrastructure failure
        fixture.write_text(json.dumps({"state": {}}), encoding="utf-8")
        raised = False
        try:
            load_inputs("/nonexistent/evidence.json")
        except InfrastructureFailure:
            raised = True
        assert raised, "missing 'evidence' key must raise InfrastructureFailure"
    finally:
        os.environ.pop("BENCHMARK_CALIBRATION_FIXTURE", None)


def test_load_inputs_live_path(tmp: Path) -> None:
    evidence_path = tmp / "evidence.json"
    evidence_path.write_text(json.dumps({"live": True}), encoding="utf-8")
    inputs = load_inputs(str(evidence_path), live_reader=lambda: {"rows": 3})
    assert inputs == {
        "evidence": {"live": True},
        "state": {"rows": 3},
        "input_source": "live",
    }, inputs
    # no live_reader -> empty state
    assert load_inputs(str(evidence_path))["state"] == {}


def test_run_verifier_main(tmp: Path) -> None:
    report_path = tmp / "reports" / "audit.json"
    os.environ["VERIFIER_REPORT_PATH"] = str(report_path)
    fixture = tmp / "verifier-fixture.json"
    fixture.write_text(
        json.dumps({"evidence": {"e": 1}, "state": {"s": 2}}), encoding="utf-8"
    )
    os.environ["BENCHMARK_CALIBRATION_FIXTURE"] = str(fixture)
    try:
        # pass
        code = run_verifier_main("bench-x", lambda evidence, state: [])
        assert code == 0, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["passed"] is True, report
        assert report["failures"] == [], report
        assert report["benchmark_id"] == "bench-x", report
        assert report["input_source"] == str(fixture), report

        # scoreable failure
        code = run_verifier_main("bench-x", lambda evidence, state: ["boom"])
        assert code == 10, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["passed"] is False and report["failures"] == ["boom"], report

        # report_extra_fn merges into the report and sees both inputs
        code = run_verifier_main(
            "bench-x",
            lambda evidence, state: [],
            report_extra_fn=lambda evidence, state: {"extra": [evidence, state]},
        )
        assert code == 0, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["extra"] == [{"e": 1}, {"s": 2}], report

        # raising gate -> infrastructure error
        def exploding_gate(evidence, state):
            raise RuntimeError("gate exploded")

        code = run_verifier_main("bench-x", exploding_gate)
        assert code == 2, code
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert "verifier_error" in report, report
        assert "gate exploded" in report["verifier_error"], report
        assert "passed" not in report, report
    finally:
        os.environ.pop("VERIFIER_REPORT_PATH", None)
        os.environ.pop("BENCHMARK_CALIBRATION_FIXTURE", None)


class _StubResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubClient:
    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, messages):  # noqa: ANN001 - test stub, signature matches usage
        return _StubResponse(self._content)


class _SequenceStubClient:
    """Returns each queued content once, so a retry sees a different reply."""

    def __init__(self, contents: list[str], calls: list[int]) -> None:
        self._contents = list(contents)
        self._calls = calls

    def invoke(self, messages):  # noqa: ANN001 - test stub, signature matches usage
        self._calls.append(len(messages))
        return _StubResponse(self._contents.pop(0))


class _FakeBadRequest(Exception):
    """Simulates an OpenAI/Azure SDK exception exposing a real status_code,
    the way openai.BadRequestError does -- status-based detection should be
    preferred over substring sniffing."""

    status_code = 400


class _RejectingClient:
    """A client that always rejects, used to simulate a deployment that does
    not support JSON mode."""

    def __init__(self, exc: Exception, calls: list[str]) -> None:
        self._exc = exc
        self._calls = calls

    def invoke(self, messages):  # noqa: ANN001 - test stub, signature matches usage
        self._calls.append("invoke")
        raise self._exc


class _FlakyThenGoodClient:
    """Raises a transport exception N times, then returns good content."""

    def __init__(
        self, exc: Exception, failures: int, content: str, calls: list[str]
    ) -> None:
        self._exc = exc
        self._failures = failures
        self._content = content
        self._calls = calls

    def invoke(self, messages):  # noqa: ANN001 - test stub, signature matches usage
        self._calls.append("invoke")
        if self._failures > 0:
            self._failures -= 1
            raise self._exc
        return _StubResponse(self._content)


class _AlwaysFailingClient:
    def __init__(self, exc: Exception, calls: list[str]) -> None:
        self._exc = exc
        self._calls = calls

    def invoke(self, messages):  # noqa: ANN001 - test stub, signature matches usage
        self._calls.append("invoke")
        raise self._exc


def _json_mode_factory(good_content: str, construction_log: list, invoke_calls: list):
    """A `_client_factory` that opts into the env-path JSON-mode protocol
    (accepts `json_object`) and rejects with a 400 the first time it is
    asked for a JSON-mode client, so the fallback path gets exercised."""

    def factory(*, json_object: bool):
        construction_log.append(json_object)
        if json_object:
            invoke_calls.append("construction-rejected")
            raise _FakeBadRequest("bad request: unknown_parameter")
        return _StubClient(good_content)

    return factory


def test_run_semantic_judge() -> None:
    verdict_json = (
        '{"supported": true, "contradictions": [], '
        '"unsupported_material_claims": [], "reason": "ok"}'
    )
    result = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=lambda: _StubClient(verdict_json),
    )
    assert result["supported"] is True, result

    raised = False
    try:
        run_semantic_judge(
            question="q",
            trusted_sources=["source a"],
            candidate_answer="answer",
            rubric="rubric text",
            _client_factory=lambda: _StubClient("I think it is fine"),
        )
    except InfrastructureFailure:
        raised = True
    assert raised, "malformed (non-JSON) verdict must raise InfrastructureFailure"

    # A single unparseable completion must NOT void the trial: the judge is
    # sampled, so the retry usually parses. Before this, one stray prose reply
    # cost a whole recorded trial as an infrastructure failure.
    calls: list[int] = []
    recovered = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=lambda: _SequenceStubClient(
            ["no json here", verdict_json], calls
        ),
    )
    assert recovered["supported"] is True, recovered
    assert len(calls) == 2, f"expected one retry, got {len(calls)} calls"
    assert calls[1] > calls[0], "retry must append the corrective reminder message"

    # (a) JSON-mode rejection on the first (construction-time) call falls
    # back to prompt-only enforcement and succeeds -- without consuming a
    # parse attempt. Only one real completion (`invoke`) should happen: the
    # rejected client's constructor call doesn't even reach invoke, and the
    # fallback client's single call is the one that produces the verdict.
    construction_log: list = []
    invoke_calls: list = []
    result = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=_json_mode_factory(
            verdict_json, construction_log, invoke_calls
        ),
    )
    assert result["supported"] is True, result
    assert construction_log == [True, False], (
        f"expected json-mode client built and rejected, then rebuilt without "
        f"it, got {construction_log}"
    )
    assert invoke_calls == ["construction-rejected"], (
        "the json-mode client should be rejected at construction time, "
        "before invoke() is ever reachable"
    )

    # (a-variant) rejection surfaces from client.invoke() rather than from
    # construction -- same fallback, same "no parse attempt consumed" rule.
    class _RejectOnInvokeFactory:
        def __init__(self) -> None:
            self.calls: list[bool] = []

        def __call__(self, *, json_object: bool):
            self.calls.append(json_object)
            if json_object:
                return _RejectingClient(
                    _FakeBadRequest("bad request: unknown_parameter"), []
                )
            return _SequenceStubClient([verdict_json], [])

    factory = _RejectOnInvokeFactory()
    result = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=factory,
    )
    assert result["supported"] is True, result
    assert factory.calls == [True, False], factory.calls

    # (b) the wall-clock deadline guard trips -> InfrastructureFailure naming
    # budget exhaustion. Force it deterministically (no real sleeping) by
    # shrinking the module's budget constant below one request_timeout.
    saved_budget = judge_module._JUDGE_BUDGET_SEC
    judge_module._JUDGE_BUDGET_SEC = 1  # less than _JUDGE_REQUEST_TIMEOUT
    try:
        never_called: list = []

        def _factory_never_called():
            never_called.append(1)
            return _StubClient(verdict_json)

        raised = False
        try:
            run_semantic_judge(
                question="q",
                trusted_sources=["source a"],
                candidate_answer="answer",
                rubric="rubric text",
                _client_factory=_factory_never_called,
            )
        except InfrastructureFailure as exc:
            raised = True
            assert "budget" in str(exc).lower(), str(exc)
        assert raised, "shrunken budget must raise InfrastructureFailure"
        assert never_called == [], "budget guard must trip before any client call"
    finally:
        judge_module._JUDGE_BUDGET_SEC = saved_budget

    # (c) a transport exception (unrelated to JSON mode) followed by success
    # recovers, and does not raise.
    calls_c: list = []
    result = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=lambda: _FlakyThenGoodClient(
            ConnectionError("connection reset"), 1, verdict_json, calls_c
        ),
    )
    assert result["supported"] is True, result
    assert len(calls_c) == 2, f"expected one transport retry, got {calls_c}"

    # A transport exception on the final allowed attempt still ends as
    # InfrastructureFailure (not, say, an infinite loop or a misreported
    # "unusable verdict" attempt count).
    calls_final: list = []
    raised = False
    try:
        run_semantic_judge(
            question="q",
            trusted_sources=["source a"],
            candidate_answer="answer",
            rubric="rubric text",
            _client_factory=lambda: _AlwaysFailingClient(
                ConnectionError("connection reset"), calls_final
            ),
        )
    except InfrastructureFailure as exc:
        raised = True
        assert "final attempt" in str(exc), str(exc)
    assert raised, "persistent transport failure must raise InfrastructureFailure"
    assert len(calls_final) == judge_module._MAX_JUDGE_ATTEMPTS, calls_final

    env_vars = (
        "HARBOR_JUDGE_ENDPOINT",
        "HARBOR_JUDGE_API_KEY",
        "HARBOR_JUDGE_MODEL",
        "HARBOR_JUDGE_API_VERSION",
    )
    saved = {name: os.environ.pop(name, None) for name in env_vars}
    for name in env_vars[:-1]:
        os.environ[name] = "x"
    try:
        raised = False
        try:
            run_semantic_judge(
                question="q",
                trusted_sources=["source a"],
                candidate_answer="answer",
                rubric="rubric text",
            )
        except InfrastructureFailure:
            raised = True
        assert raised, "missing HARBOR_JUDGE_* env var must raise InfrastructureFailure"
    finally:
        for name, value in saved.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value


def test_judge_client_disables_reasoning() -> None:
    captured: dict = {}

    class _CapturingAzureChatOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def bind(self, **_kwargs):
            return self

        def invoke(self, _messages):
            return _StubResponse(
                '{"supported": true, "contradictions": [], '
                '"unsupported_material_claims": [], "reason": "ok"}'
            )

    judge_env = {name: "test" for name in judge_module._ENV_VARS}
    with (
        patch.dict(os.environ, judge_env),
        patch("langchain_openai.AzureChatOpenAI", _CapturingAzureChatOpenAI),
    ):
        run_semantic_judge(
            question="q",
            trusted_sources=["source a"],
            candidate_answer="answer",
            rubric="rubric text",
        )

    assert captured["reasoning_effort"] == "none", captured
    assert captured["max_tokens"] == 800, captured


def test_task_judge_inputs() -> None:
    root = Path(__file__).resolve().parents[2]

    def load_verifier(name: str, relative_path: str):
        spec = spec_from_file_location(name, root / relative_path)
        assert spec and spec.loader
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def capture_call(module, evidence: dict) -> dict:
        captured: dict = {}

        def capture(**kwargs):
            captured.update(kwargs)
            return {
                "supported": True,
                "contradictions": [],
                "unsupported_material_claims": [],
                "reason": "ok",
            }

        module.run_semantic_judge = capture
        module.run_judge(evidence)
        return captured

    writing = load_verifier(
        "writing_verify", "evals/agent-writing-flow-v1/tests/verify.py"
    )
    writing_call = capture_call(
        writing,
        {
            "final_assistant_message": {"content": "visible writing answer"},
            "raw_tool_executions": [
                {
                    "tool_name": writing.COMPARE_TOOL,
                    "result": {"comparison": "raw comparison sentinel"},
                }
            ],
        },
    )
    assert writing_call["candidate_answer"] == "visible writing answer", writing_call
    assert "raw comparison sentinel" in json.dumps(
        writing_call["trusted_sources"]
    ), writing_call

    kb = load_verifier("kb_verify", "evals/agent-kb-retrieval-v1/tests/verify.py")
    kb_call = capture_call(
        kb,
        {
            "final_assistant_message": {"content": "visible KB answer"},
            "raw_tool_executions": [
                {
                    "tool_name": kb.RETRIEVE_TOOL,
                    "result": {"chunks": [{"text": "raw chunk sentinel"}]},
                }
            ],
        },
    )
    assert kb_call["candidate_answer"] == "visible KB answer", kb_call
    assert "raw chunk sentinel" in json.dumps(kb_call["trusted_sources"]), kb_call

    kg = load_verifier(
        "kg_verify", "evals/agent-knowledge-graph-flow-v1/tests/verify.py"
    )
    kg_call = capture_call(
        kg,
        {"final_assistant_message": {"content": "visible KG answer"}},
    )
    assert kg_call["candidate_answer"] == "visible KG answer", kg_call
    assert kg_call["trusted_sources"], kg_call


class _ListContentResponse:
    """Simulates langchain-openai>=1.0's list-shaped `AIMessage.content`."""

    def __init__(self, blocks: list[dict]) -> None:
        self.content = blocks


class _ListContentClient:
    def __init__(self, blocks: list[dict]) -> None:
        self._blocks = blocks

    def invoke(self, messages):  # noqa: ANN001 - test stub, signature matches usage
        return _ListContentResponse(self._blocks)


def test_extract_text_from_content_blocks() -> None:
    # str content: unchanged (existing behavior).
    assert judge_module._extract_text(_StubResponse("hello")) == "hello"

    # list-shaped content (langchain-openai>=1.0 AIMessage.content blocks):
    # must be joined from the "text" fields, not str()'d into a repr.
    verdict_json = (
        '{"supported": true, "contradictions": [], '
        '"unsupported_material_claims": [], "reason": "ok"}'
    )
    blocks = [{"type": "text", "text": verdict_json}]
    assert judge_module._extract_text(_ListContentResponse(blocks)) == verdict_json

    result = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=lambda: _ListContentClient(blocks),
    )
    assert result["supported"] is True, result

    # a `.text` attribute/callable, when present, is preferred outright.
    class _WithTextAttr:
        content = [{"type": "text", "text": "ignored"}]
        text = "preferred"

    assert judge_module._extract_text(_WithTextAttr()) == "preferred"

    class _WithTextMethod:
        content = [{"type": "text", "text": "ignored"}]

        def text(self):
            return "preferred-callable"

    assert judge_module._extract_text(_WithTextMethod()) == "preferred-callable"


def test_retry_reminder_includes_offending_reply() -> None:
    # Finding 7: the retry reminder must include a capped snippet of the
    # actual offending reply, since each request is stateless and the model
    # cannot see "your previous reply" without it being restated.
    verdict_json = (
        '{"supported": true, "contradictions": [], '
        '"unsupported_material_claims": [], "reason": "ok"}'
    )
    long_bad_reply = "not json " * 40  # > _RETRY_SNIPPET_MAX_CHARS
    captured: list = []

    class _CapturingClient:
        def __init__(self) -> None:
            self._replies = [long_bad_reply, verdict_json]

        def invoke(self, messages):  # noqa: ANN001
            captured.append([m.content for m in messages])
            return _StubResponse(self._replies.pop(0))

    result = run_semantic_judge(
        question="q",
        trusted_sources=["source a"],
        candidate_answer="answer",
        rubric="rubric text",
        _client_factory=lambda: _CapturingClient(),
    )
    assert result["supported"] is True, result
    assert len(captured) == 2, captured
    retry_message = captured[1][-1]
    assert "previous reply" in retry_message, retry_message
    # The reminder must actually quote (a capped prefix of) the bad reply,
    # not just gesture at it.
    assert long_bad_reply[:50] in retry_message, retry_message
    assert (
        len(retry_message) < len(long_bad_reply) + 400
    ), "reminder must cap the quoted snippet, not embed the full reply"


def main() -> None:
    test_json_safe_nested_with_datetime()
    test_utc_now()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_load_inputs_fixture_path(tmp)
        test_load_inputs_live_path(tmp)
        test_run_verifier_main(tmp)
    test_run_semantic_judge()
    test_judge_client_disables_reasoning()
    test_task_judge_inputs()
    test_extract_text_from_content_blocks()
    test_retry_reminder_includes_offending_reply()
    print("selftest ok")


if __name__ == "__main__":
    main()
