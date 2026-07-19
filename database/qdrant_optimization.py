"""
Qdrant vector database optimization for the Multimodal Enterprise RAG system
"""

import asyncio
import time
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, ScalarQuantization,
    ScalarQuantizationConfig, ScalarType,
    OptimizersConfigDiff, HnswConfigDiff,
    PayloadSchemaType, PayloadIndexParams, CreatePayloadIndexRequest
)
import logging

logger = logging.getLogger(__name__)

@dataclass
class QdrantOptimizationConfig:
    """Qdrant optimization configuration"""
    # Vector parameters
    vector_size: int = 1536  # OpenAI embedding size
    distance: Distance = Distance.COSINE

    # HNSW optimization
    m: int = 16  # Number of edges per node
    ef_construct: int = 100  # Construction time accuracy/speed tradeoff
    ef_search: int = 64  # Search time accuracy/speed tradeoff
    full_scan_threshold: int = 10000  # Threshold for full scan vs HNSW

    # Quantization
    quantization_enabled: bool = True
    quantization_type: ScalarType = ScalarType.INT8
    quantization_ram: bool = True

    # Optimizer configuration
    deleted_threshold: float = 0.2
    vacuum_min_vector_number: int = 1000
    default_segment_number: int = 2
    max_segment_size: int = 200000
    memmap_threshold: int = 50000

    # Payload indexing
    index_payload_fields: List[str] = None
    payload_field_types: Dict[str, PayloadSchemaType] = None

class QdrantOptimizer:
    """Advanced Qdrant optimization manager"""

    def __init__(self, client: QdrantClient, config: QdrantOptimizationConfig = None):
        self.client = client
        self.config = config or QdrantOptimizationConfig()
        self.performance_stats = {
            'search_times': [],
            'upload_times': [],
            'index_sizes': {},
            'collection_stats': {}
        }

    def create_optimized_collection(
        self,
        collection_name: str,
        vector_size: Optional[int] = None,
        distance: Optional[Distance] = None
    ) -> bool:
        """Create an optimized collection with best practices"""
        try:
            vector_size = vector_size or self.config.vector_size
            distance = distance or self.config.distance

            # Configure HNSW for optimal performance
            hnsw_config = HnswConfigDiff(
                m=self.config.m,
                ef_construct=self.config.ef_construct,
                ef_search=self.config.ef_search,
                full_scan_threshold=self.config.full_scan_threshold,
                max_indexing_threads=4  # Optimize for multi-core systems
            )

            # Configure quantization for memory efficiency
            quantization_config = None
            if self.config.quantization_enabled:
                quantization_config = ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=self.config.quantization_type,
                        ram=self.config.quantization_ram
                    )
                )

            # Configure optimizers
            optimizer_config = OptimizersConfigDiff(
                deleted_threshold=self.config.deleted_threshold,
                vacuum_min_vector_number=self.config.vacuum_min_vector_number,
                default_segment_number=self.config.default_segment_number,
                max_segment_size=self.config.max_segment_size,
                memmap_threshold=self.config.memmap_threshold,
                indexing_threshold=20000,
                flush_interval_sec=5,
                max_optimization_threads=4
            )

            # Create collection with optimized configuration
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance,
                    hnsw_config=hnsw_config,
                    quantization_config=quantization_config,
                    on_disk=True  # Enable disk storage for large collections
                ),
                optimizers_config=optimizer_config
            )

            logger.info(f"Created optimized collection: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return False

    def create_payload_indexes(self, collection_name: str) -> bool:
        """Create payload indexes for better filtering performance"""
        try:
            # Common payload fields to index
            payload_fields = self.config.index_payload_fields or [
                'document_id',
                'document_type',
                'tenant_id',
                'created_at',
                'content_type',
                'modality'
            ]

            field_types = self.config.payload_field_types or {
                'document_id': PayloadSchemaType.KEYWORD,
                'document_type': PayloadSchemaType.KEYWORD,
                'tenant_id': PayloadSchemaType.KEYWORD,
                'created_at': PayloadSchemaType.DATETIME,
                'content_type': PayloadSchemaType.KEYWORD,
                'modality': PayloadSchemaType.KEYWORD
            }

            for field in payload_fields:
                if field in field_types:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        payload_index_params=PayloadIndexParams(
                            field_name=field,
                            field_type=field_types[field],
                            field_schema_options={
                                'type': field_types[field].value
                            }
                        )
                    )
                    logger.info(f"Created payload index for field: {field}")

            return True

        except Exception as e:
            logger.error(f"Failed to create payload indexes for {collection_name}: {e}")
            return False

    async def batch_upload_optimized(
        self,
        collection_name: str,
        vectors: List[List[float]],
        payloads: List[Dict],
        ids: List[str],
        batch_size: int = 1000
    ) -> bool:
        """Optimized batch upload with performance monitoring"""
        try:
            total_start_time = time.time()
            uploaded_count = 0

            for i in range(0, len(vectors), batch_size):
                batch_start_time = time.time()

                # Prepare batch
                batch_vectors = vectors[i:i + batch_size]
                batch_payloads = payloads[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]

                # Upload batch
                self.client.upsert(
                    collection_name=collection_name,
                    points=[
                        {
                            'id': idx,
                            'vector': vector,
                            'payload': payload
                        }
                        for idx, vector, payload in zip(batch_ids, batch_vectors, batch_payloads)
                    ]
                )

                batch_time = time.time() - batch_start_time
                uploaded_count += len(batch_vectors)

                # Record performance
                self.performance_stats['upload_times'].append({
                    'batch_size': len(batch_vectors),
                    'time': batch_time,
                    'throughput': len(batch_vectors) / batch_time
                })

                logger.debug(f"Uploaded batch {i//batch_size + 1}: {len(batch_vectors)} vectors in {batch_time:.2f}s")

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.01)

            total_time = time.time() - total_start_time
            logger.info(f"Uploaded {uploaded_count} vectors in {total_time:.2f}s ({uploaded_count/total_time:.1f} vectors/s)")

            return True

        except Exception as e:
            logger.error(f"Batch upload failed for {collection_name}: {e}")
            return False

    async def search_optimized(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict] = None,
        search_params: Optional[Dict] = None
    ) -> List[Dict]:
        """Optimized search with performance monitoring"""
        try:
            start_time = time.time()

            # Configure search parameters for optimal performance
            default_search_params = {
                'hnsw_ef': self.config.ef_search,
                'exact': False  # Use approximate search for speed
            }
            if search_params:
                default_search_params.update(search_params)

            # Perform search
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=filter_conditions,
                limit=limit,
                score_threshold=score_threshold,
                search_params=default_search_params,
                with_payload=True,
                with_vectors=False  # Don't return vectors unless needed
            )

            search_time = time.time() - start_time

            # Record performance
            self.performance_stats['search_times'].append({
                'time': search_time,
                'limit': limit,
                'results_count': len(search_result),
                'throughput': len(search_result) / search_time if search_time > 0 else 0
            })

            # Format results
            results = []
            for hit in search_result:
                results.append({
                    'id': hit.id,
                    'score': hit.score,
                    'payload': hit.payload
                })

            return results

        except Exception as e:
            logger.error(f"Search failed for {collection_name}: {e}")
            return []

    def get_collection_stats(self, collection_name: str) -> Dict:
        """Get detailed collection statistics"""
        try:
            info = self.client.get_collection(collection_name)

            stats = {
                'name': collection_name,
                'vectors_count': info.vectors_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'points_count': info.points_count,
                'segments_count': len(info.segments) if hasattr(info, 'segments') else 0,
                'disk_data_size': info.disk_data_size if hasattr(info, 'disk_data_size') else 0,
                'ram_data_size': info.ram_data_size if hasattr(info, 'ram_data_size') else 0,
                'config': {
                    'vector_size': info.config.params.vectors.size,
                    'distance': info.config.params.vectors.distance.value,
                    'quantization': bool(info.config.params.vectors.quantization_config)
                }
            }

            self.performance_stats['collection_stats'][collection_name] = stats
            return stats

        except Exception as e:
            logger.error(f"Failed to get collection stats for {collection_name}: {e}")
            return {}

    def optimize_collection(self, collection_name: str) -> bool:
        """Trigger collection optimization"""
        try:
            # Force optimization
            self.client.update_collection(
                collection_name=collection_name,
                optimizer_config=OptimizersConfigDiff(
                    max_optimization_threads=4
                )
            )

            logger.info(f"Triggered optimization for collection: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to optimize collection {collection_name}: {e}")
            return False

    def get_performance_stats(self) -> Dict:
        """Get comprehensive performance statistics"""
        stats = dict(self.performance_stats)

        # Calculate averages and percentiles
        if stats['search_times']:
            search_times = [s['time'] for s in stats['search_times']]
            stats['search_stats'] = {
                'avg_time': np.mean(search_times),
                'min_time': np.min(search_times),
                'max_time': np.max(search_times),
                'p95_time': np.percentile(search_times, 95),
                'total_searches': len(search_times)
            }

        if stats['upload_times']:
            upload_throughputs = [u['throughput'] for u in stats['upload_times']]
            stats['upload_stats'] = {
                'avg_throughput': np.mean(upload_throughputs),
                'min_throughput': np.min(upload_throughputs),
                'max_throughput': np.max(upload_throughputs),
                'total_uploaded': sum(u['batch_size'] for u in stats['upload_times'])
            }

        return stats

    def cleanup_old_data(self, collection_name: str, days_old: int = 30) -> bool:
        """Clean up old vectors to maintain performance"""
        try:
            # Calculate cutoff timestamp
            cutoff_time = int((time.time() - days_old * 24 * 3600) * 1000)

            # Delete old points
            self.client.delete(
                collection_name=collection_name,
                points_selector={
                    'filter': {
                        'must': [
                            {
                                'key': 'created_at',
                                'range': {'lt': cutoff_time}
                            }
                        ]
                    }
                }
            )

            logger.info(f"Cleaned up old data from {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup old data from {collection_name}: {e}")
            return False

# Utility functions for vector optimization
def normalize_vectors(vectors: List[List[float]]) -> List[List[float]]:
    """Normalize vectors to unit length for better cosine similarity"""
    normalized = []

    for vector in vectors:
        vector_np = np.array(vector)
        norm = np.linalg.norm(vector_np)
        if norm > 0:
            normalized.append((vector_np / norm).tolist())
        else:
            normalized.append(vector)

    return normalized

def reduce_dimensions(
    vectors: List[List[float]],
    target_dim: int = 256
) -> List[List[float]]:
    """Reduce vector dimensions for faster search (placeholder for PCA/UMAP)"""
    # In production, use sklearn.decomposition.PCA or umap-learn
    # For now, just truncate vectors
    return [vector[:target_dim] for vector in vectors]

def create_optimal_batch_size(total_vectors: int, max_batch_size: int = 1000) -> int:
    """Calculate optimal batch size based on data size"""
    # Smaller batches for smaller datasets, larger for bigger ones
    if total_vectors < 1000:
        return min(100, total_vectors)
    elif total_vectors < 10000:
        return min(500, total_vectors)
    else:
        return max_batch_size