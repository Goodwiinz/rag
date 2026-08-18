from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "writing_flow_verify", TESTS_DIR / "verify.py"
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def test_semantic_judge_does_not_trust_model_authored_tool_args(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_judge(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"supported": True, "contradictions": []}

    monkeypatch.setattr(VERIFY, "run_semantic_judge", fake_judge)
    evidence = {
        "raw_tool_executions": [
            {
                "tool_name": VERIFY.COMPARE_TOOL,
                "status": "completed",
                "args": {"invented_claim": "The model says this is true"},
                "result": {"comparison": "Result returned by the tool"},
            }
        ],
        "final_assistant_message": {"content": "candidate"},
    }

    VERIFY.run_judge(evidence)

    workflow = captured["trusted_sources"][-1]["successful_workflow_tool_executions"]
    assert workflow == [
        {
            "tool": VERIFY.COMPARE_TOOL,
            "result": {"comparison": "Result returned by the tool"},
        }
    ]
