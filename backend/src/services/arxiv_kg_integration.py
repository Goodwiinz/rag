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
from ..shared.schemas import ProcessingStatus
from ..models.document import DocumentType

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
            from ..services.knowledge_graph_service import KnowledgeGraphService
            self.kg_service = KnowledgeGraphService()
            # Test connection
            if self.kg_service.driver:
                logger.info("Knowledge graph service initialized successfully")
            else:
                logger.error("Knowledge graph service driver not initialized")
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
                        relationships = await self._extract_relationships_from_paper(paper)
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
        entities.extend(self._extract_concepts(text))
        entities.extend(self._extract_datasets(text))
        entities.extend(self._extract_methods(text))

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
                    'source': 'technical_terms'
                })

        return entities

    def _extract_authors_as_entities(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract authors as entities"""
        entities = []

        for author in paper.get('authors', []):
            # Extract last name for entity disambiguation
            name_parts = author.split()
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                entities.append({
                    'text': last_name,
                    'full_name': author,
                    'type': 'author',
                    'confidence': 0.95,
                    'source': 'paper_authors'
                })
            elif len(name_parts) == 1:
                entities.append({
                    'text': name_parts[0],
                    'full_name': author,
                    'type': 'author',
                    'confidence': 0.9,
                    'source': 'paper_authors'
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
                'source': 'arxiv_category'
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
        """Extract abstract concepts and ideas"""
        entities = []

        # Look for concept indicators
        concept_patterns = [
            (r'\b(objective|goal|contribution|novelty|innovation|advancement)\b', 'concept'),
            (r'\b(approach|methodology|framework|architecture|paradigm)\b', 'method'),
            (r'\b(performance|accuracy|efficiency|scalability|robustness)\b', 'metric'),
            (r'\b(limitation|drawback|challenge|future work|open problem)\b', 'concept'),
        ]

        for pattern, entity_type in concept_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Extract context around the match
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end].strip()
                    entities.append({
                        'text': context,
                        'type': entity_type,
                        'confidence': 0.7,
                        'source': 'text_pattern'
                    })

        return entities

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
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE)
                entities.append({
                    'text': match.group(),
                    'type': 'dataset',
                    'confidence': 0.8,
                    'source': 'known_dataset'
                })

        return entities

    def _extract_methods(self, text: str) -> List[Dict[str, Any]]:
        """Extract methods and algorithms"""
        entities = []

        # Method indicators
        method_patterns = [
            (r'\b(prove|demonstrate|evaluate|validate|benchmark)\b', 'method'),
            (r'\b(achieve|obtain|improve|outperform|exceed)\b', 'result'),
            (r'\b(state-of-the-art|SOTA|cutting-edge)\b', 'comparison'),
            (r'\b(baseline|comparative|ablation)\b', 'method'),
        ]

        for pattern, entity_type in method_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE)
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end].strip()
                entities.append({
                    'text': context,
                    'type': entity_type,
                    'confidence': 0.7,
                    'source': 'text_pattern'
                })

        return entities

    async def _extract_relationships_from_paper(self, paper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract relationships from paper

        Args:
            paper: Paper metadata

        Returns:
            List of relationships
        """
        relationships = []

        # Author-paper relationships
        for author in paper.get('authors', []):
            relationships.append({
                'source': {'text': author, 'type': 'author'},
                'target': {'text': paper['title'], 'type': 'paper'},
                'relation': 'author_of',
                'confidence': 1.0,
                'source': 'paper_metadata'
            })

        # Paper-category relationships
        for category in paper.get('categories', []):
            relationships.append({
                'source': {'text': paper['title'], 'type': 'paper'},
                'target': {'text': category, 'type': 'category'},
                'relation': 'belongs_to',
                'confidence': 1.0,
                'source': 'paper_metadata'
            })

        # Look for citation patterns in abstract
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
                        'source': 'abstract_text'
                    })

        return relationships

    async def _add_entity_to_kg(self, entity: Dict[str, Any], paper: Dict[str, Any]):
        """Add entity to knowledge graph"""
        if not self.kg_service:
            return

        try:
            from ..models.graph import CreateEntityRequest, EntityType, ExtractionMethod

            # Map entity types to known EntityType enum
            type_mapping = {
                'author': EntityType.PERSON,
                'concept': EntityType.CONCEPT,
                'method': EntityType.CONCEPT,
                'dataset': EntityType.OTHER,
                'category': EntityType.CONCEPT
            }

            entity_type = type_mapping.get(entity['type'], EntityType.OTHER)

            # Create entity request
            request = CreateEntityRequest(
                name=entity['text'],
                entity_type=entity_type,
                confidence_score=entity['confidence'],
                extraction_method=ExtractionMethod.MANUAL,
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
            from ..models.graph import CreateRelationshipRequest, RelationshipType

            # For relationships, we need to first find the entities
            # This is a simplified approach - in production you'd want to ensure entities exist
            source_name = relationship['source']['text']
            target_name = relationship['target']['text']

            # Create relationship request
            request = CreateRelationshipRequest(
                source_entity_name=source_name,
                target_entity_name=target_name,
                relationship_type=RelationshipType.RELATED_TO,  # Use generic relationship
                confidence=relationship['confidence'],
                metadata={
                    'relationship_subtype': relationship['relation'],
                    'source': relationship.get('source', ''),
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