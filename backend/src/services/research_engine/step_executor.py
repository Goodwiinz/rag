"""Step executor for research engine workflow steps."""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument
from src.services.research_engine.providers.base import LLMProvider, LLMRequest, LLMResponse
from src.services.research_engine.verification import QualityMark


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    output: Dict[str, Any]
    sources_used: List[SourceDocument] = field(default_factory=list)
    quality_marks: List[QualityMark] = field(default_factory=list)
    token_count: int = 0
    inputs_hash: Optional[str] = None
    outputs_hash: Optional[str] = None
    full_prompt: Optional[str] = None


class StepExecutor:
    """Dispatches and executes individual workflow steps."""

    def __init__(
        self,
        connectors: Dict[str, SourceConnector],
        providers: Dict[str, LLMProvider],
    ) -> None:
        self.connectors = connectors
        self.providers = providers
        self._handlers = {
            "search": self._execute_search,
            "screen": self._execute_screen,
            "extract": self._execute_extract,
            "synthesize": self._execute_synthesize,
            "export": self._execute_export,
            "verify": self._execute_verify,
        }

    async def execute(self, step_def: Dict, context: Dict) -> StepResult:
        """Execute a step based on its type, dispatching to the appropriate handler."""
        step_type = step_def.get("type", "")
        handler = self._handlers.get(step_type)
        if handler is None:
            raise ValueError(f"Unknown step type: {step_type}")
        return await handler(step_def, context)

    async def _execute_search(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        """Search across configured source connectors."""
        params = step_def.get("params", {})
        sources = params.get("sources", [])
        query_template = params.get("query_template", "{query}")
        query = query_template.format(**context)

        all_sources: List[SourceDocument] = []
        for source_name in sources:
            connector = self.connectors.get(source_name)
            if connector is None:
                continue
            results = await connector.search(query)
            all_sources.extend(results)

        return StepResult(
            output={"sources": [s.title for s in all_sources], "query": query},
            sources_used=all_sources,
        )

    async def _execute_screen(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_extract(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_synthesize(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_export(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_verify(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        """Verification step - returns a pass-through result."""
        return StepResult(
            output={"verified": True},
            quality_marks=[],
        )

    async def _execute_llm_step(
        self, step_def: Dict, context: Dict
    ) -> StepResult:
        """Execute a step that requires LLM completion."""
        params = step_def.get("params", {})
        model_id = params.get("model_id", "")
        system_prompt_template = params.get("system_prompt_template", "")
        temperature = params.get("temperature", 0.0)
        seed = params.get("seed", 42)

        provider = self.providers.get(model_id)
        if provider is None:
            raise ValueError(f"No provider found for model_id: {model_id}")

        system_prompt = system_prompt_template.format(**context)

        request = LLMRequest(
            prompt=str(context),
            system_prompt=system_prompt,
            temperature=temperature,
            seed=seed,
        )

        response: LLMResponse = await provider.complete(request)

        inputs_hash = hashlib.sha256(
            (request.prompt + (request.system_prompt or "")).encode()
        ).hexdigest()
        outputs_hash = hashlib.sha256(response.content.encode()).hexdigest()

        return StepResult(
            output={"content": response.content},
            token_count=response.total_tokens,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
            full_prompt=system_prompt,
        )
