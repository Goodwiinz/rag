"""
ArXiv Knowledge Graph Integration Service

This service enhances arXiv paper ingestion by extracting entities and relationships
and adding them to the knowledge graph for better semantic search and understanding.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
import json

from .arxiv_service import ArXivIngestionService
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.shared.schemas import ProcessingStatus
from src.models.document import DocumentType

logger = logging.getLogger(__name__)


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
                # Try to get a session to test connection
                with self.kg_service.get_session() as session:
                    session.run("RETURN 1")
                logger.info("Knowledge graph service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize knowledge graph service: {e}", exc_info=True)
            self.kg_service = None

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
        **kwargs
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
            download_pdfs=kwargs.get('download_pdfs', True),
            extract_content=kwargs.get('extract_content', True),
            batch_size=kwargs.get('batch_size', 10)
        )

        # Process each paper for knowledge graph
        if self.kg_service and (extract_entities or create_relationships):
            for i, (paper, doc) in enumerate(zip(papers, documents)):
                try:
                    logger.info(f"Processing paper {i+1}/{len(papers)} for knowledge graph: {paper['title'][:50]}...")

                    # Extract entities
                    if extract_entities:
                        entities = await self._extract_entities_from_paper(paper)
                        logger.info(f"Extracted {len(entities)} entities")

                        # Add entities to knowledge graph
                        for entity in entities:
                            await self._add_entity_to_kg(entity, paper)

                    # Create relationships
                    if create_relationships:
                        # Pass extracted entities to relationship extraction for context
                        relationships = await self._extract_relationships_from_paper(paper, entities if extract_entities else None)
                        logger.info(f"Extracted {len(relationships)} relationships")

                        # Add relationships to knowledge graph
                        for rel in relationships:
                            await self._add_relationship_to_kg(rel, paper)

                except Exception as e:
                    logger.error(f"Failed to process paper for KG: {e}")
                    import traceback
                    traceback.print_exc()

        return documents

    async def _extract_entities_from_paper(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            key = entity['text'].lower().strip()
            if key not in unique_entities or entity['confidence'] > unique_entities[key]['confidence']:
                unique_entities[key] = entity

        return list(unique_entities.values())

    def _extract_technical_terms(self, text: str) -> List[Dict[str, Any]]:
        """Extract technical terms and acronyms"""
        entities = []

        # Common ML/AI terms
        technical_terms = {
            'Transformer': {'type': 'model', 'confidence': 0.9},
            'BERT': {'type': 'model', 'confidence': 0.9},
            'GPT': {'type': 'model', 'confidence': 0.9},
            'LSTM': {'type': 'model', 'confidence': 0.9},
            'RNN': {'type': 'model', 'confidence': 0.9},
            'CNN': {'type': 'model', 'confidence': 0.9},
            'GAN': {'type': 'model', 'confidence': 0.9},
            'SVM': {'type': 'model', 'confidence': 0.9},
            'Attention': {'type': 'mechanism', 'confidence': 0.85},
            'Backpropagation': {'type': 'method', 'confidence': 0.85},
            'Gradient Descent': {'type': 'method', 'confidence': 0.85},
            'Adam': {'type': 'optimizer', 'confidence': 0.85},
            'SGD': {'type': 'optimizer', 'confidence': 0.85},
            'Dropout': {'type': 'technique', 'confidence': 0.8},
            'Batch Normalization': {'type': 'technique', 'confidence': 0.8},
            'ReLU': {'type': 'activation', 'confidence': 0.8},
            'Softmax': {'type': 'activation', 'confidence': 0.8},
            'Embedding': {'type': 'technique', 'confidence': 0.8},
        }

        # Find terms
        for term, info in technical_terms.items():
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                entities.append({
                    'text': term,
                    'type': info['type'],
                    'confidence': info['confidence'],
                    'source': 'technical_terms',
                    'extraction_method': 'pattern_matching'
                })

        return entities

    def _extract_authors_as_entities(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract authors as entities"""
        entities = []

        for author in paper.get('authors', []):
            # Extract last name for entity disambiguation
            name_parts = author.split()
            if len(name_parts) >= 2:
                # Use full name as the primary entity text
                entities.append({
                    'text': author,
                    'full_name': author,
                    'type': 'author',
                    'confidence': 0.95,
                    'source': 'paper_authors',
                    'extraction_method': 'rule_based'
                })
            elif len(name_parts) == 1:
                entities.append({
                    'text': author,
                    'full_name': author,
                    'type': 'author',
                    'confidence': 0.9,
                    'source': 'paper_authors',
                    'extraction_method': 'rule_based'
                })

        return entities

    def _extract_categories(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract arXiv categories as entities"""
        entities = []

        for category in paper.get('categories', []):
            # Map category to full name
            category_mapping = self._get_category_mapping(category)

            entities.append({
                'text': category,
                'full_name': category_mapping.get('full_name', category),
                'field': category_mapping.get('field', 'Unknown'),
                'confidence': 1.0,
                'type': 'category',
                'source': 'arxiv_category',
                'extraction_method': 'manual'
            })

        return entities

    def _extract_affiliations(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract affiliations (Schools, Labs) from paper metadata"""
        entities = []
        
        # Check if detailed author info is available
        for author_info in paper.get('authors_detailed', []):
            for affiliation in author_info.get('affiliations', []):
                if affiliation:
                    entities.append({
                        'text': affiliation,
                        'type': 'institution',
                        'confidence': 1.0,
                        'source': 'paper_metadata',
                        'extraction_method': 'metadata'
                    })
                    
        return entities

    def _get_category_mapping(self, category: str) -> Dict[str, str]:
        """Get mapping from arXiv category to full name"""
        mappings = {
            # Computer Science
            'cs.AI': {'full_name': 'Artificial Intelligence', 'field': 'Computer Science'},
            'cs.LG': {'full_name': 'Machine Learning', 'field': 'Computer Science'},
            'cs.CL': {'full_name': 'Computation and Language', 'field': 'Computer Science'},
            'cs.CV': {'full_name': 'Computer Vision', 'field': 'Computer Science'},
            'cs.RO': {'full_name': 'Robotics', 'field': 'Computer Science'},
            'cs.IR': {'full_name': 'Information Retrieval', 'field': 'Computer Science'},
            'cs.NE': {'full_name': 'Neural and Evolutionary Computing', 'field': 'Computer Science'},

            # Mathematics
            'math.ML': {'full_name': 'Machine Learning', 'field': 'Mathematics'},
            'math.ST': {'full_name': 'Statistics Theory', 'field': 'Mathematics'},
            'math.OC': {'full_name': 'Optimization and Control', 'field': 'Mathematics'},

            # Physics
            'quant-ph': {'full_name': 'Quantum Physics', 'field': 'Physics'},
            'cond-mat': {'full_name': 'Condensed Matter', 'field': 'Physics'},
            'astro-ph': {'full_name': 'Astrophysics', 'field': 'Physics'},

            # Statistics
            'stat.ML': {'full_name': 'Machine Learning', 'field': 'Statistics'},
            'stat.ME': {'full_name': 'Methodology', 'field': 'Statistics'},
            'stat.TH': {'full_name': 'Theory', 'field': 'Statistics'},
        }

        return mappings.get(category, {'full_name': category, 'field': 'Unknown'})

    def _extract_concepts(self, text: str) -> List[Dict[str, Any]]:
        """Extract abstract concepts and ideas with context-aware boundaries"""
        entities = []

        # Look for concept indicators
        concept_patterns = [
            (r'\b(objective|goal|contribution|novelty|innovation|advancement)\b', 'concept'),
            (r'\b(approach|methodology|framework|architecture|paradigm)\b', 'method'),
            (r'\b(performance|accuracy|efficiency|scalability|robustness)\b', 'metric'),
            (r'\b(limitation|drawback|challenge|future work|open problem)\b', 'concept'),
        ]

        for pattern, entity_type in concept_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get context with word boundaries
                context = self._get_context_with_boundaries(text, match.start(), match.end())
                
                if context:
                    entities.append({
                        'text': context,
                        'type': entity_type,
                        'confidence': 0.7,
                        'source': 'text_pattern',
                        'extraction_method': 'pattern_matching'
                    })

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
            r'ImageNet|COCO|SQuAD|GLUE|SuperGLUE',
            r'PASCAL|MNIST|CIFAR-10|CIFAR-100',
            r'WMT|ACL|EMNLP|ICLR|NeurIPS',
            r'SQUAD|TREC|Kaggle|UCI',
        ]

        for pattern in dataset_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities.append({
                    'text': match.group(),
                    'type': 'dataset',
                    'confidence': 0.8,
                    'source': 'known_dataset',
                    'extraction_method': 'pattern_matching'
                })

        return entities

    def _extract_methods(self, text: str) -> List[Dict[str, Any]]:
        """Extract methods and algorithms with context-aware boundaries"""
        entities = []

        # Method indicators
        method_patterns = [
            (r'\b(prove|demonstrate|evaluate|validate|benchmark)\b', 'method'),
            (r'\b(achieve|obtain|improve|outperform|exceed)\b', 'result'),
            (r'\b(state-of-the-art|SOTA|cutting-edge)\b', 'comparison'),
            (r'\b(baseline|comparative|ablation)\b', 'method'),
        ]

        for pattern, entity_type in method_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get context with word boundaries
                context = self._get_context_with_boundaries(text, match.start(), match.end())
                
                if context:
                    entities.append({
                        'text': context,
                        'type': entity_type,
                        'confidence': 0.7,
                        'source': 'text_pattern',
                        'extraction_method': 'pattern_matching'
                    })

        return entities

    def _get_context_with_boundaries(self, text: str, start_idx: int, end_idx: int, padding: int = 40) -> str:
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
                    {"role": "user", "content": text[:4000]} # Truncate to avoid context window issues
                ],
                temperature=0.0
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
                entities.append({
                    'text': item['text'],
                    'type': item['type'],
                    'confidence': item['confidence'],
                    'source': 'llm_extraction',
                    'extraction_method': 'llm_extraction' 
                })
                
        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")
            
        return entities

    async def _extract_relationships_from_paper(
        self, 
        paper: Dict[str, Any], 
        entities: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships from paper, including semantic ones if entities are provided
        """
        relationships = []

        # 1. Author-paper relationships
        for author in paper.get('authors', []):
            relationships.append({
                'source': {'text': author, 'type': 'author'},
                'target': {'text': paper['title'], 'type': 'paper'},
                'relation': 'author_of',
                'confidence': 1.0,
                'extraction_source': 'paper_metadata'
            })
            
        # 1b. Author-Affiliation relationships
        for author_info in paper.get('authors_detailed', []):
            name = author_info['name']
            for aff in author_info.get('affiliations', []):
                relationships.append({
                    'source': {'text': name, 'type': 'author'},
                    'target': {'text': aff, 'type': 'institution'},
                    'relation': 'AFFILIATED_WITH',
                    'confidence': 1.0,
                    'extraction_source': 'paper_metadata'
                })

        # 2. Paper-category relationships
        for category in paper.get('categories', []):
            relationships.append({
                'source': {'text': paper['title'], 'type': 'paper'},
                'target': {'text': category, 'type': 'category'},
                'relation': 'belongs_to',
                'confidence': 1.0,
                'extraction_source': 'paper_metadata'
            })

        # 3. Citation relationships
        abstract = paper.get('abstract', '')
        citation_patterns = [
            r'(?:cite|reference|based on|builds upon|extends)\s+([^,.]+)',
            r'previous work[^.]*?\(([^)]+)\)',
            r'(?:as\s+shown\s+in)\s+([^,.]+)',
        ]

        for pattern in citation_patterns:
            matches = re.finditer(pattern, abstract)
            for match in matches:
                cited_paper = match.group(1).strip('()[]')
                if cited_paper:
                    relationships.append({
                        'source': {'text': paper['title'], 'type': 'paper'},
                        'target': {'text': cited_paper, 'type': 'paper'},
                        'relation': 'cites',
                        'confidence': 0.8,
                        'extraction_source': 'abstract_text'
                    })
                    
        # 4. LLM Semantic Relationships (New)
        if entities and azure_openai_service.is_chat_available():
            semantic_rels = await self._extract_semantic_relations_with_llm(
                f"{paper['title']}\n{abstract}", 
                entities
            )
            relationships.extend(semantic_rels)

        return relationships

    async def _extract_semantic_relations_with_llm(
        self, 
        text: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract semantic relationships using LLM"""
        relationships = []
        try:
            # Filter distinct entity names for context
            entity_names = list(set([e['text'] for e in entities]))
            
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
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0
            )
            
            content = response.get("content", "")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            
            # Map back to required structure
            # We need to look up entity types for the result
            entity_type_map = {e['text']: e.get('type', 'concept') for e in entities}
            
            for rel in data.get('relationships', []):
                src = rel.get('source')
                tgt = rel.get('target')
                
                if src in entity_type_map and tgt in entity_type_map:
                    relationships.append({
                        'source': {'text': src, 'type': entity_type_map[src]},
                        'target': {'text': tgt, 'type': entity_type_map[tgt]},
                        'relation': rel.get('relation', 'RELATED_TO'),
                        'confidence': rel.get('confidence', 0.7),
                        'extraction_source': 'llm_semantic'
                    })
                    
        except Exception as e:
            logger.warning(f"LLM semantic relationship extraction failed: {e}")
            
        return relationships

    async def _add_entity_to_kg(self, entity: Dict[str, Any], paper: Dict[str, Any]):
        """Add entity to knowledge graph"""
        if not self.kg_service:
            return

        try:
            from src.models.graph import CreateEntityRequest, EntityType, ExtractionMethod

            # Map entity types to known EntityType enum
            type_mapping = {
                'author': EntityType.PERSON,
                'concept': EntityType.CONCEPT,
                'method': EntityType.CONCEPT,
                'dataset': EntityType.OTHER,
                'category': EntityType.CONCEPT,
                'institution': getattr(EntityType, 'ORGANIZATION', EntityType.OTHER),
                'topic': EntityType.CONCEPT
            }

            entity_type = type_mapping.get(entity['type'], EntityType.OTHER)

            # Create entity request
            request = CreateEntityRequest(
                name=entity['text'],
                entity_type=entity_type,
                confidence_score=entity['confidence'],
                extraction_method=entity.get('extraction_method', ExtractionMethod.MANUAL),
                metadata={
                    'source': entity['source'],
                    'paper_id': paper.get('id', ''),
                    'paper_title': paper.get('title', ''),
                    'arxiv_category': paper.get('primary_category', ''),
                    'publication_date': paper.get('published', ''),
                    'entity_type_original': entity['type'],
                    'full_name': entity.get('full_name', ''),
                    'field': entity.get('field', '')
                }
            )

            # Create entity
            self.kg_service.create_entity(request)

        except Exception as e:
            logger.error(f"Failed to add entity to KG: {e}")

    async def _add_relationship_to_kg(self, relationship: Dict[str, Any], paper:Dict[str, Any]):
        """Add relationship to knowledge graph"""
        if not self.kg_service:
            return

        try:
            from src.models.graph import CreateRelationshipRequest, RelationshipType

            # For relationships, we need to first find the entities
            # This is a simplified approach - in production you'd want to ensure entities exist
            source_name = relationship['source']['text']
            target_name = relationship['target']['text']

            # Find source entity
            source_entities = self.kg_service.search_entities(query=source_name, limit=1)
            if not source_entities:
                # logger.warning(f"Source entity not found for relationship: {source_name}")
                return
            source_id = source_entities[0].id

            # Find target entity
            target_entities = self.kg_service.search_entities(query=target_name, limit=1)
            if not target_entities:
                # logger.warning(f"Target entity not found for relationship: {target_name}")
                return
            target_id = target_entities[0].id

            # Create relationship request
            request = CreateRelationshipRequest(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=RelationshipType.RELATED_TO,  # Use generic relationship
                confidence=relationship['confidence'],
                strength=relationship.get('confidence', 0.5), # strength field required
                metadata={
                    'relationship_subtype': relationship['relation'],
                    'source': relationship.get('extraction_source', ''),
                    'paper_id': paper.get('id', ''),
                    'paper_title': paper.get('title', '')
                }
            )

            # Create relationship
            self.kg_service.create_relationship(request)

        except Exception as e:
            logger.error(f"Failed to add relationship to KG: {e}")

    async def create_paper_kg_subgraph(
        self,
        paper_id: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Create a knowledge graph subgraph for a specific paper

        Args:
            paper_id: ArXiv paper ID
            depth: How many citation levels to explore

        Returns:
            Subgraph information
        """
        if not self.kg_service:
            return {'error': 'Knowledge graph service not available'}

        try:
            # Get paper details
            async with self.arxiv_service as service:
                papers = await service.search_papers(
                    query=f"id:{paper_id}",
                    max_results=1
                )

            if not papers:
                return {'error': f'Paper {paper_id} not found'}

            paper = papers[0]

            # Create nodes and relationships
            entities = await self._extract_entities_from_paper(paper)
            relationships = await self._extract_relationships_from_paper(paper)

            # Extract cited papers (simplified)
            cited_papers = await self._extract_cited_papers(paper['abstract'])

            return {
                'paper': paper,
                'entities': entities,
                'relationships': relationships,
                'cited_papers': cited_papers
            }

        except Exception as e:
            logger.error(f"Failed to create KG subgraph: {e}")
            return {'error': str(e)}

    async def _extract_cited_papers(self, text: str) -> List[str]:
        """Extract cited paper references from text"""
        cited_papers = []

        # Simple pattern to find [Author, Year] style citations
        citation_pattern = r'\[([^,]+,\s*\d{4})\]'
        matches = re.findall(citation_pattern, text)

        for match in matches:
            # Extract just the author name part
            authors = match[0].split(',')[0].strip()
            cited_papers.append(authors)

        return cited_papers

    async def get_author_collaboration_network(
        self,
        author_name: str,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Build collaboration network for an author

        Args:
            author_name: Author name to search for
            max_depth: How many levels deep to explore

        Returns:
            Network information
        """
        if not self.kg_service:
            return {'error': 'Knowledge graph service not available'}

        try:
            # Search for papers by author
            async with self.arxiv_service as service:
                papers = await service.search_papers(
                    query=f"au:\"{author_name}\"",
                    max_results=50
                )

            # Extract co-authors and build network
            network = {
                'author': author_name,
                'papers': papers,
                'coauthors': set(),
                'collaborators': {},
                'collaboration_strength': {}
            }

            for paper in papers:
                for coauthor in paper.get('authors', []):
                    if coauthor != author_name:
                        network['coauthors'].add(coauthor)
                        if coauthor not in network['collaborators']:
                            network['collaborators'][coauthor] = []
                        network['collaborators'][coauthor].append(paper)

            # Calculate collaboration strength
            for coauthor, papers_list in network['collaborators'].items():
                network['collaboration_strength'][coauthor] = len(papers_list)

            return network

        except Exception as e:
            logger.error(f"Failed to build collaboration network: {e}")
            return {'error': str(e)}

    async def analyze_research_area_trends(
        self,
        category: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze trends in a research area

        Args:
            category: ArXiv category (e.g., cs.LG)
            days: Number of recent days to analyze

        Returns:
            Trend analysis results
        """
        try:
            # Get recent papers in category
            async with self.arxiv_service as service:
                papers = await service.search_papers(
                    query=f"cat:{category}",
                    max_results=1000,
                    date_from=datetime.now() - timedelta(days=days)
                )

            # Analyze patterns
            analysis = {
                'category': category,
                'period_days': days,
                'total_papers': len(papers),
                'trending_topics': self._extract_trending_topics(papers),
                'author_collaborations': self._analyze_author_collaborations(papers),
                'citation_patterns': self._analyze_citation_patterns(papers),
                'keyword_evolution': self._analyze_keyword_evolution(papers)
            }

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze trends: {e}")
            return {'error': str(e)}

    def _extract_trending_topics(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract trending topics from paper titles and abstracts"""
        # Simple frequency analysis of terms
        all_text = " ".join([p.get('title', '') + " " + p.get('abstract', '') for p in papers])
        words = re.findall(r'\b\w+\b', all_text.lower())

        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        filtered_words = [w for w in words if w not in stop_words and len(w) > 3]

        # Count frequencies
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Get top words
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:20]

        trending = [
            {'term': word, 'count': count, 'trend': 'increasing'}
            for word, count in top_words
        ]

        return trending

    def _analyze_author_collaborations(self, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze author collaboration patterns"""
        collab_counts = {}

        for paper in papers:
            authors = paper.get('authors', [])
            num_authors = len(authors)

            if num_authors > 1:
                for i in range(num_authors):
                    for j in range(i + 1, num_authors):
                        pair = tuple(sorted([authors[i], authors[j]]))
                        collab_counts[pair] = collab_counts.get(pair, 0) + 1

        # Get top collaborations
        top_collabs = sorted(collab_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'total_collaborations': sum(collab_counts.values()),
            'top_pairs': [
                {'authors': pair, 'count': count}
                for pair, count in top_collabs
            ]
        }

    def _analyze_citation_patterns(self, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze citation patterns in abstracts"""
        papers_with_citations = 0
        total_citations = 0

        for paper in papers:
            abstract = paper.get('abstract', '')
            citation_count = len(re.findall(r'\[', abstract))
            if citation_count > 0:
                papers_with_citations += 1
                total_citations += citation_count

        return {
            'papers_with_citations': papers_with_citations,
            'total_citations_estimated': total_citations,
            'average_citations_per_paper': total_citations / max(1, papers_with_citations)
        }

    def _analyze_keyword_evolution(self, papers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze how keywords evolve over time"""
        # Group papers by month
        monthly_keywords = {}

        for paper in papers:
            try:
                pub_date = datetime.fromisoformat(paper['published'].replace('Z', '+00:00'))
                month_key = pub_date.strftime('%Y-%m')

                if month_key not in monthly_keywords:
                    monthly_keywords[month_key] = {}

                # Extract key terms from title
                title = paper['title'].lower()
                words = re.findall(r'\b\w+\b', title)

                for word in words:
                    if len(word) > 3:
                        monthly_keywords[month_key][word] = monthly_keywords[month_key].get(word, 0) + 1
            except:
                pass

        return {
            'monthly_trends': monthly_keywords
        }

    async def process_paper_kg_integration(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a paper with full knowledge graph integration

        Args:
            paper: Paper metadata

        Returns:
            Processing results with entities and relationships
        """
        logger.info(f"Processing KG integration for paper: {paper.get('title', 'Unknown')}")

        try:
            # Extract entities
            entities = await self._extract_entities_from_paper(paper)

            # Extract relationships
            relationships = await self._extract_relationships_from_paper(paper)

            # Add to knowledge graph if available
            if self.kg_service:
                # Add entities
                for entity in entities:
                    await self._add_entity_to_kg(entity, paper)

                # Add relationships
                for relationship in relationships:
                    await self._add_relationship_to_kg(relationship, paper)

            return {
                'paper_id': paper.get('id'),
                'entities': entities,
                'relationships': relationships,
                'kg_updated': self.kg_service is not None
            }

        except Exception as e:
            logger.error(f"Failed to process paper KG integration: {e}")
            return None

    async def close(self):
        """Close services"""
        if hasattr(self, 'arxiv_service') and self.arxiv_service:
            if hasattr(self.arxiv_service, 'close'):
                await self.arxiv_service.close()

        if hasattr(self, 'kg_service') and self.kg_service and hasattr(self.kg_service, 'close'):
            await self.kg_service.close()