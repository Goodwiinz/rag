"""Host-side Harbor adapter for production-shaped NOUS benchmark tasks.

Each task image owns a ``/benchmark/run_agent.py`` entrypoint.  This adapter
only passes the approved instruction into that entrypoint, captures its logs,
and exposes token/metadata summaries to Harbor.  It deliberately does not
rewrite prompts, routes, tool arguments, or model output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class NousProductionAgent(BaseAgent):
    """Execute the task-owned production adapter inside the Harbor container."""

    SUPPORTS_ATIF = True

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        extra_env: dict[str, str] | None = None,
        runner_path: str = "/benchmark/run_agent.py",
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._extra_env = dict(extra_env or {})
        self._runner_path = runner_path

    @staticmethod
    def name() -> str:
        return "nous-production-agent"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec(
            command=f"test -f {self._runner_path} && python --version",
            timeout_sec=30,
        )
        if result.return_code != 0:
            raise RuntimeError(
                f"NOUS benchmark runner is unavailable at {self._runner_path}"
            )

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        result = await environment.exec(
            command=f"python {self._runner_path}",
            env={"HARBOR_INSTRUCTION": instruction, **self._extra_env},
        )

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "adapter-stdout.txt").write_text(result.stdout or "")
        (self.logs_dir / "adapter-stderr.txt").write_text(result.stderr or "")
        (self.logs_dir / "adapter-exit-code.txt").write_text(str(result.return_code))

        evidence_path = self.logs_dir / "evidence.json"
        if evidence_path.exists():
            try:
                evidence = json.loads(evidence_path.read_text())
            except (OSError, json.JSONDecodeError):
                evidence = {}
            usage = evidence.get("model_usage") or {}
            context.n_input_tokens = _optional_int(usage.get("input_tokens"))
            context.n_output_tokens = _optional_int(usage.get("output_tokens"))
            context.n_cache_tokens = _optional_int(usage.get("cache_tokens"))
            context.metadata = {
                "benchmark_id": evidence.get("benchmark_id"),
                "source_revision": evidence.get("source_revision"),
                "termination_reason": evidence.get("termination_reason"),
                "evidence_schema": evidence.get("schema_version"),
            }

        if result.return_code != 0:
            raise RuntimeError(
                "NOUS production adapter failed before producing a scoreable outcome; "
                f"exit_code={result.return_code}. See adapter logs."
            )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
