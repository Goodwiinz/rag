"""
ArXiv Knowledge Graph Integration Service

This service enhances arXiv paper ingestion by extracting entities and relationships
and adding them to the knowledge graph for better semantic search and understanding.
"""

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar

from src.models.document import DocumentType
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.shared.schemas import ProcessingStatus

from .arxiv_service import ArXivIngestionService

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ArXivKnowledgeGraphIntegration:
    """
    Service for integrating arXiv papers with the knowledge graph

    Features:
    - Extract entities from titles and abstracts
    - Identify relationships between papers, authors, and concepts
    - Create nodes and edges in the knowledge graph
    - Support for citation detection and network analysis
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.arxiv_service = ArXivIngestionService(config)
        self.kg_service = None  # Will be initialized when needed

    async def __aenter__(self):
        """Async context manager entry"""
        self.arxiv_service = await self.arxiv_service.__aenter__()

        # Try to import and initialize knowledge graph service
        try:
            from src.services.knowledge_graph import KnowledgeGraphService

            self.kg_service = KnowledgeGraphService()
            # Test connection using the class attribute
            if KnowledgeGraphService._driver_instance:
                logger.info("Knowledge graph service initialized successfully")
            else:
                # Sync driver I/O must not run on the event loop.
                await asyncio.to_thread(self._probe_kg_connection)
                logger.info("Knowledge graph service initialized successfully")
        except Exception as e:
            # Loud, not silent. Swallowing this left kg_service=None, and every
            # caller then either skipped all KG writes or AttributeError'd per
            # paper into a swallowed log — "success" while writing nothing.
            logger.error(
                f"Failed to initialize knowledge graph service: {e}", exc_info=True
            )
            self.kg_service = None
            await self.arxiv_service.__aexit__(type(e), e, e.__traceback__)
            raise RuntimeError(f"Knowledge graph service unavailable: {e}") from e

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.arxiv_service.__aexit__(exc_type, exc_val, exc_tb)

        if self.kg_service:
            await self.kg_service.__aexit__(exc_type, exc_val, exc_tb)

    async def ingest_papers_with_kg(
        self,
        papers: List[Dict[str, Any]],
        extract_entities: bool = True,
        create_relationships: bool = True,
        **kwargs,
    ) -> List[Any]:
        """
        Ingest papers into both document store and knowledge graph

        Args:
            papers: List of paper metadata
            extract_entities: Whether to extract entities from papers
            create_relationships: Whether to create relationships between papers
            **kwargs: Additional arguments for ingestion

        Returns:
            List of processed documents
        """
        logger.info(f"Ingesting {len(papers)} papers with knowledge graph integration")
        logger.info(f"Entity extraction: {extract_entities}")
        logger.info(f"Relationship creation: {create_relationships}")

        # First ingest papers normally
        documents = await self.arxiv_service.ingest_papers(
            papers=papers,
            download_pdfs=kwargs.get("download_pdfs", True),
            extract_content=kwargs.get("extract_content", True),
            batch_size=kwargs.get("batch_size", 10),
        )

        # Process each paper for knowledge graph. Correlate papers to their
        # ingested documents by arXiv id — NOT positionally. ingest_papers
        # drops failed papers from its result list, so zip(papers, documents)
        # shifted every subsequent paper onto a foreign document and stamped
        # the KG with another paper's metadata.
        if self.kg_service and (extract_entities or create_relationships):
            docs_by_arxiv_id = {}
            for doc in documents:
                key = self._document_arxiv_id(doc)
                if key:
                    docs_by_arxiv_id[key] = doc
                else:
                    logger.warning(
                        "Skipping unidentifiable ingested document in KG pass "
                        "(no arxiv_id in metadata)"
                    )
            for i, paper in enumerate(papers):
                doc = docs_by_arxiv_id.get(paper.get("id"))
                if doc is None:
                    logger.warning(
                        f"Skipping KG processing for paper {paper.get('id')}: "
                        "no successfully ingested document matches it"
                    )
                    continue
                try:
                    logger.info(
                        f"Processing paper {i+1}/{len(papers)} for knowledge graph: {paper['title'][:50]}..."
                    )
                    # SimpleDocument from arxiv ingest carries no org, so fall
                    # back to an explicit organization_id kwarg when the caller
                    # supplies one. (This method currently has no live caller;
                    # the kwarg keeps it correct if it is wired up later.)
                    doc_org_id = (
                        str(doc.organization_id)
                        if getattr(doc, "organization_id", None)
                        else kwargs.get("organization_id")
                    )

                    # Extract entities
                    if extract_entities:
                        entities = await self._extract_entities_from_paper(paper)
                        logger.info(f"Extracted {len(entities)} entities")

                        # Add entities to knowledge graph
                        for entity in entities:
                            await self._add_entity_to_kg(
                                entity, paper, organization_id=doc_org_id
                            )

                    # Create relationships
                    if create_relationships:
                        # The paper-title node is referenced by author_of /
                        # belongs_to / cites edges but is never an extracted
                        # entity — without it every one of those edges was
                        # silently dropped. Create it (idempotent MERGE) first.
                        await self._ensure_paper_title_entity(
                            paper, organization_id=doc_org_id
                        )
                        # Pass extracted entities to relationship extraction for context
                        relationships = await self._extract_relationships_from_paper(
                            paper, entities if extract_entities else None
                        )
                        logger.info(f"Extracted {len(relationships)} relationships")

                        # Add relationships to knowledge graph
                        for rel in relationships:
                            await self._add_relationship_to_kg(
                                rel, paper, organization_id=doc_org_id
                            )

                except Exception as e:
                    logger.error(f"Failed to process paper for KG: {e}")
                    import traceback

                    traceback.print_exc()

        return documents

    async def _extract_entities_from_paper(
        self, paper: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from paper title and abstract

        Args:
            paper: Paper metadata

        Returns:
            List of extracted entities
        """
        entities = []
        text = f"{paper['title']} {paper['abstract']}"

        # Extract common patterns
        entities.extend(self._extract_technical_terms(text))
        entities.extend(self._extract_authors_as_entities(paper))
        entities.extend(self._extract_categories(paper))
        entities.extend(self._extract_affiliations(paper))
        # Removed regex-based concept/method extraction to prevent sentence fragment extraction
        # entities.extend(self._extract_concepts(text))
        entities.extend(self._extract_datasets(text))
        # entities.extend(self._extract_methods(text))

        # LLM Extraction
        llm_entities = await self._extract_entities_with_llm(text)
        entities.extend(llm_entities)

        # Remove duplicates and add confidence scores
        unique_entities = {}
        for entity in entities:
            key = entity["text"].lower().strip()
            if (
                key not in unique_entities
                or entity["confidence"] > unique_entities[key]["confidence"]
            ):
                unique_entities[key] = entity

        return list(unique_entities.values())

    def _extract_technical_terms(self, text: str) -> List[Dict[str, Any]]:
        """Extract technical terms and acronyms"""
        entities = []

        # Common ML/AI terms
        technical_terms = {
            "Transformer": {"type": "model", "confidence": 0.9},
            "BERT": {"type": "model", "confidence": 0.9},
            "GPT": {"type": "model", "confidence": 0.9},
            "LSTM": {"type": "model", "confidence": 0.9},
            "RNN": {"type": "model", "confidence": 0.9},
            "CNN": {"type": "model", "confidence": 0.9},
            "GAN": {"type": "model", "confidence": 0.9},
            "SVM": {"type": "model", "confidence": 0.9},
            "Attention": {"type": "mechanism", "confidence": 0.85},
            "Backpropagation": {"type": "method", "confidence": 0.85},
            "Gradient Descent": {"type": "method", "confidence": 0.85},
            "Adam": {"type": "optimizer", "confidence": 0.85},
            "SGD": {"type": "optimizer", "confidence": 0.85},
            "Dropout": {"type": "technique", "confidence": 0.8},
            "Batch Normalization": {"type": "technique", "confidence": 0.8},
            "ReLU": {"type": "activation", "confidence": 0.8},
            "Softmax": {"type": "activation", "confidence": 0.8},
            "Embedding": {"type": "technique", "confidence": 0.8},
        }

        # Find terms
        for term, info in technical_terms.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(
                    {
                        "text": term,
                        "type": info["type"],
                        "confidence": info["confidence"],
                        "source": "technical_terms",
                        "extraction_method": "pattern_matching",
                    }
                )

        return entities

    def _extract_authors_as_entities(
        self, paper: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract authors as entities"""
        entities = []

        for author in paper.get("authors", []):
            # Extract last name for entity disambiguation
            name_parts = author.split()
            if len(name_parts) >= 2:
                # Use full name as the primary entity text
                entities.append(
                    {
                        "text": author,
                        "full_name": author,
                        "type": "author",
                        "confidence": 0.95,
                        "source": "paper_authors",
                        "extraction_method": "rule_based",
                    }
                )
            elif len(name_parts) == 1:
                entities.append(
                    {
                        "text": author,
                        "full_name": author,
                        "type": "author",
                        "confidence": 0.9,
                        "source": "paper_authors",
                        "extraction_method": "rule_based",
                    }
                )

        return entities

    def _extract_categories(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract arXiv categories as entities"""
        entities = []

        for category in paper.get("categories", []):
            # Map category to full name
            category_mapping = self._get_category_mapping(category)

            entities.append(
                {
                    "text": category,
                    "full_name": category_mapping.get("full_name", category),
                    "field": category_mapping.get("field", "Unknown"),
                    "confidence": 1.0,
                    "type": "category",
                    "source": "arxiv_category",
                    "extraction_method": "manual",
                }
            )

        return entities

    def _extract_affiliations(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract affiliations (Schools, Labs) from paper metadata"""
        entities = []

        # Check if detailed author info is available
        for author_info in paper.get("authors_detailed", []):
            for affiliation in author_info.get("affiliations", []):
                if affiliation:
                    entities.append(
                        {
                            "text": affiliation,
                            "type": "institution",
                            "confidence": 1.0,
                            "source": "paper_metadata",
                            # Must be a valid ExtractionMethod member —
                            # "metadata" is not one, and the resulting pydantic
                            # ValidationError was swallowed in _add_entity_to_kg,
                            # silently dropping every institution entity (and
                            # its AFFILIATED_WITH relationship).
                            "extraction_method": "rule_based",
                        }
                    )

        return entities

    def _get_category_mapping(self, category: str) -> Dict[str, str]:
        """Get mapping from arXiv category to full name"""
        mappings = {
            # Computer Science
            "cs.AI": {
                "full_name": "Artificial Intelligence",
                "field": "Computer Science",
            },
            "cs.LG": {"full_name": "Machine Learning", "field": "Computer Science"},
            "cs.CL": {
                "full_name": "Computation and Language",
                "field": "Computer Science",
            },
            "cs.CV": {"full_name": "Computer Vision", "field": "Computer Science"},
            "cs.RO": {"full_name": "Robotics", "field": "Computer Science"},
            "cs.IR": {
                "full_name": "Information Retrieval",
                "field": "Computer Science",
            },
            "cs.NE": {
                "full_name": "Neural and Evolutionary Computing",
                "field": "Computer Science",
            },
            # Mathematics
            "math.ML": {"full_name": "Machine Learning", "field": "Mathematics"},
            "math.ST": {"full_name": "Statistics Theory", "field": "Mathematics"},
            "math.OC": {
                "full_name": "Optimization and Control",
                "field": "Mathematics",
            },
            # Physics
            "quant-ph": {"full_name": "Quantum Physics", "field": "Physics"},
            "cond-mat": {"full_name": "Condensed Matter", "field": "Physics"},
            "astro-ph": {"full_name": "Astrophysics", "field": "Physics"},
            # Statistics
            "stat.ML": {"full_name": "Machine Learning", "field": "Statistics"},
            "stat.ME": {"full_name": "Methodology", "field": "Statistics"},
            "stat.TH": {"full_name": "Theory", "field": "Statistics"},
        }

        return mappings.get(category, {"full_name": category, "field": "Unknown"})

    def _extract_concepts(self, text: str) -> List[Dict[str, Any]]:
        """Extract abstract concepts and ideas with context-aware boundaries"""
        entities = []

        # Look for concept indicators
        concept_patterns = [
            (
                r"\b(objective|goal|contribution|novelty|innovation|advancement)\b",
                "concept",
            ),
            (r"\b(approach|methodology|framework|architecture|paradigm)\b", "method"),
            (r"\b(performance|accuracy|efficiency|scalability|robustness)\b", "metric"),
            (
                r"\b(limitation|drawback|challenge|future work|open problem)\b",
                "concept",
            ),
        ]

        for pattern, entity_type in concept_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get context with word boundaries
                context = self._get_context_with_boundaries(
                    text, match.start(), match.end()
                )

                if context:
                    entities.append(
                        {
                            "text": context,
                            "type": entity_type,
                            "confidence": 0.7,
                            "source": "text_pattern",
                            "extraction_method": "pattern_matching",
                        }
                    )

        return entities

    def _extract_dataset_references(self, text: str) -> List[Dict[str, Any]]:
        """Helper to extract datasets (kept previous name for compatibility)"""
        # This was previously _extract_datasets, keeping naming consistent if called externally
        # but locally implementing via improved logic if needed.
        return self._extract_datasets(text)

    def _extract_datasets(self, text: str) -> List[Dict[str, Any]]:
        """Extract dataset names and benchmarks"""
        entities = []

        # Common datasets
        dataset_patterns = [
            r"ImageNet|COCO|SQuAD|GLUE|SuperGLUE",
            r"PASCAL|MNIST|CIFAR-10|CIFAR-100",
            r"WMT|ACL|EMNLP|ICLR|NeurIPS",
            r"SQUAD|TREC|Kaggle|UCI",
        ]

        for pattern in dataset_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities.append(
                    {
                        "text": match.group(),
                        "type": "dataset",
                        "confidence": 0.8,
                        "source": "known_dataset",
                        "extraction_method": "pattern_matching",
                    }
                )

        return entities

    def _extract_methods(self, text: str) -> List[Dict[str, Any]]:
        """Extract methods and algorithms with context-aware boundaries"""
        entities = []

        # Method indicators
        method_patterns = [
            (r"\b(prove|demonstrate|evaluate|validate|benchmark)\b", "method"),
            (r"\b(achieve|obtain|improve|outperform|exceed)\b", "result"),
            (r"\b(state-of-the-art|SOTA|cutting-edge)\b", "comparison"),
            (r"\b(baseline|comparative|ablation)\b", "method"),
        ]

        for pattern, entity_type in method_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get context with word boundaries
                context = self._get_context_with_boundaries(
                    text, match.start(), match.end()
                )

                if context:
                    entities.append(
                        {
                            "text": context,
                            "type": entity_type,
                            "confidence": 0.7,
                            "source": "text_pattern",
                            "extraction_method": "pattern_matching",
                        }
                    )

        return entities

    def _get_context_with_boundaries(
        self, text: str, start_idx: int, end_idx: int, padding: int = 40
    ) -> str:
        """
        Get text context respecting word boundaries.
        Expands left and right from the match indices up to 'padding' characters,
        but stops at the nearest whitespace to avoid cutting words.
        """
        text_len = len(text)

        # Initial expansion
        ctx_start = max(0, start_idx - padding)
        ctx_end = min(text_len, end_idx + padding)

        # Expand start to nearest whitespace (going left) or beginning
        while ctx_start > 0 and not text[ctx_start].isspace():
            ctx_start -= 1
        # If we hit a space, move forward one char to start of word
        if ctx_start > 0:
            ctx_start += 1

        # Expand end to nearest whitespace (going right) or end
        while ctx_end < text_len and not text[ctx_end].isspace():
            ctx_end += 1

        return text[ctx_start:ctx_end].strip()

    async def _extract_entities_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using Azure OpenAI LLM"""
        entities = []
        if not azure_openai_service.is_chat_available():
            return entities

        try:
            prompt = """
            Extract key technical entities from the following text.
            Focus on: Methodologies, Models, Metrics, Tasks, Datasets, Institutions (Schools, Labs), Research Topics.
            
            CRITICAL GUIDELINES:
            1. Extract FULL CANONICAL NAMES where possible. (e.g. "Gradient-Guided Reinforcement Learning" instead of "G2RL").
            2. If an acronym is prominent, you may include it, but prefer the full name.
            3. DO NOT extract sentence fragments, descriptions, or generic terms (e.g. "our proposed method", "state-of-the-art results", "improvements").
            4. Entities must be Noun Phrases.
            
            Return a JSON object with a key "entities" containing a list of objects.
            Each object should have: 
            - "text": The clean, full name of the entity.
            - "type": (one of: method, model, metric, task, dataset, institution, topic, other)
            - "confidence": (0.0-1.0)
            """

            response = await azure_openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": text[:4000],
                    },  # Truncate to avoid context window issues
                ],
                temperature=0.0,
            )

            # Parse JSON
            content = response.get("content", "")
            # Cleanup markdown code blocks if any
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)
            for item in data.get("entities", []):
                entities.append(
                    {
                        "text": item["text"],
                        "type": item["type"],
                        "confidence": item["confidence"],
                        "source": "llm_extraction",
                        "extraction_method": "llm_extraction",
                    }
                )

        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")

        return entities

    async def _extract_relationships_from_paper(
        self, paper: Dict[str, Any], entities: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships from paper, including semantic ones if entities are provided
        """
        relationships = []

        # 1. Author-paper relationships
        for author in paper.get("authors", []):
            relationships.append(
                {
                    "source": {"text": author, "type": "author"},
                    "target": {"text": paper["title"], "type": "paper"},
                    "relation": "author_of",
                    "confidence": 1.0,
                    "extraction_source": "paper_metadata",
                }
            )

        # 1b. Author-Affiliation relationships
        for author_info in paper.get("authors_detailed", []):
            name = author_info["name"]
            for aff in author_info.get("affiliations", []):
                relationships.append(
                    {
                        "source": {"text": name, "type": "author"},
                        "target": {"text": aff, "type": "institution"},
                        "relation": "AFFILIATED_WITH",
                        "confidence": 1.0,
                        "extraction_source": "paper_metadata",
                    }
                )

        # 2. Paper-category relationships
        for category in paper.get("categories", []):
            relationships.append(
                {
                    "source": {"text": paper["title"], "type": "paper"},
                    "target": {"text": category, "type": "category"},
                    "relation": "belongs_to",
                    "confidence": 1.0,
                    "extraction_source": "paper_metadata",
                }
            )

        # 3. Citation relationships
        abstract = paper.get("abstract", "")
        citation_patterns = [
            r"(?:cite|reference|based on|builds upon|extends)\s+([^,.]+)",
            r"previous work[^.]*?\(([^)]+)\)",
            r"(?:as\s+shown\s+in)\s+([^,.]+)",
        ]

        for pattern in citation_patterns:
            matches = re.finditer(pattern, abstract)
            for match in matches:
                cited_paper = match.group(1).strip("()[]")
                if cited_paper:
                    relationships.append(
                        {
                            "source": {"text": paper["title"], "type": "paper"},
                            "target": {"text": cited_paper, "type": "paper"},
                            "relation": "cites",
                            "confidence": 0.8,
                            "extraction_source": "abstract_text",
                        }
                    )

        # 4. LLM Semantic Relationships (New)
        if entities and azure_openai_service.is_chat_available():
            semantic_rels = await self._extract_semantic_relations_with_llm(
                f"{paper['title']}\n{abstract}", entities
            )
            relationships.extend(semantic_rels)

        return relationships

    async def _extract_semantic_relations_with_llm(
        self, text: str, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract semantic relationships using LLM"""
        relationships = []
        try:
            # Filter distinct entity names for context
            entity_names = list(set([e["text"] for e in entities]))

            prompt = """
            Identify semantic relationships between the provided entities based on the text.
            Possible relations: USES, EVALUATED_ON, ACHIEVED, IS_A, COMPARED_WITH, RELATED_TO.
            
            Return a JSON object with a key 'relationships' containing a list of objects.
            Each object must have:
            - source: exact name of the source entity
            - target: exact name of the target entity
            - relation: the relationship type (uppercase)
            - confidence: 0.0-1.0
            
            Only output relationships where BOTH entities appear in the entity list provided.
            """

            user_content = f"""
            Text: {text[:3000]}
            
            Entities: {', '.join(entity_names)}
            """

            response = await azure_openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
            )

            content = response.get("content", "")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            # Map back to required structure
            # We need to look up entity types for the result
            entity_type_map = {e["text"]: e.get("type", "concept") for e in entities}

            for rel in data.get("relationships", []):
                src = rel.get("source")
                tgt = rel.get("target")

                if src in entity_type_map and tgt in entity_type_map:
                    relationships.append(
                        {
                            "source": {"text": src, "type": entity_type_map[src]},
                            "target": {"text": tgt, "type": entity_type_map[tgt]},
                            "relation": rel.get("relation", "RELATED_TO"),
                            "confidence": rel.get("confidence", 0.7),
                            "extraction_source": "llm_semantic",
                        }
                    )

        except Exception as e:
            logger.warning(f"LLM semantic relationship extraction failed: {e}")

        return relationships

    def _probe_kg_connection(self) -> None:
        """Sync connectivity probe — run via asyncio.to_thread only."""
        with self.kg_service.get_session() as session:
            session.run("RETURN 1")

    async def _offload(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a blocking Neo4j driver call in the default thread pool.

        The KnowledgeGraphService driver is synchronous; calling it directly
        from these async methods stalled the whole event loop for every query.
        """
        return await asyncio.to_thread(func, *args, **kwargs)

    @staticmethod
    def _document_arxiv_id(doc: Any) -> Optional[str]:
        """Best-effort arXiv id for an ingested document."""
        metadata = getattr(doc, "metadata", None) or getattr(
            doc, "document_metadata", None
        )
        if isinstance(metadata, dict):
            arxiv_id = metadata.get("arxiv_id")
            if arxiv_id:
                return str(arxiv_id)
        filename = getattr(doc, "filename", None)
        if filename:
            return str(filename).removesuffix(".pdf")
        return None

    @staticmethod
    def _paper_entity_dict(paper: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "text": paper.get("title", ""),
            "type": "paper",
            "confidence": 1.0,
            "source": "paper_metadata",
            "extraction_method": "manual",
        }

    @staticmethod
    def _is_paper_title_endpoint(
        endpoint: Dict[str, Any], paper: Dict[str, Any]
    ) -> bool:
        title = (paper.get("title") or "").strip().lower()
        text = str(endpoint.get("text") or "").strip().lower()
        endpoint_type = str(endpoint.get("type") or "").lower()
        return bool(title) and text == title and endpoint_type == "paper"

    async def _ensure_paper_title_entity(
        self, paper: Dict[str, Any], organization_id: Optional[str] = None
    ) -> bool:
        """Make sure the paper-title node exists before edges reference it.

        create_entity MERGEs on (canonical_key, type, organization_id), so
        re-running this is cheap and idempotent. Returns True if the node
        write succeeded.
        """
        return await self._add_entity_to_kg(
            self._paper_entity_dict(paper), paper, organization_id=organization_id
        )

    async def _resolve_entity_id(
        self,
        name: str,
        organization_id: Optional[str] = None,
        expected_types: Optional[Tuple[str, ...]] = None,
    ) -> Optional[str]:
        """Resolve an entity name to a node id without wiring the wrong node.

        Fulltext search is prefix-based ("Attention" also hits "Attention
        Mechanism"), so an exact case-insensitive name match always wins.
        A non-exact hit is accepted only when it is unambiguous (single
        candidate); anything else is skipped loudly instead of guessing.
        """
        candidates = await self._offload(
            self.kg_service.search_entities,
            query=name,
            limit=5,
            organization_id=organization_id,
        )
        if not candidates:
            return None

        wanted = (name or "").strip().lower()
        exact = [c for c in candidates if c.name.strip().lower() == wanted]
        if exact:
            if len(exact) > 1 and expected_types:
                typed = [c for c in exact if str(c.entity_type) in expected_types]
                if typed:
                    exact = typed
            if len(exact) > 1:
                logger.warning(
                    f"Multiple exact matches for entity {name!r}; using the "
                    f"top-ranked one ({exact[0].id})"
                )
            return exact[0].id

        if len(candidates) == 1:
            logger.debug(
                f"Entity {name!r} resolved via unambiguous prefix match to "
                f"{candidates[0].name!r}"
            )
            return candidates[0].id

        logger.warning(
            f"Entity {name!r} has no exact match and {len(candidates)} "
            f"ambiguous prefix candidates — skipping edge endpoint"
        )
        return None

    async def _add_entity_to_kg(
        self,
        entity: Dict[str, Any],
        paper: Dict[str, Any],
        organization_id: Optional[str] = None,
    ) -> bool:
        """Add entity to the KG. Returns True only if a node was written."""
        if not self.kg_service:
            return False

        try:
            from src.models.graph import (
                CreateEntityRequest,
                EntityType,
                ExtractionMethod,
            )

            # Map entity types to known EntityType enum
            type_mapping = {
                "author": EntityType.PERSON,
                "concept": EntityType.CONCEPT,
                "method": EntityType.CONCEPT,
                "dataset": EntityType.OTHER,
                "category": EntityType.CONCEPT,
                "institution": getattr(EntityType, "ORGANIZATION", EntityType.OTHER),
                "topic": EntityType.CONCEPT,
                "paper": EntityType.DOCUMENT,
            }

            entity_type = type_mapping.get(entity["type"], EntityType.OTHER)

            # Create entity request
            request = CreateEntityRequest(
                name=entity["text"],
                entity_type=entity_type,
                confidence_score=entity["confidence"],
                extraction_method=entity.get(
                    "extraction_method", ExtractionMethod.MANUAL
                ),
                metadata={
                    "source": entity["source"],
                    "paper_id": paper.get("id", ""),
                    "paper_title": paper.get("title", ""),
                    "arxiv_category": paper.get("primary_category", ""),
                    "publication_date": paper.get("published", ""),
                    "entity_type_original": entity["type"],
                    "full_name": entity.get("full_name", ""),
                    "field": entity.get("field", ""),
                },
                organization_id=organization_id,
            )

            # Create entity (sync driver call — off the event loop)
            await self._offload(self.kg_service.create_entity, request)
            return True

        except Exception as e:
            logger.error(f"Failed to add entity to KG: {e}")
            return False

    async def _add_relationship_to_kg(
        self,
        relationship: Dict[str, Any],
        paper: Dict[str, Any],
        organization_id: Optional[str] = None,
    ) -> bool:
        """Add a relationship to the KG. Returns True only if an edge was written."""
        if not self.kg_service:
            return False

        try:
            from src.models.graph import CreateRelationshipRequest, RelationshipType

            source_name = relationship["source"]["text"]
            target_name = relationship["target"]["text"]

            async def resolve(endpoint: Dict[str, Any]) -> Optional[str]:
                entity_id = await self._resolve_entity_id(
                    endpoint["text"], organization_id=organization_id
                )
                if entity_id is None and self._is_paper_title_endpoint(endpoint, paper):
                    # Belt and braces: the paper-title node should already exist
                    # (ingest paths create it up front), but a direct caller may
                    # not have. Create it (idempotent) and retry once.
                    logger.warning(
                        f"Paper-title entity missing for edge endpoint "
                        f"{endpoint['text'][:80]!r} — creating it now"
                    )
                    if await self._ensure_paper_title_entity(
                        paper, organization_id=organization_id
                    ):
                        entity_id = await self._resolve_entity_id(
                            endpoint["text"], organization_id=organization_id
                        )
                return entity_id

            source_id = await resolve(relationship["source"])
            if not source_id:
                logger.warning(
                    f"Dropping relationship {relationship.get('relation')!r}: "
                    f"source entity {source_name!r} could not be resolved"
                )
                return False

            target_id = await resolve(relationship["target"])
            if not target_id:
                logger.warning(
                    f"Dropping relationship {relationship.get('relation')!r}: "
                    f"target entity {target_name!r} could not be resolved"
                )
                return False

            # Create relationship request
            request = CreateRelationshipRequest(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=RelationshipType.RELATED_TO,  # Use generic relationship
                # Field is confidence_score — a `confidence=` kwarg is silently
                # ignored by pydantic (extra-ignore), so every relationship got
                # the default 0.8 instead of the extracted confidence.
                confidence_score=relationship["confidence"],
                strength=relationship.get("confidence", 0.5),  # strength field required
                metadata={
                    "relationship_subtype": relationship["relation"],
                    "source": relationship.get("extraction_source", ""),
                    "paper_id": paper.get("id", ""),
                    "paper_title": paper.get("title", ""),
                },
                organization_id=organization_id,
            )

            # Create relationship (sync driver call — off the event loop)
            await self._offload(self.kg_service.create_relationship, request)
            return True

        except Exception as e:
            logger.error(f"Failed to add relationship to KG: {e}")
            return False

    async def process_paper_kg_integration(
        self, paper: Dict[str, Any], organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a paper with full knowledge graph integration

        Args:
            paper: Paper metadata

        Returns:
            Processing results with entities and relationships
        """
        logger.info(
            f"Processing KG integration for paper: {paper.get('title', 'Unknown')}"
        )

        # Extraction costs a paid LLM call per paper. With no graph to write to
        # there is nothing to spend it on — bail before extracting, not after.
        if not self.kg_service:
            logger.warning(
                "Knowledge graph unavailable — skipping extraction for paper "
                f"{paper.get('id')}"
            )
            return {
                "paper_id": paper.get("id"),
                "entities": [],
                "relationships": [],
                "entities_created": 0,
                "relationships_created": 0,
                "kg_updated": False,
            }

        try:
            # Extract entities
            entities = await self._extract_entities_from_paper(paper)

            # Extract relationships
            relationships = await self._extract_relationships_from_paper(paper)

            entities_created = 0
            for entity in entities:
                if await self._add_entity_to_kg(
                    entity, paper, organization_id=organization_id
                ):
                    entities_created += 1

            # Paper-title node must exist before author_of/belongs_to/cites
            # edges reference it (idempotent MERGE).
            await self._ensure_paper_title_entity(
                paper, organization_id=organization_id
            )

            relationships_created = 0
            for relationship in relationships:
                if await self._add_relationship_to_kg(
                    relationship, paper, organization_id=organization_id
                ):
                    relationships_created += 1

            return {
                "paper_id": paper.get("id"),
                "entities": entities,
                "relationships": relationships,
                # Counts of what was *written*, not what was extracted.
                "entities_created": entities_created,
                "relationships_created": relationships_created,
                "kg_updated": bool(entities_created or relationships_created),
            }

        except Exception as e:
            logger.error(f"Failed to process paper KG integration: {e}")
            return None

    async def close(self):
        """Close services"""
        if hasattr(self, "arxiv_service") and self.arxiv_service:
            if hasattr(self.arxiv_service, "close"):
                await self.arxiv_service.close()

        if (
            hasattr(self, "kg_service")
            and self.kg_service
            and hasattr(self.kg_service, "close")
        ):
            await self.kg_service.close()
