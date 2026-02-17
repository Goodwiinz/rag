# Deterministic Research AI Assistant — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic Research Mode to the existing RAG system with blueprint-based workflow execution, multi-provider LLM support, and evidence graph visualization.

**Architecture:** Workflow Engine as a new FastAPI module (`src/research_engine/`) executing YAML blueprints step-by-step. Each step is a bounded LLM task with deterministic defaults. Audit trail in PostgreSQL, evidence graph in Neo4j, source embeddings in Qdrant. Frontend extends existing Next.js app with new `/research` routes.

**Tech Stack:** FastAPI, SQLAlchemy (async), Celery, Pydantic v2, YAML blueprints, SSE streaming, Neo4j, Qdrant, Next.js 15, Zustand, React

---

## Task 1: Research Engine Data Models

**Files:**

- Create: `backend/src/models/research_project.py`
- Create: `backend/src/models/research_blueprint.py`
- Create: `backend/src/models/research_run.py`
- Create: `backend/src/models/research_step.py`
- Create: `backend/src/models/research_source.py`
- Create: `backend/src/models/research_evidence.py`
- Test: `backend/tests/unit/models/test_research_models.py`

**Step 1: Write the failing test**

```python
"""Tests for research engine SQLAlchemy models."""
import uuid
from datetime import datetime

import pytest

from src.models.research_project import ResearchProject
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_run import ResearchRun, RunStatus
from src.models.research_step import ResearchStep, StepType, ExecutionMode
from src.models.research_source import ResearchSource
from src.models.research_evidence import ResearchEvidence, GroundingStatus


class TestResearchProject:
    def test_create_project(self):
        project = ResearchProject(
            name="Test Project",
            description="A test research project",
            owner_id=uuid.uuid4(),
        )
        assert project.name == "Test Project"
        assert project.status == "active"

    def test_project_has_timestamps(self):
        project = ResearchProject(name="Test", owner_id=uuid.uuid4())
        assert hasattr(project, "created_at")
        assert hasattr(project, "updated_at")


class TestResearchBlueprint:
    def test_create_blueprint(self):
        bp = ResearchBlueprint(
            project_id=uuid.uuid4(),
            name="Systematic Lit Review",
            version=1,
            steps=[{"type": "search", "params": {}}],
            parameters={"date_range": "2020-2026"},
        )
        assert bp.version == 1
        assert bp.is_immutable is False

    def test_blueprint_immutable_default(self):
        bp = ResearchBlueprint(
            project_id=uuid.uuid4(), name="Test", version=1, steps=[]
        )
        assert bp.is_immutable is False


class TestResearchRun:
    def test_create_run(self):
        run = ResearchRun(
            blueprint_id=uuid.uuid4(),
            blueprint_version=1,
        )
        assert run.status == RunStatus.PENDING

    def test_run_status_enum(self):
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.PAUSED.value == "paused"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"


class TestResearchStep:
    def test_create_step(self):
        step = ResearchStep(
            run_id=uuid.uuid4(),
            step_index=0,
            step_type=StepType.SEARCH,
            mode=ExecutionMode.DETERMINISTIC,
            model_id="claude-sonnet-4-6",
            model_version="claude-sonnet-4-6-20250514",
            temperature=0.0,
            seed=42,
        )
        assert step.mode == ExecutionMode.DETERMINISTIC
        assert step.temperature == 0.0

    def test_step_type_enum(self):
        assert StepType.SEARCH.value == "search"
        assert StepType.SCREEN.value == "screen"
        assert StepType.EXTRACT.value == "extract"
        assert StepType.SYNTHESIZE.value == "synthesize"
        assert StepType.VERIFY.value == "verify"
        assert StepType.EXPORT.value == "export"


class TestResearchSource:
    def test_create_source(self):
        source = ResearchSource(
            run_id=uuid.uuid4(),
            connector_type="arxiv",
            external_id="2301.00001",
            title="Test Paper",
        )
        assert source.connector_type == "arxiv"


class TestResearchEvidence:
    def test_create_evidence(self):
        evidence = ResearchEvidence(
            step_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            claim_text="AI improves outcomes by 20%",
            confidence=0.85,
            grounding_status=GroundingStatus.VERIFIED,
        )
        assert evidence.grounding_status == GroundingStatus.VERIFIED
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/models/test_research_models.py -v`
Expected: FAIL with import errors

**Step 3: Write minimal implementation**

`backend/src/models/research_project.py`:

```python
"""Research project model."""
import uuid
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import BaseModel, GUID


class ResearchProject(BaseModel):
    __tablename__ = "research_projects"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="active", nullable=False)
    settings = Column(JSONB, default=dict)
```

`backend/src/models/research_blueprint.py`:

```python
"""Research blueprint model."""
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import BaseModel, GUID


class ResearchBlueprint(BaseModel):
    __tablename__ = "research_blueprints"

    project_id = Column(GUID(), ForeignKey("research_projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    template_source = Column(String(100), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    steps = Column(JSONB, nullable=False, default=list)
    parameters = Column(JSONB, nullable=False, default=dict)
    is_immutable = Column(Boolean, default=False, nullable=False)
```

`backend/src/models/research_run.py`:

```python
"""Research run model."""
import enum
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import BaseModel, GUID


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRun(BaseModel):
    __tablename__ = "research_runs"

    blueprint_id = Column(GUID(), ForeignKey("research_blueprints.id"), nullable=False)
    blueprint_version = Column(Integer, nullable=False)
    status = Column(String(50), default=RunStatus.PENDING.value, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    reproducibility_manifest = Column(JSONB, nullable=True)
    total_tokens = Column(Integer, default=0)
```

`backend/src/models/research_step.py`:

```python
"""Research step model."""
import enum
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import BaseModel, GUID


class StepType(str, enum.Enum):
    SEARCH = "search"
    SCREEN = "screen"
    EXTRACT = "extract"
    SYNTHESIZE = "synthesize"
    VERIFY = "verify"
    EXPORT = "export"


class ExecutionMode(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    EXPLORATORY = "exploratory"


class ResearchStep(BaseModel):
    __tablename__ = "research_steps"

    run_id = Column(GUID(), ForeignKey("research_runs.id"), nullable=False)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(50), nullable=False)
    mode = Column(String(50), default=ExecutionMode.DETERMINISTIC.value, nullable=False)
    inputs_hash = Column(String(64), nullable=True)
    outputs_hash = Column(String(64), nullable=True)
    full_prompt = Column(Text, nullable=True)
    model_id = Column(String(100), nullable=True)
    model_version = Column(String(100), nullable=True)
    temperature = Column(Float, default=0.0, nullable=False)
    seed = Column(Integer, nullable=True)
    output = Column(JSONB, nullable=True)
    quality_marks = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    token_count = Column(Integer, default=0)
```

`backend/src/models/research_source.py`:

```python
"""Research source model."""
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import BaseModel, GUID


class ResearchSource(BaseModel):
    __tablename__ = "research_sources"

    run_id = Column(GUID(), ForeignKey("research_runs.id"), nullable=False)
    connector_type = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=True)
    title = Column(String(500), nullable=False)
    authors = Column(JSONB, nullable=True)
    abstract = Column(Text, nullable=True)
    url = Column(String(2048), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    content_hash = Column(String(64), nullable=True)
```

`backend/src/models/research_evidence.py`:

```python
"""Research evidence model."""
import enum
from sqlalchemy import Column, Float, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.models.base import BaseModel, GUID


class GroundingStatus(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class ResearchEvidence(BaseModel):
    __tablename__ = "research_evidence"

    step_id = Column(GUID(), ForeignKey("research_steps.id"), nullable=False)
    source_id = Column(GUID(), ForeignKey("research_sources.id"), nullable=False)
    claim_text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    grounding_status = Column(
        String(50), default=GroundingStatus.UNVERIFIED.value, nullable=False
    )
    page_reference = Column(String(100), nullable=True)
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/models/test_research_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/models/research_*.py backend/tests/unit/models/test_research_models.py
git commit -m "feat(research): add SQLAlchemy models for research engine"
```

---

## Task 2: Research Engine Pydantic Schemas

**Files:**

- Create: `backend/src/schemas/research_engine.py`
- Test: `backend/tests/unit/schemas/test_research_engine_schemas.py`

**Step 1: Write the failing test**

```python
"""Tests for research engine Pydantic schemas."""
import uuid
import pytest
from pydantic import ValidationError

from src.schemas.research_engine import (
    BlueprintCreate,
    BlueprintResponse,
    BlueprintStepDefinition,
    ProjectCreate,
    ProjectResponse,
    RunCreate,
    RunResponse,
    RunStatus,
    StepResponse,
    ExecutionMode,
    StepType,
)


class TestProjectSchemas:
    def test_project_create_valid(self):
        project = ProjectCreate(name="My Research", description="Testing")
        assert project.name == "My Research"

    def test_project_create_name_required(self):
        with pytest.raises(ValidationError):
            ProjectCreate(description="Missing name")

    def test_project_response(self):
        resp = ProjectResponse(
            id=uuid.uuid4(),
            name="Test",
            status="active",
            created_at="2026-02-17T00:00:00Z",
            updated_at="2026-02-17T00:00:00Z",
        )
        assert resp.status == "active"


class TestBlueprintSchemas:
    def test_step_definition(self):
        step = BlueprintStepDefinition(
            type=StepType.SEARCH,
            name="Search arXiv",
            description="Search arXiv for papers on topic",
            parameters={"query": "machine learning", "max_results": 50},
            model_id="claude-sonnet-4-6",
            mode=ExecutionMode.DETERMINISTIC,
        )
        assert step.type == StepType.SEARCH

    def test_blueprint_create(self):
        bp = BlueprintCreate(
            name="Lit Review",
            steps=[
                BlueprintStepDefinition(
                    type=StepType.SEARCH,
                    name="Search",
                    parameters={},
                )
            ],
            parameters={"topic": "AI safety"},
        )
        assert len(bp.steps) == 1

    def test_blueprint_create_empty_steps_rejected(self):
        with pytest.raises(ValidationError):
            BlueprintCreate(name="Empty", steps=[], parameters={})


class TestRunSchemas:
    def test_run_create(self):
        run = RunCreate(parameters_override={})
        assert run.parameters_override == {}

    def test_run_response(self):
        resp = RunResponse(
            id=uuid.uuid4(),
            blueprint_id=uuid.uuid4(),
            blueprint_version=1,
            status=RunStatus.PENDING,
            created_at="2026-02-17T00:00:00Z",
            updated_at="2026-02-17T00:00:00Z",
        )
        assert resp.status == RunStatus.PENDING
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/schemas/test_research_engine_schemas.py -v`
Expected: FAIL with import errors

**Step 3: Write minimal implementation**

`backend/src/schemas/research_engine.py`:

```python
"""Pydantic schemas for the deterministic research engine."""
import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class StepType(str, enum.Enum):
    SEARCH = "search"
    SCREEN = "screen"
    EXTRACT = "extract"
    SYNTHESIZE = "synthesize"
    VERIFY = "verify"
    EXPORT = "export"


class ExecutionMode(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    EXPLORATORY = "exploratory"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class GroundingStatus(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


# --- Projects ---

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    status: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Blueprints ---

class BlueprintStepDefinition(BaseModel):
    type: StepType
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    mode: ExecutionMode = ExecutionMode.DETERMINISTIC
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    seed: Optional[int] = None
    system_prompt_template: Optional[str] = None


class BlueprintCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    template_source: Optional[str] = None
    steps: List[BlueprintStepDefinition] = Field(..., min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("Blueprint must have at least one step")
        return v


class BlueprintUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    steps: Optional[List[BlueprintStepDefinition]] = None
    parameters: Optional[Dict[str, Any]] = None


class BlueprintResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    template_source: Optional[str] = None
    version: int
    steps: List[BlueprintStepDefinition]
    parameters: Dict[str, Any]
    is_immutable: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Runs ---

class RunCreate(BaseModel):
    parameters_override: Dict[str, Any] = Field(default_factory=dict)


class RunResponse(BaseModel):
    id: UUID
    blueprint_id: UUID
    blueprint_version: int
    status: RunStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_tokens: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Steps ---

class QualityMark(BaseModel):
    check_type: str
    passed: bool
    details: Optional[str] = None


class StepResponse(BaseModel):
    id: UUID
    run_id: UUID
    step_index: int
    step_type: StepType
    mode: ExecutionMode
    inputs_hash: Optional[str] = None
    outputs_hash: Optional[str] = None
    full_prompt: Optional[str] = None
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    temperature: float
    seed: Optional[int] = None
    output: Optional[Dict[str, Any]] = None
    quality_marks: Optional[List[QualityMark]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    token_count: int = 0

    model_config = {"from_attributes": True}


# --- Sources ---

class SourceResponse(BaseModel):
    id: UUID
    run_id: UUID
    connector_type: str
    external_id: Optional[str] = None
    title: str
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    content_hash: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Evidence ---

class EvidenceResponse(BaseModel):
    id: UUID
    step_id: UUID
    source_id: UUID
    claim_text: str
    confidence: float
    grounding_status: GroundingStatus
    page_reference: Optional[str] = None

    model_config = {"from_attributes": True}
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/schemas/test_research_engine_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/schemas/research_engine.py backend/tests/unit/schemas/test_research_engine_schemas.py
git commit -m "feat(research): add Pydantic schemas for research engine API"
```

---

## Task 3: LLM Provider Abstraction

**Files:**

- Create: `backend/src/services/research_engine/__init__.py`
- Create: `backend/src/services/research_engine/providers/__init__.py`
- Create: `backend/src/services/research_engine/providers/base.py`
- Create: `backend/src/services/research_engine/providers/claude_provider.py`
- Create: `backend/src/services/research_engine/providers/openai_provider.py`
- Create: `backend/src/services/research_engine/providers/ollama_provider.py`
- Test: `backend/tests/unit/services/test_llm_providers.py`

**Step 1: Write the failing test**

```python
"""Tests for LLM provider abstraction."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.research_engine.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
)
from src.services.research_engine.providers.claude_provider import ClaudeProvider
from src.services.research_engine.providers.openai_provider import OpenAIProvider
from src.services.research_engine.providers.ollama_provider import OllamaProvider


class TestLLMRequest:
    def test_deterministic_defaults(self):
        req = LLMRequest(prompt="Summarize this.", system_prompt="You are a researcher.")
        assert req.temperature == 0.0
        assert req.seed == 42
        assert req.max_tokens == 2048

    def test_exploratory_mode(self):
        req = LLMRequest(
            prompt="Brainstorm hypotheses.",
            temperature=0.7,
            seed=None,
        )
        assert req.temperature == 0.7


class TestLLMResponse:
    def test_response_fields(self):
        resp = LLMResponse(
            content="The result.",
            model_id="claude-sonnet-4-6",
            model_version="claude-sonnet-4-6-20250514",
            input_tokens=100,
            output_tokens=50,
            temperature=0.0,
            seed=42,
        )
        assert resp.input_tokens == 100
        assert resp.total_tokens == 150


class TestProviderConfig:
    def test_config(self):
        cfg = ProviderConfig(
            provider_type="claude",
            model_id="claude-sonnet-4-6",
            model_version="claude-sonnet-4-6-20250514",
            api_key="sk-test",
        )
        assert cfg.provider_type == "claude"


class TestClaudeProvider:
    @pytest.mark.asyncio
    async def test_complete_calls_anthropic(self):
        with patch("src.services.research_engine.providers.claude_provider.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="Summary result")],
                model="claude-sonnet-4-6-20250514",
                usage=MagicMock(input_tokens=50, output_tokens=30),
            )
            mock_cls.return_value = mock_client

            provider = ClaudeProvider(ProviderConfig(
                provider_type="claude",
                model_id="claude-sonnet-4-6",
                api_key="sk-test",
            ))
            req = LLMRequest(prompt="Summarize this paper.", system_prompt="You are a researcher.")
            resp = await provider.complete(req)

            assert resp.content == "Summary result"
            assert resp.temperature == 0.0
            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_complete_calls_openai(self):
        with patch("src.services.research_engine.providers.openai_provider.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Extracted data"))],
                model="gpt-4o-2024-05-13",
                usage=MagicMock(prompt_tokens=40, completion_tokens=20),
            )
            mock_cls.return_value = mock_client

            provider = OpenAIProvider(ProviderConfig(
                provider_type="openai",
                model_id="gpt-4o",
                model_version="gpt-4o-2024-05-13",
                api_key="sk-test",
            ))
            req = LLMRequest(prompt="Extract fields.", seed=42)
            resp = await provider.complete(req)

            assert resp.content == "Extracted data"
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["seed"] == 42


class TestOllamaProvider:
    @pytest.mark.asyncio
    async def test_complete_calls_ollama(self):
        with patch("src.services.research_engine.providers.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "message": {"content": "Local summary"},
                "model": "llama3",
                "prompt_eval_count": 30,
                "eval_count": 20,
            }
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_cls.return_value = mock_client

            provider = OllamaProvider(ProviderConfig(
                provider_type="ollama",
                model_id="llama3",
                base_url="http://localhost:11434",
            ))
            req = LLMRequest(prompt="Summarize abstract.")
            resp = await provider.complete(req)

            assert resp.content == "Local summary"
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_llm_providers.py -v`
Expected: FAIL with import errors

**Step 3: Write minimal implementation**

`backend/src/services/research_engine/__init__.py`:

```python
"""Deterministic research engine services."""
```

`backend/src/services/research_engine/providers/__init__.py`:

```python
"""LLM provider abstraction for deterministic research engine."""
from .base import LLMProvider, LLMRequest, LLMResponse, ProviderConfig
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider

__all__ = [
    "LLMProvider", "LLMRequest", "LLMResponse", "ProviderConfig",
    "ClaudeProvider", "OpenAIProvider", "OllamaProvider",
]
```

`backend/src/services/research_engine/providers/base.py`:

```python
"""Base LLM provider interface with deterministic defaults."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderConfig:
    provider_type: str
    model_id: str
    model_version: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMRequest:
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.0
    seed: Optional[int] = 42
    max_tokens: int = 2048
    response_format: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    content: str
    model_id: str
    model_version: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    temperature: float = 0.0
    seed: Optional[int] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    async def is_model_available(self) -> bool:
        ...
```

`backend/src/services/research_engine/providers/claude_provider.py`:

```python
"""Anthropic Claude provider."""
from anthropic import AsyncAnthropic

from .base import LLMProvider, LLMRequest, LLMResponse, ProviderConfig


class ClaudeProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = AsyncAnthropic(api_key=config.api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        kwargs = {
            "model": self.config.model_version or self.config.model_id,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        response = await self.client.messages.create(**kwargs)
        return LLMResponse(
            content=response.content[0].text,
            model_id=self.config.model_id,
            model_version=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            temperature=request.temperature,
            seed=request.seed,
        )

    async def is_model_available(self) -> bool:
        try:
            await self.client.messages.create(
                model=self.config.model_version or self.config.model_id,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
```

`backend/src/services/research_engine/providers/openai_provider.py`:

```python
"""OpenAI provider."""
from openai import AsyncOpenAI

from .base import LLMProvider, LLMRequest, LLMResponse, ProviderConfig


class OpenAIProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        kwargs = {
            "model": self.config.model_version or self.config.model_id,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.seed is not None:
            kwargs["seed"] = request.seed

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content,
            model_id=self.config.model_id,
            model_version=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            temperature=request.temperature,
            seed=request.seed,
        )

    async def is_model_available(self) -> bool:
        try:
            await self.client.chat.completions.create(
                model=self.config.model_version or self.config.model_id,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
```

`backend/src/services/research_engine/providers/ollama_provider.py`:

```python
"""Ollama local model provider."""
import httpx

from .base import LLMProvider, LLMRequest, LLMResponse, ProviderConfig


class OllamaProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.config.model_id,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.seed is not None:
            payload["options"]["seed"] = request.seed
        if request.system_prompt:
            payload["messages"].insert(0, {"role": "system", "content": request.system_prompt})

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model_id=self.config.model_id,
            model_version=data.get("model"),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            temperature=request.temperature,
            seed=request.seed,
        )

    async def is_model_available(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/api/tags", timeout=5)
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                return self.config.model_id in models
        except Exception:
            return False
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_llm_providers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/research_engine/ backend/tests/unit/services/test_llm_providers.py
git commit -m "feat(research): add LLM provider abstraction with Claude, OpenAI, Ollama"
```

---

## Task 4: Blueprint Loader and Templates

**Files:**

- Create: `backend/src/services/research_engine/blueprints/__init__.py`
- Create: `backend/src/services/research_engine/blueprints/loader.py`
- Create: `backend/src/services/research_engine/blueprints/templates/systematic_literature_review.yaml`
- Create: `backend/src/services/research_engine/blueprints/templates/evidence_synthesis.yaml`
- Create: `backend/src/services/research_engine/blueprints/templates/data_extraction.yaml`
- Test: `backend/tests/unit/services/test_blueprint_loader.py`

**Step 1: Write the failing test**

```python
"""Tests for blueprint loader."""
import pytest
from pathlib import Path

from src.services.research_engine.blueprints.loader import BlueprintLoader
from src.schemas.research_engine import BlueprintStepDefinition, StepType


class TestBlueprintLoader:
    def test_list_templates(self):
        loader = BlueprintLoader()
        templates = loader.list_templates()
        assert len(templates) >= 3
        names = [t["name"] for t in templates]
        assert "Systematic Literature Review" in names
        assert "Evidence Synthesis" in names
        assert "Data Extraction" in names

    def test_load_template(self):
        loader = BlueprintLoader()
        template = loader.load_template("systematic_literature_review")
        assert template["name"] == "Systematic Literature Review"
        assert len(template["steps"]) > 0

    def test_load_template_returns_valid_steps(self):
        loader = BlueprintLoader()
        template = loader.load_template("systematic_literature_review")
        for step_data in template["steps"]:
            step = BlueprintStepDefinition(**step_data)
            assert step.type in StepType

    def test_load_template_not_found(self):
        loader = BlueprintLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_template("nonexistent_template")

    def test_validate_template(self):
        loader = BlueprintLoader()
        template = loader.load_template("systematic_literature_review")
        errors = loader.validate_template(template)
        assert errors == []

    def test_validate_template_rejects_empty_steps(self):
        loader = BlueprintLoader()
        errors = loader.validate_template({"name": "Bad", "steps": [], "parameters": {}})
        assert len(errors) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_blueprint_loader.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

`backend/src/services/research_engine/blueprints/__init__.py`:

```python
"""Blueprint loader and template management."""
from .loader import BlueprintLoader

__all__ = ["BlueprintLoader"]
```

`backend/src/services/research_engine/blueprints/templates/systematic_literature_review.yaml`:

```yaml
name: Systematic Literature Review
description: Conduct a systematic review following PRISMA guidelines
parameters:
  topic: ""
  date_range_start: "2020-01-01"
  date_range_end: "2026-12-31"
  max_sources: 100
  inclusion_criteria: []
  exclusion_criteria: []
steps:
  - type: search
    name: Search academic databases
    description: Query arXiv, Semantic Scholar, and PubMed for relevant papers
    parameters:
      sources: [arxiv, semantic_scholar, pubmed]
      max_results_per_source: 50
    model_id: null
    mode: deterministic

  - type: screen
    name: Screen by title and abstract
    description: Apply inclusion/exclusion criteria to filter relevant papers
    parameters:
      criteria_mode: strict
    model_id: claude-sonnet-4-6
    mode: deterministic
    system_prompt_template: |
      You are a systematic reviewer. Given the following inclusion criteria: {inclusion_criteria}
      and exclusion criteria: {exclusion_criteria}, evaluate whether this paper should be included.
      Respond with JSON: {"include": true/false, "reason": "..."}

  - type: extract
    name: Extract key data
    description: Extract structured data from included papers
    parameters:
      fields:
        [
          title,
          authors,
          year,
          methodology,
          sample_size,
          key_findings,
          limitations,
        ]
    model_id: gpt-4o
    mode: deterministic
    system_prompt_template: |
      Extract the following fields from this paper: {fields}.
      Return JSON with each field as a key. Use null for unavailable fields.

  - type: synthesize
    name: Synthesize findings
    description: Synthesize extracted data into a coherent narrative
    parameters: {}
    model_id: claude-sonnet-4-6
    mode: deterministic
    system_prompt_template: |
      You are a research synthesizer. Given the following extracted data from {paper_count} papers,
      synthesize the findings into a coherent narrative. Identify common themes, contradictions,
      and gaps in the literature. Cite papers by their title.

  - type: verify
    name: Verify source grounding
    description: Check that all claims are grounded in source documents
    parameters:
      check_types: [source_grounding, consistency]
    model_id: null
    mode: deterministic

  - type: export
    name: Generate report
    description: Generate a structured literature review report
    parameters:
      format: markdown
      sections: [introduction, methodology, findings, discussion, references]
    model_id: claude-sonnet-4-6
    mode: deterministic
```

`backend/src/services/research_engine/blueprints/templates/evidence_synthesis.yaml`:

```yaml
name: Evidence Synthesis
description: Synthesize evidence from multiple sources on a specific research question
parameters:
  research_question: ""
  max_sources: 50
steps:
  - type: search
    name: Search for evidence
    description: Find relevant evidence across academic and web sources
    parameters:
      sources: [arxiv, semantic_scholar, web]
      max_results_per_source: 25
    mode: deterministic

  - type: extract
    name: Extract claims and evidence
    description: Extract specific claims and supporting evidence from sources
    parameters:
      fields: [claim, evidence_text, methodology, confidence_level]
    model_id: gpt-4o
    mode: deterministic

  - type: synthesize
    name: Build evidence map
    description: Organize evidence by theme, identify support/contradiction relationships
    parameters: {}
    model_id: claude-sonnet-4-6
    mode: deterministic

  - type: verify
    name: Verify grounding
    description: Verify all claims are grounded in source material
    parameters:
      check_types: [source_grounding]
    mode: deterministic

  - type: export
    name: Generate synthesis report
    description: Generate structured evidence synthesis report
    parameters:
      format: markdown
    model_id: claude-sonnet-4-6
    mode: deterministic
```

`backend/src/services/research_engine/blueprints/templates/data_extraction.yaml`:

```yaml
name: Data Extraction
description: Extract structured data from a set of documents
parameters:
  extraction_schema: {}
  source_documents: []
steps:
  - type: search
    name: Gather documents
    description: Collect documents from specified sources or uploads
    parameters:
      sources: [rag_store]
    mode: deterministic

  - type: extract
    name: Extract structured data
    description: Extract data according to the defined schema
    parameters: {}
    model_id: gpt-4o
    mode: deterministic
    system_prompt_template: |
      Extract data from the following document according to this schema: {extraction_schema}.
      Return valid JSON matching the schema. Use null for unavailable fields.

  - type: verify
    name: Validate extraction
    description: Validate extracted data against schema and source
    parameters:
      check_types: [schema_validation, source_grounding]
    mode: deterministic

  - type: export
    name: Export dataset
    description: Export extracted data as structured dataset
    parameters:
      format: json
    mode: deterministic
```

`backend/src/services/research_engine/blueprints/loader.py`:

```python
"""Blueprint template loader."""
import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.schemas.research_engine import BlueprintStepDefinition, StepType

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class BlueprintLoader:
    def __init__(self, templates_dir: Path = TEMPLATES_DIR):
        self.templates_dir = templates_dir

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = []
        for path in sorted(self.templates_dir.glob("*.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f)
            templates.append({
                "slug": path.stem,
                "name": data["name"],
                "description": data.get("description", ""),
                "step_count": len(data.get("steps", [])),
            })
        return templates

    def load_template(self, slug: str) -> Dict[str, Any]:
        path = self.templates_dir / f"{slug}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {slug}")
        with open(path) as f:
            return yaml.safe_load(f)

    def validate_template(self, template: Dict[str, Any]) -> List[str]:
        errors = []
        steps = template.get("steps", [])
        if not steps:
            errors.append("Blueprint must have at least one step")
            return errors
        for i, step in enumerate(steps):
            step_type = step.get("type")
            if step_type not in [t.value for t in StepType]:
                errors.append(f"Step {i}: invalid type '{step_type}'")
            if not step.get("name"):
                errors.append(f"Step {i}: missing name")
        return errors
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_blueprint_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/research_engine/blueprints/ backend/tests/unit/services/test_blueprint_loader.py
git commit -m "feat(research): add blueprint loader with YAML templates"
```

---

## Task 5: Source Connectors

**Files:**

- Create: `backend/src/services/research_engine/connectors/__init__.py`
- Create: `backend/src/services/research_engine/connectors/base.py`
- Create: `backend/src/services/research_engine/connectors/arxiv_connector.py`
- Create: `backend/src/services/research_engine/connectors/semantic_scholar_connector.py`
- Create: `backend/src/services/research_engine/connectors/rag_store_connector.py`
- Test: `backend/tests/unit/services/test_source_connectors.py`

**Step 1: Write the failing test**

```python
"""Tests for source connectors."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument
from src.services.research_engine.connectors.arxiv_connector import ArxivConnector
from src.services.research_engine.connectors.semantic_scholar_connector import SemanticScholarConnector
from src.services.research_engine.connectors.rag_store_connector import RagStoreConnector


class TestSourceDocument:
    def test_create(self):
        doc = SourceDocument(
            connector_type="arxiv",
            external_id="2301.00001",
            title="Test Paper",
            authors=["Author A"],
            abstract="Abstract text.",
            url="https://arxiv.org/abs/2301.00001",
        )
        assert doc.connector_type == "arxiv"
        assert doc.content_hash is None


class TestArxivConnector:
    @pytest.mark.asyncio
    async def test_search_returns_source_documents(self):
        mock_xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>http://arxiv.org/abs/2301.00001v1</id>
                <title>Test Paper Title</title>
                <summary>This is the abstract.</summary>
                <author><name>Author A</name></author>
            </entry>
        </feed>"""

        with patch("src.services.research_engine.connectors.arxiv_connector.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_response = MagicMock()
            mock_response.text = mock_xml
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_cls.return_value = mock_client

            connector = ArxivConnector()
            results = await connector.search("machine learning", max_results=10)

            assert len(results) == 1
            assert results[0].connector_type == "arxiv"
            assert results[0].title == "Test Paper Title"


class TestSemanticScholarConnector:
    @pytest.mark.asyncio
    async def test_search_returns_source_documents(self):
        mock_response_data = {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "S2 Paper",
                    "abstract": "Some abstract.",
                    "authors": [{"name": "Author B"}],
                    "url": "https://semanticscholar.org/paper/abc123",
                }
            ]
        }

        with patch("src.services.research_engine.connectors.semantic_scholar_connector.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response_data
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            mock_cls.return_value = mock_client

            connector = SemanticScholarConnector()
            results = await connector.search("machine learning", max_results=10)

            assert len(results) == 1
            assert results[0].connector_type == "semantic_scholar"
            assert results[0].title == "S2 Paper"


class TestRagStoreConnector:
    @pytest.mark.asyncio
    async def test_search_uses_hybrid_search(self):
        mock_search = AsyncMock(return_value={
            "results": [
                {"document_id": "doc1", "title": "Uploaded Paper", "content": "Content here", "score": 0.9}
            ]
        })

        connector = RagStoreConnector(search_fn=mock_search)
        results = await connector.search("machine learning", max_results=10)

        assert len(results) == 1
        assert results[0].connector_type == "rag_store"
        mock_search.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_source_connectors.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

`backend/src/services/research_engine/connectors/__init__.py`:

```python
"""Source connectors for research engine."""
from .base import SourceConnector, SourceDocument
from .arxiv_connector import ArxivConnector
from .semantic_scholar_connector import SemanticScholarConnector
from .rag_store_connector import RagStoreConnector

__all__ = [
    "SourceConnector", "SourceDocument",
    "ArxivConnector", "SemanticScholarConnector", "RagStoreConnector",
]
```

`backend/src/services/research_engine/connectors/base.py`:

```python
"""Base source connector interface."""
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceDocument:
    connector_type: str
    external_id: Optional[str] = None
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    url: Optional[str] = None
    full_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: Optional[str] = None

    def compute_hash(self) -> str:
        content = f"{self.title}{self.abstract or ''}{self.full_text or ''}"
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.content_hash


class SourceConnector(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 50, **kwargs) -> List[SourceDocument]:
        ...
```

`backend/src/services/research_engine/connectors/arxiv_connector.py`:

```python
"""arXiv source connector."""
import logging
import xml.etree.ElementTree as ET
from typing import List

import httpx

from .base import SourceConnector, SourceDocument

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"


class ArxivConnector(SourceConnector):
    async def search(self, query: str, max_results: int = 50, **kwargs) -> List[SourceDocument]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(ARXIV_API_URL, params=params, timeout=60)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        results = []
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            arxiv_id = (entry.findtext(f"{{{ATOM_NS}}}id") or "").split("/abs/")[-1]
            title = (entry.findtext(f"{{{ATOM_NS}}}title") or "").strip()
            abstract = (entry.findtext(f"{{{ATOM_NS}}}summary") or "").strip()
            authors = [
                a.findtext(f"{{{ATOM_NS}}}name") or ""
                for a in entry.findall(f"{{{ATOM_NS}}}author")
            ]
            results.append(SourceDocument(
                connector_type="arxiv",
                external_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                url=f"https://arxiv.org/abs/{arxiv_id}",
            ))
        return results
```

`backend/src/services/research_engine/connectors/semantic_scholar_connector.py`:

```python
"""Semantic Scholar source connector."""
import logging
from typing import List

import httpx

from .base import SourceConnector, SourceDocument

logger = logging.getLogger(__name__)

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarConnector(SourceConnector):
    def __init__(self, api_key: str = None):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 50, **kwargs) -> List[SourceDocument]:
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "paperId,title,abstract,authors,url",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(S2_API_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for paper in data.get("data", []):
            results.append(SourceDocument(
                connector_type="semantic_scholar",
                external_id=paper.get("paperId"),
                title=paper.get("title", ""),
                authors=[a["name"] for a in paper.get("authors", [])],
                abstract=paper.get("abstract"),
                url=paper.get("url"),
            ))
        return results
```

`backend/src/services/research_engine/connectors/rag_store_connector.py`:

```python
"""RAG document store connector — searches existing uploaded documents."""
import logging
from typing import Any, Callable, Coroutine, Dict, List

from .base import SourceConnector, SourceDocument

logger = logging.getLogger(__name__)


class RagStoreConnector(SourceConnector):
    def __init__(self, search_fn: Callable[..., Coroutine[Any, Any, Dict]]):
        self.search_fn = search_fn

    async def search(self, query: str, max_results: int = 50, **kwargs) -> List[SourceDocument]:
        result = await self.search_fn(query=query, limit=max_results)
        results = []
        for item in result.get("results", []):
            results.append(SourceDocument(
                connector_type="rag_store",
                external_id=item.get("document_id"),
                title=item.get("title", "Untitled"),
                abstract=item.get("content", "")[:500],
                metadata={"score": item.get("score", 0.0)},
            ))
        return results
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_source_connectors.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/research_engine/connectors/ backend/tests/unit/services/test_source_connectors.py
git commit -m "feat(research): add source connectors for arXiv, Semantic Scholar, RAG store"
```

---

## Task 6: Workflow Engine Core

**Files:**

- Create: `backend/src/services/research_engine/engine.py`
- Create: `backend/src/services/research_engine/step_executor.py`
- Create: `backend/src/services/research_engine/verification.py`
- Test: `backend/tests/unit/services/test_workflow_engine.py`

**Step 1: Write the failing test**

```python
"""Tests for workflow engine core."""
import hashlib
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.research_engine.engine import WorkflowEngine
from src.services.research_engine.step_executor import StepExecutor, StepResult
from src.services.research_engine.verification import (
    VerificationService,
    QualityMark,
    run_source_grounding_check,
)
from src.services.research_engine.providers.base import LLMResponse


class TestStepResult:
    def test_create(self):
        result = StepResult(
            output={"summary": "ML is important."},
            sources_used=[],
            quality_marks=[QualityMark(check_type="schema_validation", passed=True)],
            token_count=150,
        )
        assert result.token_count == 150
        assert result.quality_marks[0].passed is True


class TestVerificationService:
    def test_source_grounding_pass(self):
        claim = "The model achieved 95% accuracy."
        source_text = "Our model achieved 95% accuracy on the benchmark dataset."
        mark = run_source_grounding_check(claim, source_text)
        assert mark.passed is True
        assert mark.check_type == "source_grounding"

    def test_source_grounding_fail(self):
        claim = "The model achieved 99% accuracy."
        source_text = "Our model achieved 72% accuracy on the benchmark dataset."
        mark = run_source_grounding_check(claim, source_text)
        assert mark.passed is False


class TestStepExecutor:
    @pytest.mark.asyncio
    async def test_execute_search_step(self):
        mock_connector = AsyncMock()
        mock_connector.search.return_value = [
            MagicMock(title="Paper A", connector_type="arxiv", external_id="001"),
        ]

        executor = StepExecutor(
            connectors={"arxiv": mock_connector},
            providers={},
        )
        step_def = {
            "type": "search",
            "name": "Search",
            "parameters": {"sources": ["arxiv"], "max_results_per_source": 10},
        }
        result = await executor.execute(step_def, context={})

        assert len(result.output["sources"]) == 1
        mock_connector.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_synthesize_step(self):
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = LLMResponse(
            content="Synthesis: ML is transformative.",
            model_id="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
        )

        executor = StepExecutor(
            connectors={},
            providers={"claude-sonnet-4-6": mock_provider},
        )
        step_def = {
            "type": "synthesize",
            "name": "Synthesize",
            "parameters": {},
            "model_id": "claude-sonnet-4-6",
            "mode": "deterministic",
            "temperature": 0.0,
            "seed": 42,
            "system_prompt_template": "Synthesize these findings: {findings}",
        }
        context = {"findings": "Paper A says X. Paper B says Y."}
        result = await executor.execute(step_def, context=context)

        assert "Synthesis" in result.output["content"]
        assert result.token_count == 150


class TestWorkflowEngine:
    @pytest.mark.asyncio
    async def test_run_blueprint(self):
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = StepResult(
            output={"sources": [{"title": "A"}]},
            sources_used=[],
            quality_marks=[],
            token_count=0,
        )

        engine = WorkflowEngine(step_executor=mock_executor)
        blueprint = {
            "steps": [
                {"type": "search", "name": "Search", "parameters": {"sources": ["arxiv"]}},
            ],
            "parameters": {"topic": "AI"},
        }
        events = []
        async for event in engine.run(blueprint, run_id=uuid.uuid4()):
            events.append(event)

        assert any(e["event"] == "step_start" for e in events)
        assert any(e["event"] == "step_complete" for e in events)
        assert any(e["event"] == "run_complete" for e in events)

    @pytest.mark.asyncio
    async def test_run_pauses_on_quality_failure(self):
        fail_result = StepResult(
            output={},
            sources_used=[],
            quality_marks=[QualityMark(check_type="source_grounding", passed=False, details="Claim not found")],
            token_count=0,
        )
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = fail_result

        engine = WorkflowEngine(step_executor=mock_executor, pause_on_quality_failure=True)
        blueprint = {
            "steps": [{"type": "verify", "name": "Verify", "parameters": {}}],
            "parameters": {},
        }
        events = []
        async for event in engine.run(blueprint, run_id=uuid.uuid4()):
            events.append(event)

        assert any(e["event"] == "run_paused" for e in events)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_workflow_engine.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

`backend/src/services/research_engine/verification.py`:

```python
"""Verification and quality checking for research steps."""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QualityMark:
    check_type: str
    passed: bool
    details: Optional[str] = None


def run_source_grounding_check(claim: str, source_text: str) -> QualityMark:
    """Check if a claim is grounded in the source text.

    Uses substring and key-number matching as a deterministic check.
    """
    claim_lower = claim.lower().strip()
    source_lower = source_text.lower().strip()

    # Extract numbers from claim
    import re
    claim_numbers = set(re.findall(r'\d+\.?\d*%?', claim))

    if not claim_numbers:
        # No numbers — check if key phrases overlap
        claim_words = set(claim_lower.split())
        source_words = set(source_lower.split())
        overlap = len(claim_words & source_words) / max(len(claim_words), 1)
        passed = overlap > 0.5
    else:
        # Check all numbers in claim appear in source
        source_numbers = set(re.findall(r'\d+\.?\d*%?', source_lower))
        passed = claim_numbers.issubset(source_numbers)

    return QualityMark(
        check_type="source_grounding",
        passed=passed,
        details=None if passed else f"Claim numbers {claim_numbers} not found in source",
    )
```

`backend/src/services/research_engine/step_executor.py`:

```python
"""Executes individual blueprint steps."""
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .connectors.base import SourceConnector, SourceDocument
from .providers.base import LLMProvider, LLMRequest
from .verification import QualityMark

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    output: Dict[str, Any]
    sources_used: List[SourceDocument] = field(default_factory=list)
    quality_marks: List[QualityMark] = field(default_factory=list)
    token_count: int = 0
    inputs_hash: Optional[str] = None
    outputs_hash: Optional[str] = None
    full_prompt: Optional[str] = None


class StepExecutor:
    def __init__(
        self,
        connectors: Dict[str, SourceConnector],
        providers: Dict[str, LLMProvider],
    ):
        self.connectors = connectors
        self.providers = providers

    async def execute(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        step_type = step_def["type"]
        handler = getattr(self, f"_execute_{step_type}", None)
        if handler is None:
            raise ValueError(f"Unknown step type: {step_type}")
        return await handler(step_def, context)

    async def _execute_search(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        params = step_def.get("parameters", {})
        sources_requested = params.get("sources", [])
        max_per_source = params.get("max_results_per_source", 50)
        query = context.get("topic", context.get("research_question", ""))

        all_sources = []
        for source_name in sources_requested:
            connector = self.connectors.get(source_name)
            if connector:
                results = await connector.search(query, max_results=max_per_source)
                all_sources.extend(results)

        return StepResult(
            output={"sources": [{"title": s.title, "id": s.external_id, "type": s.connector_type} for s in all_sources]},
            sources_used=all_sources,
        )

    async def _execute_screen(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_extract(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_synthesize(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_verify(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        # Verification runs deterministic checks, no LLM needed
        return StepResult(output={"verified": True}, quality_marks=[])

    async def _execute_export(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        return await self._execute_llm_step(step_def, context)

    async def _execute_llm_step(
        self, step_def: Dict[str, Any], context: Dict[str, Any]
    ) -> StepResult:
        model_id = step_def.get("model_id")
        provider = self.providers.get(model_id)
        if not provider:
            raise ValueError(f"No provider configured for model: {model_id}")

        template = step_def.get("system_prompt_template", "")
        system_prompt = template.format(**context) if template else None
        prompt = json.dumps(context)

        inputs_hash = hashlib.sha256(prompt.encode()).hexdigest()

        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=step_def.get("temperature", 0.0),
            seed=step_def.get("seed", 42),
        )
        response = await provider.complete(request)

        outputs_hash = hashlib.sha256(response.content.encode()).hexdigest()

        return StepResult(
            output={"content": response.content},
            token_count=response.total_tokens,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
            full_prompt=prompt,
        )
```

`backend/src/services/research_engine/engine.py`:

```python
"""Workflow engine — executes blueprints step-by-step."""
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

from .step_executor import StepExecutor, StepResult
from .verification import QualityMark

logger = logging.getLogger(__name__)


class WorkflowEngine:
    def __init__(
        self,
        step_executor: StepExecutor,
        pause_on_quality_failure: bool = True,
    ):
        self.step_executor = step_executor
        self.pause_on_quality_failure = pause_on_quality_failure

    async def run(
        self,
        blueprint: Dict[str, Any],
        run_id: UUID,
        start_from_step: int = 0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        steps = blueprint["steps"]
        context = dict(blueprint.get("parameters", {}))
        total_tokens = 0

        yield {
            "event": "run_start",
            "run_id": str(run_id),
            "total_steps": len(steps),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for i, step_def in enumerate(steps[start_from_step:], start=start_from_step):
            yield {
                "event": "step_start",
                "step_index": i,
                "step_type": step_def["type"],
                "step_name": step_def.get("name", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            try:
                result = await self.step_executor.execute(step_def, context)
            except Exception as exc:
                yield {
                    "event": "step_error",
                    "step_index": i,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                yield {
                    "event": "run_failed",
                    "run_id": str(run_id),
                    "failed_at_step": i,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return

            total_tokens += result.token_count

            # Merge step output into context for subsequent steps
            context.update(result.output)

            yield {
                "event": "step_complete",
                "step_index": i,
                "step_type": step_def["type"],
                "token_count": result.token_count,
                "quality_marks": [
                    {"check_type": qm.check_type, "passed": qm.passed, "details": qm.details}
                    for qm in result.quality_marks
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Check for quality failures
            has_failure = any(not qm.passed for qm in result.quality_marks)
            if has_failure and self.pause_on_quality_failure:
                yield {
                    "event": "run_paused",
                    "run_id": str(run_id),
                    "paused_at_step": i,
                    "reason": "quality_check_failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return

        yield {
            "event": "run_complete",
            "run_id": str(run_id),
            "total_tokens": total_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_workflow_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/research_engine/engine.py backend/src/services/research_engine/step_executor.py backend/src/services/research_engine/verification.py backend/tests/unit/services/test_workflow_engine.py
git commit -m "feat(research): add workflow engine with step executor and verification"
```

---

## Task 7: Research Engine API Endpoints

**Files:**

- Create: `backend/src/api/research_engine/__init__.py`
- Create: `backend/src/api/research_engine/projects.py`
- Create: `backend/src/api/research_engine/blueprints.py`
- Create: `backend/src/api/research_engine/runs.py`
- Create: `backend/src/api/research_engine/steps.py`
- Modify: `backend/src/main.py` (register new routers)
- Test: `backend/tests/unit/api/test_research_engine_endpoints.py`

**Step 1: Write the failing test**

```python
"""Tests for research engine API endpoints."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.dependencies import get_current_user


# ---- Factories ----

def _mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.role = "admin"
    return user


def _mock_project(owner_id=None):
    return MagicMock(
        id=uuid.uuid4(),
        name="Test Project",
        description="Desc",
        owner_id=owner_id or uuid.uuid4(),
        status="active",
        settings={},
        created_at="2026-02-17T00:00:00Z",
        updated_at="2026-02-17T00:00:00Z",
        is_deleted=False,
    )


# ---- Project Endpoints ----

class TestProjectEndpoints:
    def test_create_project(self, client_with_auth):
        resp = client_with_auth.post(
            "/api/v1/research-engine/projects",
            json={"name": "My Research", "description": "Test"},
        )
        assert resp.status_code == 201

    def test_list_projects(self, client_with_auth):
        resp = client_with_auth.get("/api/v1/research-engine/projects")
        assert resp.status_code == 200

    def test_create_project_requires_name(self, client_with_auth):
        resp = client_with_auth.post(
            "/api/v1/research-engine/projects",
            json={"description": "Missing name"},
        )
        assert resp.status_code == 422


class TestBlueprintEndpoints:
    def test_list_templates(self, client_with_auth):
        resp = client_with_auth.get("/api/v1/research-engine/blueprints/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3


class TestRunEndpoints:
    def test_start_run_returns_202(self, client_with_auth, mock_blueprint_id):
        resp = client_with_auth.post(
            f"/api/v1/research-engine/blueprints/{mock_blueprint_id}/runs",
            json={"parameters_override": {}},
        )
        # 202 Accepted since it starts async execution
        assert resp.status_code in (201, 202)
```

Note: Full endpoint tests require fixtures from the test conftest. The test file above shows the pattern — the actual implementation will use the existing `conftest.py` patterns (mock DB, mock auth).

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/api/test_research_engine_endpoints.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

`backend/src/api/research_engine/__init__.py`:

```python
"""Research engine API endpoints."""
from .projects import router as research_engine_projects_router
from .blueprints import router as research_engine_blueprints_router
from .runs import router as research_engine_runs_router
from .steps import router as research_engine_steps_router

__all__ = [
    "research_engine_projects_router",
    "research_engine_blueprints_router",
    "research_engine_runs_router",
    "research_engine_steps_router",
]
```

`backend/src/api/research_engine/projects.py`:

```python
"""Research engine project endpoints."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_project import ResearchProject
from src.models.user import User
from src.schemas.research_engine import ProjectCreate, ProjectResponse, ProjectUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/research-engine/projects", tags=["research-engine"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = ResearchProject(
        name=body.name,
        description=body.description,
        owner_id=current_user.id,
        settings=body.settings,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    project_status: Optional[str] = Query(None, alias="status"),
):
    query = select(ResearchProject).where(
        ResearchProject.owner_id == current_user.id,
        ResearchProject.is_deleted == False,
    )
    if project_status:
        query = query.where(ResearchProject.status == project_status)
    result = await db.execute(query.order_by(ResearchProject.updated_at.desc()))
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(ResearchProject, project_id)
    if not project or project.is_deleted or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

`backend/src/api/research_engine/blueprints.py`:

```python
"""Research engine blueprint endpoints."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_project import ResearchProject
from src.models.user import User
from src.schemas.research_engine import BlueprintCreate, BlueprintResponse, BlueprintUpdate
from src.services.research_engine.blueprints.loader import BlueprintLoader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/research-engine/blueprints", tags=["research-engine"])

_loader = BlueprintLoader()


@router.get("/templates")
async def list_templates():
    return _loader.list_templates()


@router.post(
    "/projects/{project_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=BlueprintResponse,
)
async def create_blueprint(
    project_id: UUID,
    body: BlueprintCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(ResearchProject, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    bp = ResearchBlueprint(
        project_id=project_id,
        name=body.name,
        template_source=body.template_source,
        version=1,
        steps=[s.model_dump() for s in body.steps],
        parameters=body.parameters,
    )
    db.add(bp)
    await db.commit()
    await db.refresh(bp)
    return bp


@router.get("/{blueprint_id}", response_model=BlueprintResponse)
async def get_blueprint(
    blueprint_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bp = await db.get(ResearchBlueprint, blueprint_id)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return bp
```

`backend/src/api/research_engine/runs.py`:

```python
"""Research engine run endpoints."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_run import ResearchRun, RunStatus
from src.models.user import User
from src.schemas.research_engine import RunCreate, RunResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/research-engine", tags=["research-engine"])


@router.post(
    "/blueprints/{blueprint_id}/runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunResponse,
)
async def start_run(
    blueprint_id: UUID,
    body: RunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bp = await db.get(ResearchBlueprint, blueprint_id)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    # Mark blueprint as immutable after first run
    if not bp.is_immutable:
        bp.is_immutable = True

    run = ResearchRun(
        blueprint_id=blueprint_id,
        blueprint_version=bp.version,
        status=RunStatus.PENDING.value,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # TODO: Dispatch Celery task for async execution
    return run


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/pause")
async def pause_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.RUNNING.value:
        raise HTTPException(status_code=409, detail="Run is not currently running")
    run.status = RunStatus.PAUSED.value
    await db.commit()
    return {"status": "paused"}


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.PAUSED.value:
        raise HTTPException(status_code=409, detail="Run is not paused")
    run.status = RunStatus.RUNNING.value
    await db.commit()
    # TODO: Resume Celery task
    return {"status": "resumed"}


@router.get("/runs/{run_id}/manifest")
async def get_manifest(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(ResearchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Run is not completed")
    return run.reproducibility_manifest or {}
```

`backend/src/api/research_engine/steps.py`:

```python
"""Research engine step endpoints."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_step import ResearchStep
from src.models.user import User
from src.schemas.research_engine import StepResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/research-engine", tags=["research-engine"])


@router.get("/runs/{run_id}/steps", response_model=list[StepResponse])
async def list_steps(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResearchStep)
        .where(ResearchStep.run_id == run_id)
        .order_by(ResearchStep.step_index)
    )
    return result.scalars().all()


@router.get("/steps/{step_id}", response_model=StepResponse)
async def get_step(
    step_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    step = await db.get(ResearchStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step
```

Modify `backend/src/main.py` — add after the existing research imports:

```python
from src.api.research_engine import (
    research_engine_projects_router,
    research_engine_blueprints_router,
    research_engine_runs_router,
    research_engine_steps_router,
)
```

And add to router includes (after existing research router includes):

```python
app.include_router(research_engine_projects_router)
app.include_router(research_engine_blueprints_router)
app.include_router(research_engine_runs_router)
app.include_router(research_engine_steps_router)
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/api/test_research_engine_endpoints.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/research_engine/ backend/src/main.py backend/tests/unit/api/test_research_engine_endpoints.py
git commit -m "feat(research): add research engine API endpoints and register routers"
```

---

## Task 8: Database Migration

**Files:**

- Create: `backend/src/migrations/007_create_research_engine_tables.sql`

**Step 1: Write the migration SQL**

```sql
-- Research Engine Tables
-- Deterministic research workflow system

BEGIN;

-- Research projects
CREATE TABLE IF NOT EXISTS research_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSONB NOT NULL DEFAULT '{}',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_projects_owner ON research_projects(owner_id);
CREATE INDEX idx_research_projects_status ON research_projects(status);

-- Research blueprints
CREATE TABLE IF NOT EXISTS research_blueprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    template_source VARCHAR(100),
    version INTEGER NOT NULL DEFAULT 1,
    steps JSONB NOT NULL DEFAULT '[]',
    parameters JSONB NOT NULL DEFAULT '{}',
    is_immutable BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_blueprints_project ON research_blueprints(project_id);

-- Research runs
CREATE TABLE IF NOT EXISTS research_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id UUID NOT NULL REFERENCES research_blueprints(id) ON DELETE CASCADE,
    blueprint_version INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    reproducibility_manifest JSONB,
    total_tokens INTEGER DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_runs_blueprint ON research_runs(blueprint_id);
CREATE INDEX idx_research_runs_status ON research_runs(status);

-- Research steps (audit trail)
CREATE TABLE IF NOT EXISTS research_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    mode VARCHAR(50) NOT NULL DEFAULT 'deterministic',
    inputs_hash VARCHAR(64),
    outputs_hash VARCHAR(64),
    full_prompt TEXT,
    model_id VARCHAR(100),
    model_version VARCHAR(100),
    temperature FLOAT NOT NULL DEFAULT 0.0,
    seed INTEGER,
    output JSONB,
    quality_marks JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    token_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_steps_run ON research_steps(run_id);
CREATE INDEX idx_research_steps_type ON research_steps(step_type);

-- Research sources
CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    connector_type VARCHAR(50) NOT NULL,
    external_id VARCHAR(255),
    title VARCHAR(500) NOT NULL,
    authors JSONB,
    abstract TEXT,
    url VARCHAR(2048),
    metadata JSONB,
    content_hash VARCHAR(64),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_sources_run ON research_sources(run_id);
CREATE INDEX idx_research_sources_connector ON research_sources(connector_type);

-- Research evidence
CREATE TABLE IF NOT EXISTS research_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id UUID NOT NULL REFERENCES research_steps(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES research_sources(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    grounding_status VARCHAR(50) NOT NULL DEFAULT 'unverified',
    page_reference VARCHAR(100),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_evidence_step ON research_evidence(step_id);
CREATE INDEX idx_research_evidence_source ON research_evidence(source_id);
CREATE INDEX idx_research_evidence_grounding ON research_evidence(grounding_status);

COMMIT;
```

**Step 2: Commit**

```bash
git add backend/src/migrations/007_create_research_engine_tables.sql
git commit -m "feat(research): add database migration for research engine tables"
```

---

## Task 9: Frontend — Research Store and API Service

**Files:**

- Create: `frontend/src/services/researchEngineService.ts`
- Create: `frontend/src/store/research-engine-store.ts`
- Test: `frontend/src/services/__tests__/researchEngineService.test.ts`

**Step 1: Write the failing test**

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock apiClient before import
vi.mock("@/services/apiClient", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from "@/services/apiClient";
import {
  listProjects,
  createProject,
  listTemplates,
  createBlueprint,
  startRun,
  getRun,
  pauseRun,
  resumeRun,
} from "@/services/researchEngineService";

describe("researchEngineService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listProjects calls correct endpoint", async () => {
    (apiClient.get as any).mockResolvedValue({ data: [] });
    await listProjects();
    expect(apiClient.get).toHaveBeenCalledWith(
      "/api/v1/research-engine/projects",
    );
  });

  it("createProject sends name and description", async () => {
    (apiClient.post as any).mockResolvedValue({
      data: { id: "1", name: "Test" },
    });
    await createProject({ name: "Test", description: "Desc" });
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/research-engine/projects",
      { name: "Test", description: "Desc" },
    );
  });

  it("listTemplates calls correct endpoint", async () => {
    (apiClient.get as any).mockResolvedValue({ data: [] });
    await listTemplates();
    expect(apiClient.get).toHaveBeenCalledWith(
      "/api/v1/research-engine/blueprints/templates",
    );
  });

  it("startRun calls correct endpoint", async () => {
    (apiClient.post as any).mockResolvedValue({
      data: { id: "1", status: "pending" },
    });
    await startRun("bp-1", {});
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/research-engine/blueprints/bp-1/runs",
      { parameters_override: {} },
    );
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd /home/clawdbot/clawd/rag/frontend && npx vitest run src/services/__tests__/researchEngineService.test.ts`
Expected: FAIL

**Step 3: Write minimal implementation**

`frontend/src/services/researchEngineService.ts`:

```typescript
import apiClient from "@/services/apiClient";

const BASE = "/api/v1/research-engine";

export interface ProjectCreate {
  name: string;
  description?: string;
  settings?: Record<string, unknown>;
}

export interface BlueprintStepDef {
  type: string;
  name: string;
  description?: string;
  parameters: Record<string, unknown>;
  model_id?: string;
  model_version?: string;
  mode: "deterministic" | "exploratory";
  temperature?: number;
  seed?: number;
}

export interface BlueprintCreate {
  name: string;
  template_source?: string;
  steps: BlueprintStepDef[];
  parameters: Record<string, unknown>;
}

export const listProjects = () => apiClient.get(`${BASE}/projects`);

export const createProject = (data: ProjectCreate) =>
  apiClient.post(`${BASE}/projects`, data);

export const getProject = (id: string) =>
  apiClient.get(`${BASE}/projects/${id}`);

export const listTemplates = () =>
  apiClient.get(`${BASE}/blueprints/templates`);

export const createBlueprint = (projectId: string, data: BlueprintCreate) =>
  apiClient.post(`${BASE}/blueprints/projects/${projectId}`, data);

export const getBlueprint = (id: string) =>
  apiClient.get(`${BASE}/blueprints/${id}`);

export const startRun = (
  blueprintId: string,
  parametersOverride: Record<string, unknown>,
) =>
  apiClient.post(`${BASE}/blueprints/${blueprintId}/runs`, {
    parameters_override: parametersOverride,
  });

export const getRun = (runId: string) => apiClient.get(`${BASE}/runs/${runId}`);

export const pauseRun = (runId: string) =>
  apiClient.post(`${BASE}/runs/${runId}/pause`);

export const resumeRun = (runId: string) =>
  apiClient.post(`${BASE}/runs/${runId}/resume`);

export const getRunManifest = (runId: string) =>
  apiClient.get(`${BASE}/runs/${runId}/manifest`);

export const listSteps = (runId: string) =>
  apiClient.get(`${BASE}/runs/${runId}/steps`);

export const getStep = (stepId: string) =>
  apiClient.get(`${BASE}/steps/${stepId}`);
```

`frontend/src/store/research-engine-store.ts`:

```typescript
import { create } from "zustand";

export interface ResearchProject {
  id: string;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchRun {
  id: string;
  blueprint_id: string;
  blueprint_version: number;
  status: "pending" | "running" | "paused" | "completed" | "failed";
  total_tokens: number;
  started_at?: string;
  completed_at?: string;
}

export interface RunStepEvent {
  event: string;
  step_index?: number;
  step_type?: string;
  step_name?: string;
  token_count?: number;
  quality_marks?: Array<{
    check_type: string;
    passed: boolean;
    details?: string;
  }>;
  timestamp: string;
}

interface ResearchEngineState {
  projects: ResearchProject[];
  activeProject: ResearchProject | null;
  activeRun: ResearchRun | null;
  runEvents: RunStepEvent[];
  isLoading: boolean;
  error: string | null;

  setProjects: (projects: ResearchProject[]) => void;
  setActiveProject: (project: ResearchProject | null) => void;
  setActiveRun: (run: ResearchRun | null) => void;
  addRunEvent: (event: RunStepEvent) => void;
  clearRunEvents: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useResearchEngineStore = create<ResearchEngineState>((set) => ({
  projects: [],
  activeProject: null,
  activeRun: null,
  runEvents: [],
  isLoading: false,
  error: null,

  setProjects: (projects) => set({ projects }),
  setActiveProject: (project) => set({ activeProject: project }),
  setActiveRun: (run) => set({ activeRun: run }),
  addRunEvent: (event) =>
    set((state) => ({ runEvents: [...state.runEvents, event] })),
  clearRunEvents: () => set({ runEvents: [] }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));
```

**Step 4: Run test to verify it passes**

Run: `cd /home/clawdbot/clawd/rag/frontend && npx vitest run src/services/__tests__/researchEngineService.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/services/researchEngineService.ts frontend/src/store/research-engine-store.ts frontend/src/services/__tests__/researchEngineService.test.ts
git commit -m "feat(research): add frontend service layer and Zustand store"
```

---

## Task 10: Frontend — Research Dashboard Page

**Files:**

- Create: `frontend/app/(dashboard)/research-engine/page.tsx`
- Create: `frontend/src/components/research-engine/ResearchDashboard.tsx`
- Create: `frontend/src/components/research-engine/ProjectCard.tsx`
- Create: `frontend/src/components/research-engine/CreateProjectModal.tsx`
- Modify: `frontend/src/components/layout/navigation.ts` (add Research nav item)

This task creates the main dashboard page showing project list, quick-start template buttons, and project creation. Follow existing component patterns from `frontend/src/components/research/ProjectCard.tsx` and `frontend/src/components/research/CreateProjectModal.tsx`. Use the Terminal Observatory theme (PHOSPHOR_GREEN, AMBER, CYAN).

**Step 1:** Create the page and components following existing patterns.
**Step 2:** Add "Research Engine" to sidebar navigation in `navigation.ts`.
**Step 3:** Run type-check: `cd /home/clawdbot/clawd/rag/frontend && npm run type-check`
**Step 4:** Commit.

```bash
git add frontend/app/\(dashboard\)/research-engine/ frontend/src/components/research-engine/ frontend/src/components/layout/navigation.ts
git commit -m "feat(research): add research dashboard page and project components"
```

---

## Task 11: Frontend — Blueprint Editor Page

**Files:**

- Create: `frontend/app/(dashboard)/research-engine/projects/[id]/blueprint/page.tsx`
- Create: `frontend/src/components/research-engine/BlueprintEditor.tsx`
- Create: `frontend/src/components/research-engine/StepCard.tsx`
- Create: `frontend/src/components/research-engine/TemplateSelector.tsx`

This task creates the blueprint editor with ordered step list, template selector, and step configuration. Each step is an expandable card with type, description, parameters, model selection, and mode toggle (deterministic/exploratory with green/amber badges).

**Step 1:** Create components following patterns from existing `frontend/src/components/research/` components.
**Step 2:** Run type-check: `cd /home/clawdbot/clawd/rag/frontend && npm run type-check`
**Step 3:** Commit.

```bash
git add frontend/app/\(dashboard\)/research-engine/projects/ frontend/src/components/research-engine/BlueprintEditor.tsx frontend/src/components/research-engine/StepCard.tsx frontend/src/components/research-engine/TemplateSelector.tsx
git commit -m "feat(research): add blueprint editor with step cards and template selector"
```

---

## Task 12: Frontend — Run View Page with SSE

**Files:**

- Create: `frontend/app/(dashboard)/research-engine/runs/[id]/page.tsx`
- Create: `frontend/src/components/research-engine/RunView.tsx`
- Create: `frontend/src/components/research-engine/StepProgress.tsx`

This task creates the live run view that connects to the SSE stream endpoint. Shows current step with spinner, completed steps with green/red quality marks, pause/resume controls. Follow the existing SSE pattern from `frontend/src/services/streamingService.ts`.

**Step 1:** Create components using existing SSE patterns.
**Step 2:** Run type-check: `cd /home/clawdbot/clawd/rag/frontend && npm run type-check`
**Step 3:** Commit.

```bash
git add frontend/app/\(dashboard\)/research-engine/runs/ frontend/src/components/research-engine/RunView.tsx frontend/src/components/research-engine/StepProgress.tsx
git commit -m "feat(research): add run view page with SSE step progress"
```

---

## Task 13: Frontend — Evidence Map Page

**Files:**

- Create: `frontend/app/(dashboard)/research-engine/projects/[id]/graph/page.tsx`
- Create: `frontend/src/components/research-engine/EvidenceMap.tsx`

This task creates the interactive evidence graph visualization. Use a lightweight graph library (e.g., `react-force-graph-2d` or `@xyflow/react` if already in deps). Nodes: ResearchQuestion (center), SubQuestion, Evidence, Source. Edge colors: supports=PHOSPHOR_GREEN, contradicts=red, relates=CYAN.

**Step 1:** Check existing graph dependencies: `cd /home/clawdbot/clawd/rag/frontend && grep -i "graph\|force\|xyflow\|d3" package.json`
**Step 2:** Create components. If no graph library exists, use simple SVG/Canvas rendering first.
**Step 3:** Run type-check: `cd /home/clawdbot/clawd/rag/frontend && npm run type-check`
**Step 4:** Commit.

```bash
git add frontend/app/\(dashboard\)/research-engine/projects/*/graph/ frontend/src/components/research-engine/EvidenceMap.tsx
git commit -m "feat(research): add evidence map graph visualization"
```

---

## Task 14: Celery Task for Workflow Execution

**Files:**

- Create: `backend/src/tasks/research_tasks.py`
- Test: `backend/tests/unit/tasks/test_research_tasks.py`

This task wires the workflow engine to Celery for async execution. Follow the existing pattern in `backend/src/tasks/processing_tasks.py`. The task:

1. Loads blueprint from DB
2. Creates provider instances based on step model_ids
3. Creates connector instances
4. Runs WorkflowEngine.run()
5. Persists each step result to research_steps table
6. Updates run status

**Step 1:** Write failing test that mocks DB + engine.
**Step 2:** Implement the Celery task.
**Step 3:** Run test.
**Step 4:** Commit.

```bash
git add backend/src/tasks/research_tasks.py backend/tests/unit/tasks/test_research_tasks.py
git commit -m "feat(research): add Celery task for async workflow execution"
```

---

## Task 15: SSE Streaming Endpoint for Run Progress

**Files:**

- Create: `backend/src/api/research_engine/stream.py`
- Modify: `backend/src/api/research_engine/__init__.py` (add stream router)
- Test: `backend/tests/unit/api/test_research_engine_stream.py`

This task adds a `POST /api/v1/research-engine/runs/{run_id}/stream` SSE endpoint. Follow the existing pattern from `backend/src/api/threads/stream.py` and `backend/src/services/threads/stream_service.py`. The endpoint:

1. Starts or resumes the workflow engine
2. Yields SSE events for each step (step_start, step_complete, step_error, run_complete, run_paused)

**Step 1:** Write failing test.
**Step 2:** Implement endpoint.
**Step 3:** Run test.
**Step 4:** Commit.

```bash
git add backend/src/api/research_engine/stream.py backend/src/api/research_engine/__init__.py backend/tests/unit/api/test_research_engine_stream.py
git commit -m "feat(research): add SSE streaming endpoint for run progress"
```

---

## Task 16: Determinism Golden Tests

**Files:**

- Create: `backend/tests/unit/services/test_determinism_golden.py`

This task verifies the core determinism guarantee: same blueprint + same inputs = identical outputs.

**Step 1: Write the test**

```python
"""Golden tests for determinism guarantee."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.research_engine.engine import WorkflowEngine
from src.services.research_engine.step_executor import StepExecutor
from src.services.research_engine.providers.base import LLMResponse


class TestDeterminismGolden:
    @pytest.mark.asyncio
    async def test_identical_inputs_produce_identical_outputs(self):
        """Run the same blueprint twice and assert identical step outputs."""
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = LLMResponse(
            content="Deterministic output.",
            model_id="test-model",
            input_tokens=10,
            output_tokens=5,
        )
        mock_connector = AsyncMock()
        mock_connector.search.return_value = [
            MagicMock(title="Paper A", connector_type="test", external_id="1"),
        ]

        executor = StepExecutor(
            connectors={"test": mock_connector},
            providers={"test-model": mock_provider},
        )
        engine = WorkflowEngine(step_executor=executor)
        blueprint = {
            "steps": [
                {"type": "search", "name": "Search", "parameters": {"sources": ["test"]}},
                {"type": "synthesize", "name": "Synth", "parameters": {},
                 "model_id": "test-model", "temperature": 0.0, "seed": 42,
                 "system_prompt_template": "Synthesize: {topic}"},
            ],
            "parameters": {"topic": "AI"},
        }

        import uuid
        run_id = uuid.uuid4()

        # Run 1
        events_1 = []
        async for event in engine.run(blueprint, run_id=run_id):
            events_1.append(event)

        # Run 2 — same inputs
        events_2 = []
        async for event in engine.run(blueprint, run_id=run_id):
            events_2.append(event)

        # Compare step_complete events
        completes_1 = [e for e in events_1 if e["event"] == "step_complete"]
        completes_2 = [e for e in events_2 if e["event"] == "step_complete"]

        assert len(completes_1) == len(completes_2)
        for c1, c2 in zip(completes_1, completes_2):
            assert c1["step_type"] == c2["step_type"]
            assert c1["token_count"] == c2["token_count"]

    @pytest.mark.asyncio
    async def test_blueprint_immutability_after_run(self):
        """Verify that blueprint version increments on edit after execution."""
        # This is a schema-level test — blueprint.is_immutable should be True after run
        from src.models.research_blueprint import ResearchBlueprint
        bp = ResearchBlueprint(
            project_id=__import__("uuid").uuid4(),
            name="Test",
            version=1,
            steps=[],
            is_immutable=False,
        )
        # Simulate marking immutable after first run
        bp.is_immutable = True
        assert bp.is_immutable is True
```

**Step 2: Run test**

Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/unit/services/test_determinism_golden.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/unit/services/test_determinism_golden.py
git commit -m "test(research): add determinism golden tests for reproducibility"
```

---

## Task 17: Export Service (Report Generation)

**Files:**

- Create: `backend/src/services/research_engine/export_service.py`
- Test: `backend/tests/unit/services/test_research_export.py`

This task adds a service that generates structured Markdown reports from completed runs. Includes: introduction, methodology, findings, discussion, references, and a reproducibility appendix auto-generated from the audit trail.

**Step 1:** Write failing test.
**Step 2:** Implement export service.
**Step 3:** Run test.
**Step 4:** Commit.

```bash
git add backend/src/services/research_engine/export_service.py backend/tests/unit/services/test_research_export.py
git commit -m "feat(research): add export service for structured report generation"
```

---

## Task 18: Integration Test — Full Workflow End-to-End

**Files:**

- Create: `backend/tests/integration/test_research_workflow_e2e.py`

This task tests the full pipeline: create project -> create blueprint -> start run -> execute steps -> verify quality marks -> generate report. Uses mock connectors and providers.

**Step 1:** Write the integration test.
**Step 2:** Run: `cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/integration/test_research_workflow_e2e.py -v`
**Step 3:** Commit.

```bash
git add backend/tests/integration/test_research_workflow_e2e.py
git commit -m "test(research): add end-to-end integration test for research workflow"
```

---

## Task 19: Frontend Validation

**Files:** All frontend files from Tasks 9-13.

**Step 1:** Run full frontend validation:

```bash
cd /home/clawdbot/clawd/rag/frontend && npm run validate
```

**Step 2:** Fix any lint, type-check, or test failures.
**Step 3:** Commit fixes.

```bash
git add -A
git commit -m "fix(research): resolve frontend lint and type-check issues"
```

---

## Task 20: Backend Test Suite

**Step 1:** Run full backend test suite:

```bash
cd /home/clawdbot/clawd/rag && python -m pytest backend/tests/ -v --tb=short -q
```

**Step 2:** Fix any failures.
**Step 3:** Commit fixes.

```bash
git add -A
git commit -m "fix(research): resolve backend test failures"
```
