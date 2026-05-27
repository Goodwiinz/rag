"""Tests for LLM entity extraction service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.entity import EntityType
from src.services.processing.llm_entity_extraction import (
    ExtractedEntity,
    LLMEntityExtractionService,
    chunk_text,
    map_to_entity_type,
    merge_entities,
    parse_llm_response,
)


class TestChunkText:
    def test_small_doc_single_chunk(self):
        """Document under token limit returns single chunk."""
        text = "This is a short document about transformers."
        chunks = chunk_text(text, max_tokens=4000, overlap_tokens=200)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_on_paragraph_boundaries(self):
        """Chunks split at double-newline paragraph breaks."""
        para1 = "First paragraph. " * 200  # ~400 tokens
        para2 = "Second paragraph. " * 200
        para3 = "Third paragraph. " * 200
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunk_text(text, max_tokens=500, overlap_tokens=50)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert not chunk.startswith(" ")

    def test_overlap_between_chunks(self):
        """Adjacent chunks share overlapping text."""
        # Use many small paragraphs so overlap can carry whole paragraphs
        paragraphs = [f"Paragraph {i} content. " * 20 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, max_tokens=300, overlap_tokens=100)
        assert len(chunks) >= 3
        for i in range(len(chunks) - 1):
            tail = chunks[i][-50:]
            assert tail in chunks[i + 1] or chunks[i + 1][:100] in chunks[i]

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("", max_tokens=4000, overlap_tokens=200)
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n  ", max_tokens=4000, overlap_tokens=200)
        assert chunks == []


class TestMergeEntities:
    def test_deduplicates_by_canonical_name(self):
        """Same canonical name from different chunks merges into one."""
        e1 = ExtractedEntity(
            name="LoopMDM", type="MODEL", canonical_name="loopmdm", confidence=0.9
        )
        e2 = ExtractedEntity(
            name="Loop MDM",
            type="MODEL",
            canonical_name="loopmdm",
            confidence=0.95,
        )
        result = merge_entities([e1, e2])
        assert len(result) == 1
        assert result[0].confidence == 0.95  # highest wins

    def test_combines_aliases(self):
        """Aliases from duplicate entities are merged."""
        e1 = ExtractedEntity(
            name="GPT-4",
            type="MODEL",
            canonical_name="gpt-4",
            aliases=["GPT4"],
        )
        e2 = ExtractedEntity(
            name="GPT-4",
            type="MODEL",
            canonical_name="gpt-4",
            aliases=["gpt-4o"],
        )
        result = merge_entities([e1, e2])
        assert len(result) == 1
        assert set(result[0].aliases) >= {"GPT4", "gpt-4o"}

    def test_first_nonempty_description_wins(self):
        e1 = ExtractedEntity(
            name="BERT", type="MODEL", canonical_name="bert", description=""
        )
        e2 = ExtractedEntity(
            name="BERT",
            type="MODEL",
            canonical_name="bert",
            description="Bidirectional encoder",
        )
        result = merge_entities([e1, e2])
        assert result[0].description == "Bidirectional encoder"

    def test_different_entities_not_merged(self):
        e1 = ExtractedEntity(name="BERT", type="MODEL", canonical_name="bert")
        e2 = ExtractedEntity(
            name="Berkeley", type="ORGANIZATION", canonical_name="berkeley"
        )
        result = merge_entities([e1, e2])
        assert len(result) == 2

    def test_empty_input(self):
        assert merge_entities([]) == []


class TestParseLLMResponse:
    def test_valid_json(self):
        raw = json.dumps({
            "entities": [
                {
                    "name": "LoopMDM",
                    "type": "MODEL",
                    "canonical_name": "loopmdm",
                    "description": "Looped Masked Diffusion Model",
                    "confidence": 0.95,
                    "aliases": ["Loop MDM"],
                }
            ]
        })
        entities = parse_llm_response(raw)
        assert len(entities) == 1
        assert entities[0].name == "LoopMDM"
        assert entities[0].type == "MODEL"
        assert entities[0].confidence == 0.95

    def test_malformed_json_returns_empty(self):
        entities = parse_llm_response("not json {{{")
        assert entities == []

    def test_json_wrapped_in_markdown_code_block(self):
        raw = '```json\n{"entities": [{"name": "BERT", "type": "MODEL"}]}\n```'
        entities = parse_llm_response(raw)
        assert len(entities) == 1
        assert entities[0].name == "BERT"

    def test_missing_fields_use_defaults(self):
        raw = json.dumps({"entities": [{"name": "GPT-4", "type": "MODEL"}]})
        entities = parse_llm_response(raw)
        assert len(entities) == 1
        assert entities[0].confidence == 0.8
        assert entities[0].aliases == []
        assert entities[0].canonical_name == "gpt-4"

    def test_empty_entities_array(self):
        raw = json.dumps({"entities": []})
        entities = parse_llm_response(raw)
        assert entities == []


class TestEntityTypeMapping:
    def test_direct_mappings(self):
        assert map_to_entity_type("PERSON") == EntityType.PERSON
        assert map_to_entity_type("ORGANIZATION") == EntityType.ORGANIZATION
        assert map_to_entity_type("CONCEPT") == EntityType.CONCEPT
        assert map_to_entity_type("TECHNOLOGY") == EntityType.TECHNOLOGY
        assert map_to_entity_type("RESEARCH") == EntityType.RESEARCH

    def test_alias_mappings(self):
        assert map_to_entity_type("MODEL") == EntityType.PRODUCT
        assert map_to_entity_type("DATASET") == EntityType.PRODUCT
        assert map_to_entity_type("METRIC") == EntityType.NUMBER
        assert map_to_entity_type("METHOD") == EntityType.CONCEPT

    def test_unknown_type_returns_custom(self):
        assert map_to_entity_type("UNKNOWN_THING") == EntityType.CUSTOM

    def test_case_insensitive(self):
        assert map_to_entity_type("person") == EntityType.PERSON
        assert map_to_entity_type("Model") == EntityType.PRODUCT


def _mock_llm_response(entities: list[dict]) -> MagicMock:
    """Build a mock LLM response with .content containing JSON."""
    mock = MagicMock()
    mock.content = json.dumps({"entities": entities})
    return mock


class TestLLMEntityExtractionService:
    @pytest.fixture
    def service(self):
        with patch(
            "src.services.processing.llm_entity_extraction.build_lightweight_llm"
        ) as mock_build:
            mock_llm = AsyncMock()
            mock_build.return_value = mock_llm
            svc = LLMEntityExtractionService()
            svc._llm = mock_llm
            svc._breaker.reset()
            yield svc, mock_llm

    @pytest.mark.asyncio
    async def test_extract_entities_full_pipeline(self, service):
        svc, mock_llm = service
        mock_llm.ainvoke.return_value = _mock_llm_response([
            {"name": "LoopMDM", "type": "MODEL", "confidence": 0.95},
            {"name": "Berkeley", "type": "ORGANIZATION", "confidence": 0.9},
        ])

        result = await svc.extract_entities("Short document about LoopMDM at Berkeley.")
        assert len(result.entities) == 2
        assert result.entities[0].name == "LoopMDM"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_partial_results_on_chunk_failure(self, service):
        svc, mock_llm = service
        good_response = _mock_llm_response([
            {"name": "BERT", "type": "MODEL", "confidence": 0.9}
        ])
        mock_llm.ainvoke.side_effect = [
            good_response,
            Exception("API timeout"),
            good_response,
        ]

        text = "\n\n".join([f"Paragraph {i}. " * 200 for i in range(30)])
        result = await svc.extract_entities(text, max_tokens_per_chunk=300)
        assert len(result.entities) >= 1
        assert result.error is None  # partial success is not an error

    @pytest.mark.asyncio
    async def test_entity_types_filter(self, service):
        svc, mock_llm = service
        mock_llm.ainvoke.return_value = _mock_llm_response([
            {"name": "BERT", "type": "MODEL", "confidence": 0.9}
        ])
        result = await svc.extract_entities(
            "BERT is a model.",
            entity_types=["MODEL", "METHOD"],
        )
        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]
        system_msg = messages[0].content
        assert "MODEL" in system_msg
        assert "METHOD" in system_msg
        assert "PERSON" not in system_msg

    @pytest.mark.asyncio
    async def test_all_chunks_fail_returns_empty(self, service):
        svc, mock_llm = service
        mock_llm.ainvoke.side_effect = Exception("All calls fail")
        result = await svc.extract_entities("Some text.")
        assert result.entities == []
        assert result.error is not None
