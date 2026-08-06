"""
ArXiv-Specific Search Service for RAG System

Provides specialized search capabilities for arXiv papers including:
- Category-based filtering
- Author-based search
- Temporal filtering (publication date ranges)
- Citation-based ranking
- Semantic similarity within arXiv domains
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from elasticsearch import Elasticsearch

from src.services.search.search_service import SearchService
from src.shared.schemas import FilterOptions, SearchResult

from .arxiv_service import ArXivIngestionService

logger = logging.getLogger(__name__)


class ArXivSearchService(SearchService):
    """
    Enhanced search service specifically for arXiv papers

    Extends the base SearchService with arXiv-specific features:
    - Category hierarchy navigation
    - Author reputation scoring
    - Citation count estimation
    - Recency boosting
    - Venue-based filtering (conferences, journals)
    """

    # ArXiv category weights for relevance boosting
    CATEGORY_WEIGHTS = {
        "cs.AI": 1.2,  # Artificial Intelligence
        "cs.LG": 1.2,  # Machine Learning
        "cs.CV": 1.1,  # Computer Vision
        "cs.CL": 1.1,  # NLP
        "cs.RO": 1.0,  # Robotics
        "stat.ML": 1.2,  # Statistics ML
        "q-bio.QM": 0.9,  # Quantitative Biology
        "physics.comp-ph": 1.0,  # Computational Physics
    }

    # Top-tier venues (conferences/journals) for boosting
    TOP_VENUES = {
        "conferences": [
            "NeurIPS",
            "ICML",
            "ICLR",
            "AAAI",
            "IJCAI",
            "CVPR",
            "ICCV",
            "ECCV",
            "ACL",
            "EMNLP",
            "KDD",
            "WWW",
            "SIGIR",
            "RECsys",
        ],
        "journals": [
            "Nature",
            "Science",
            "Cell",
            "JMLR",
            "PAMI",
            "IJCV",
            "TACL",
            "Physical Review Letters",
            "Journal of Machine Learning Research",
        ],
    }

    def __init__(self, elasticsearch_url: str = None):
        super().__init__(elasticsearch_url)
        self.arxiv_index = "arxiv_papers"

    async def search_papers(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
        sort_by: str = "relevance",
        boost_recent: bool = True,
        recency_days: int = 365,
    ) -> List[SearchResult]:
        """
        Search arXiv papers with specialized filters and ranking

        Args:
            query: Search query
            filters: Dictionary of filters (categories, authors, dates, etc.)
            limit: Number of results to return
            offset: Offset for pagination
            sort_by: Sort method (relevance, date, citations, author_rank)
            boost_recent: Whether to boost recent papers
            recency_days: Days to consider as "recent"

        Returns:
            List of search results
        """
        # Build Elasticsearch query
        es_query = self._build_arxiv_query(
            query=query,
            filters=filters or {},
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            boost_recent=boost_recent,
            recency_days=recency_days,
        )

        try:
            # Execute search
            response = self.es_client.search(index=self.arxiv_index, body=es_query)

            # Convert to SearchResult objects
            results = []
            for hit in response["hits"]["hits"]:
                result = self._convert_to_search_result(hit)
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"ArXiv search failed: {e}")
            return []

    def _build_arxiv_query(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int,
        offset: int,
        sort_by: str,
        boost_recent: bool,
        recency_days: int,
    ) -> Dict[str, Any]:
        """Build Elasticsearch query for arXiv papers"""

        # Base query structure
        es_query = {
            "query": {"bool": {"must": [], "filter": [], "should": [], "must_not": []}},
            "size": limit,
            "from": offset,
            "highlight": {
                "fields": {
                    "title": {},
                    "abstract": {},
                    "content": {"fragment_size": 150, "number_of_fragments": 3},
                }
            },
        }

        # Text search with field weights
        text_query = {
            "multi_match": {
                "query": query,
                "fields": [
                    "title^3",  # Title gets highest weight
                    "abstract^2",  # Abstract gets medium weight
                    "content",  # Full content
                    "authors.name^2",  # Author names
                    "categories^1.5",  # Categories
                ],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }
        es_query["query"]["bool"]["must"].append(text_query)

        # Apply filters
        if filters.get("categories"):
            category_filter = {"terms": {"categories": filters["categories"]}}
            es_query["query"]["bool"]["filter"].append(category_filter)

        if filters.get("authors"):
            author_filter = {
                "nested": {
                    "path": "authors",
                    "query": {"terms": {"authors.name": filters["authors"]}},
                }
            }
            es_query["query"]["bool"]["filter"].append(author_filter)

        if filters.get("date_from") or filters.get("date_to"):
            date_range = {}
            if filters.get("date_from"):
                date_range["gte"] = filters["date_from"]
            if filters.get("date_to"):
                date_range["lte"] = filters["date_to"]

            date_filter = {"range": {"published": date_range}}
            es_query["query"]["bool"]["filter"].append(date_filter)

        # Category-based boosting
        if filters.get("boost_categories"):
            for category in filters["boost_categories"]:
                weight = self.CATEGORY_WEIGHTS.get(category, 1.0)
                boost_query = {
                    "term": {"categories": {"value": category, "boost": weight}}
                }
                es_query["query"]["bool"]["should"].append(boost_query)

        # Recency boosting
        if boost_recent:
            recent_date = datetime.now() - timedelta(days=recency_days)
            recency_boost = {
                "range": {"published": {"gte": recent_date.isoformat(), "boost": 1.5}}
            }
            es_query["query"]["bool"]["should"].append(recency_boost)

        # Author reputation boosting (simplified)
        if filters.get("top_authors"):
            author_boost = {
                "nested": {
                    "path": "authors",
                    "query": {"terms": {"authors.name": filters["top_authors"]}},
                    "boost": 1.3,
                }
            }
            es_query["query"]["bool"]["should"].append(author_boost)

        # Sorting
        if sort_by == "date":
            es_query["sort"] = [
                {"published": {"order": "desc"}},
                {"_score": {"order": "desc"}},
            ]
        elif sort_by == "citations":
            es_query["sort"] = [
                {"citation_count": {"order": "desc", "missing": "_last"}},
                {"_score": {"order": "desc"}},
            ]
        elif sort_by == "author_rank":
            es_query["sort"] = [
                {"authors.h_index": {"order": "desc", "missing": "_last"}},
                {"_score": {"order": "desc"}},
            ]
        else:  # relevance (default)
            es_query["sort"] = [
                {"_score": {"order": "desc"}},
                {"published": {"order": "desc"}},
            ]

        return es_query

    def _convert_to_search_result(self, hit: Dict[str, Any]) -> SearchResult:
        """Convert Elasticsearch hit to SearchResult"""
        source = hit["_source"]
        highlight = hit.get("highlight", {})

        # Extract highlights
        title_highlight = highlight.get("title", [source.get("title", "")])[0]
        abstract_highlight = " ".join(highlight.get("abstract", []))
        content_highlights = highlight.get("content", [])

        # Calculate relevance score
        score = hit["_score"]

        # Build metadata
        metadata = {
            "authors": source.get("authors", []),
            "categories": source.get("categories", []),
            "published": source.get("published"),
            "arxiv_id": source.get("arxiv_id"),
            "journal_ref": source.get("journal_ref"),
            "doi": source.get("doi"),
            "citation_count": source.get("citation_count", 0),
            "num_pages": source.get("num_pages"),
        }

        return SearchResult(
            id=hit["_id"],
            title=title_highlight,
            content=abstract_highlight,
            url=f"https://arxiv.org/abs/{source.get('arxiv_id')}",
            score=score,
            metadata=metadata,
            highlights=content_highlights,
        )

    async def get_similar_papers(
        self, paper_id: str, limit: int = 10, similarity_threshold: float = 0.7
    ) -> List[SearchResult]:
        """
        Find papers similar to a given paper

        Uses semantic similarity and shared categories/authors
        """
        try:
            # Get the reference paper
            ref_doc = self.es_client.get(index=self.arxiv_index, id=paper_id)
            ref_source = ref_doc["_source"]

            # Build more-like-this query
            mlt_query = {
                "query": {
                    "more_like_this": {
                        "fields": ["title", "abstract", "content"],
                        "like": [{"_index": self.arxiv_index, "_id": paper_id}],
                        "min_term_freq": 1,
                        "max_query_terms": 25,
                        "min_doc_freq": 2,
                        "minimum_should_match": "30%",
                    }
                },
                "size": limit,
                "_source": False,
            }

            # Execute MLT query
            response = self.es_client.search(index=self.arxiv_index, body=mlt_query)

            # Convert to results
            results = []
            for hit in response["hits"]["hits"]:
                if hit["_score"] >= similarity_threshold:
                    # Get full document
                    doc = self.es_client.get(index=self.arxiv_index, id=hit["_id"])
                    result = self._convert_to_search_result(
                        {**hit, "_source": doc["_source"]}
                    )
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"Failed to find similar papers: {e}")
            return []

    async def get_category_hierarchy(self, category: str) -> Dict[str, Any]:
        """
        Get category hierarchy and related categories

        Returns parent categories, siblings, and related subcategories
        """
        # Category taxonomy mapping
        taxonomy = {
            "cs": {
                "name": "Computer Science",
                "subcategories": {
                    "AI": "Artificial Intelligence",
                    "CL": "Computation and Language",
                    "CV": "Computer Vision",
                    "LG": "Machine Learning",
                    "NE": "Neural and Evolutionary Computing",
                },
                "related": ["stat.ML", "math.OC", "q-bio.NC"],
            },
            "stat": {
                "name": "Statistics",
                "subcategories": {
                    "ML": "Machine Learning",
                    "ME": "Methodology",
                    "TH": "Statistics Theory",
                },
                "related": ["cs.LG", "math.ST", "econ.EM"],
            },
            "math": {
                "name": "Mathematics",
                "subcategories": {
                    "OC": "Optimization and Control",
                    "ST": "Statistics Theory",
                    "PR": "Probability",
                },
                "related": ["cs.LG", "stat.TH", "physics.comp-ph"],
            },
        }

        # Parse category
        parts = category.split(".")
        if len(parts) < 2:
            return {}

        main_cat = parts[0]
        sub_cat = parts[1]

        if main_cat not in taxonomy:
            return {}

        main_info = taxonomy[main_cat]
        sub_name = main_info["subcategories"].get(sub_cat, sub_cat)

        return {
            "category": category,
            "main_category": main_cat,
            "main_category_name": main_info["name"],
            "subcategory": sub_cat,
            "subcategory_name": sub_name,
            "siblings": [
                f"{main_cat}.{k}"
                for k in main_info["subcategories"].keys()
                if k != sub_cat
            ],
            "related_categories": main_info["related"],
        }

    async def get_author_papers(
        self, author_name: str, limit: int = 20, include_coauthors: bool = False
    ) -> List[SearchResult]:
        """
        Get all papers by a specific author

        Optionally include papers by frequent coauthors
        """
        try:
            # Build query
            author_query = {
                "query": {
                    "nested": {
                        "path": "authors",
                        "query": {"match": {"authors.name": author_name}},
                    }
                },
                "size": limit,
                "sort": [{"published": {"order": "desc"}}],
            }

            response = self.es_client.search(index=self.arxiv_index, body=author_query)

            results = []
            for hit in response["hits"]["hits"]:
                # Get full document
                doc = self.es_client.get(index=self.arxiv_index, id=hit["_id"])
                result = self._convert_to_search_result(
                    {**hit, "_source": doc["_source"]}
                )
                results.append(result)

            # If requested, add coauthor papers
            if include_coauthors and results:
                coauthors = set()
                for result in results:
                    authors = result.metadata.get("authors", [])
                    for author in authors:
                        if author != author_name:
                            coauthors.add(author)

                # Add papers from top 5 coauthors
                for coauthor in list(coauthors)[:5]:
                    coauthor_papers = await self.get_author_papers(coauthor, limit=5)
                    results.extend(coauthor_papers)

            # Sort by date and limit
            results.sort(key=lambda x: x.metadata.get("published", ""), reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to get author papers: {e}")
            return []

    async def get_trending_papers(
        self, category: Optional[str] = None, days: int = 30, limit: int = 10
    ) -> List[SearchResult]:
        """
        Get trending papers based on recent activity

        Combines recency with download/citation velocity
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Build trending query
            trending_query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "range": {
                                    "published": {
                                        "gte": start_date.isoformat(),
                                        "lte": end_date.isoformat(),
                                    }
                                }
                            }
                        ]
                    }
                },
                "size": limit * 2,  # Get more to filter
                "sort": [
                    {
                        "_script": {
                            "script": {
                                "source": """
                                    double recencyScore = 1.0 / (1.0 + (params.now - doc['published'].value.toInstant().toEpochMilli() / 1000) / 86400);
                                    double citationScore = Math.log(1 + doc.containsKey('citation_count') ? doc['citation_count'].value : 0);
                                    return recencyScore * params.recency_weight + citationScore * params.citation_weight;
                                """,
                                "params": {
                                    "now": end_date.timestamp() * 1000,
                                    "recency_weight": 0.7,
                                    "citation_weight": 0.3,
                                },
                            },
                            "type": "number",
                            "order": "desc",
                        }
                    }
                ],
            }

            # Add category filter if specified
            if category:
                trending_query["query"]["bool"]["filter"] = [
                    {"term": {"categories": category}}
                ]

            response = self.es_client.search(
                index=self.arxiv_index, body=trending_query
            )

            # Convert and return top results
            results = []
            for hit in response["hits"]["hits"][:limit]:
                doc = self.es_client.get(index=self.arxiv_index, id=hit["_id"])
                result = self._convert_to_search_result(
                    {**hit, "_source": doc["_source"]}
                )
                result.metadata["trending_score"] = hit["_score"]
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Failed to get trending papers: {e}")
            return []
