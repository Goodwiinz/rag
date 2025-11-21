"""
Comprehensive Prometheus Metrics Collection
Custom metrics for document processing, WebSocket operations, and system health
"""

import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
import psutil
import json

from prometheus_client import (
    Counter, Histogram, Gauge, Info, Summary,
    CollectorRegistry, REGISTRY, generate_latest,
    CONTENT_TYPE_LATEST, start_http_server
)

class MetricType(Enum):
    """Types of Prometheus metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"

@dataclass
class MetricDefinition:
    """Definition of a Prometheus metric"""
    name: str
    description: str
    metric_type: MetricType
    labels: List[str]
    buckets: Optional[List[float]] = None  # For histograms
    quantiles: Optional[List[float]] = None  # For summaries

class PrometheusMetricsCollector:
    """Comprehensive Prometheus metrics collector for the RAG system"""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or REGISTRY
        self.metrics: Dict[str, Any] = {}
        self.start_time = time.time()

        # Background collection state
        self._collection_tasks: List[asyncio.Task] = []
        self._shutdown = False
        self._collection_interval = 30  # seconds

        # Initialize all metrics
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize all Prometheus metrics"""

        # Application Information
        self.metrics['app_info'] = Info(
            'multimodal_rag_app_info',
            'Multimodal RAG Application Information',
            registry=self.registry
        )
        self.metrics['app_info'].info({
            'version': '1.0.0',
            'environment': 'development',
            'build_date': '2025-01-20',
            'python_version': '3.9+'
        })

        # HTTP/API Metrics
        self.metrics['http_requests_total'] = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code', 'user_role'],
            registry=self.registry
        )

        self.metrics['http_request_duration_seconds'] = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint', 'status_code', 'user_role'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )

        self.metrics['http_request_size_bytes'] = Histogram(
            'http_request_size_bytes',
            'HTTP request size in bytes',
            ['method', 'endpoint'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
            registry=self.registry
        )

        self.metrics['http_response_size_bytes'] = Histogram(
            'http_response_size_bytes',
            'HTTP response size in bytes',
            ['method', 'endpoint', 'status_code'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
            registry=self.registry
        )

        # Document Processing Metrics
        self.metrics['document_processing_total'] = Counter(
            'document_processing_total',
            'Total documents processed',
            ['file_type', 'status', 'user_role'],
            registry=self.registry
        )

        self.metrics['document_processing_duration_seconds'] = Histogram(
            'document_processing_duration_seconds',
            'Document processing duration in seconds',
            ['file_type', 'stage', 'status'],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
            registry=self.registry
        )

        self.metrics['document_processing_queue_size'] = Gauge(
            'document_processing_queue_size',
            'Current size of document processing queue',
            registry=self.registry
        )

        self.metrics['document_processing_active_jobs'] = Gauge(
            'document_processing_active_jobs',
            'Number of active document processing jobs',
            registry=self.registry
        )

        self.metrics['document_size_bytes'] = Histogram(
            'document_size_bytes',
            'Size of processed documents in bytes',
            ['file_type'],
            buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600, 1048576000],
            registry=self.registry
        )

        self.metrics['entities_extracted_total'] = Histogram(
            'entities_extracted_total',
            'Number of entities extracted from documents',
            ['file_type', 'extraction_method'],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
            registry=self.registry
        )

        self.metrics['embeddings_generated_total'] = Histogram(
            'embeddings_generated_total',
            'Number of embeddings generated',
            ['model_name', 'file_type'],
            buckets=[1, 10, 50, 100, 500, 1000, 5000, 10000],
            registry=self.registry
        )

        # WebSocket Metrics
        self.metrics['websocket_connections_total'] = Counter(
            'websocket_connections_total',
            'Total WebSocket connections',
            ['client_type', 'user_role'],
            registry=self.registry
        )

        self.metrics['websocket_connections_active'] = Gauge(
            'websocket_connections_active',
            'Number of active WebSocket connections',
            ['client_type'],
            registry=self.registry
        )

        self.metrics['websocket_messages_total'] = Counter(
            'websocket_messages_total',
            'Total WebSocket messages',
            ['message_type', 'direction', 'status'],
            registry=self.registry
        )

        self.metrics['websocket_message_duration_seconds'] = Histogram(
            'websocket_message_duration_seconds',
            'WebSocket message processing duration',
            ['message_type', 'direction'],
            buckets=[0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
            registry=self.registry
        )

        self.metrics['websocket_message_size_bytes'] = Histogram(
            'websocket_message_size_bytes',
            'WebSocket message size in bytes',
            ['message_type', 'direction'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
            registry=self.registry
        )

        self.metrics['websocket_errors_total'] = Counter(
            'websocket_errors_total',
            'Total WebSocket errors',
            ['error_type', 'client_type'],
            registry=self.registry
        )

        # Database Metrics
        self.metrics['database_query_duration_seconds'] = Histogram(
            'database_query_duration_seconds',
            'Database query duration in seconds',
            ['database', 'operation', 'table'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )

        self.metrics['database_connections_active'] = Gauge(
            'database_connections_active',
            'Number of active database connections',
            ['database'],
            registry=self.registry
        )

        self.metrics['database_connections_pool_size'] = Gauge(
            'database_connections_pool_size',
            'Database connection pool size',
            ['database'],
            registry=self.registry
        )

        self.metrics['database_query_total'] = Counter(
            'database_query_total',
            'Total database queries',
            ['database', 'operation', 'table', 'status'],
            registry=self.registry
        )

        self.metrics['database_rows_affected_total'] = Histogram(
            'database_rows_affected_total',
            'Number of rows affected by database operations',
            ['database', 'operation', 'table'],
            buckets=[1, 10, 50, 100, 500, 1000, 5000, 10000],
            registry=self.registry
        )

        # Cache Metrics
        self.metrics['cache_operations_total'] = Counter(
            'cache_operations_total',
            'Total cache operations',
            ['cache_type', 'operation', 'result'],
            registry=self.registry
        )

        self.metrics['cache_hit_ratio'] = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio',
            ['cache_type'],
            registry=self.registry
        )

        self.metrics['cache_duration_seconds'] = Histogram(
            'cache_operation_duration_seconds',
            'Cache operation duration in seconds',
            ['cache_type', 'operation'],
            buckets=[0.0001, 0.001, 0.01, 0.1, 1.0],
            registry=self.registry
        )

        self.metrics['cache_size_bytes'] = Gauge(
            'cache_size_bytes',
            'Cache size in bytes',
            ['cache_type'],
            registry=self.registry
        )

        # Search Metrics
        self.metrics['search_queries_total'] = Counter(
            'search_queries_total',
            'Total search queries',
            ['search_type', 'query_type', 'status'],
            registry=self.registry
        )

        self.metrics['search_query_duration_seconds'] = Histogram(
            'search_query_duration_seconds',
            'Search query duration in seconds',
            ['search_type', 'query_type'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )

        self.metrics['search_results_total'] = Histogram(
            'search_results_total',
            'Number of search results returned',
            ['search_type', 'query_type'],
            buckets=[0, 1, 5, 10, 25, 50, 100, 250, 500, 1000],
            registry=self.registry
        )

        self.metrics['search_precision_score'] = Gauge(
            'search_precision_score',
            'Search precision score',
            ['search_type'],
            registry=self.registry
        )

        self.metrics['search_recall_score'] = Gauge(
            'search_recall_score',
            'Search recall score',
            ['search_type'],
            registry=self.registry
        )

        # ML/AI Metrics
        self.metrics['ml_inference_duration_seconds'] = Histogram(
            'ml_inference_duration_seconds',
            'ML model inference duration in seconds',
            ['model_name', 'model_type', 'operation'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
            registry=self.registry
        )

        self.metrics['ml_inference_requests_total'] = Counter(
            'ml_inference_requests_total',
            'Total ML inference requests',
            ['model_name', 'model_type', 'status'],
            registry=self.registry
        )

        self.metrics['ml_model_accuracy_score'] = Gauge(
            'ml_model_accuracy_score',
            'ML model accuracy score',
            ['model_name', 'model_type', 'dataset'],
            registry=self.registry
        )

        self.metrics['ml_model_confidence_score'] = Histogram(
            'ml_model_confidence_score',
            'ML model confidence scores',
            ['model_name', 'model_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )

        # System Resource Metrics
        self.metrics['system_cpu_percent'] = Gauge(
            'system_cpu_percent',
            'System CPU usage percentage',
            ['core'],
            registry=self.registry
        )

        self.metrics['system_memory_bytes'] = Gauge(
            'system_memory_bytes',
            'System memory usage in bytes',
            ['type'],  # total, available, used, free
            registry=self.registry
        )

        self.metrics['system_disk_bytes'] = Gauge(
            'system_disk_bytes',
            'System disk usage in bytes',
            ['device', 'type'],  # total, used, free
            registry=self.registry
        )

        self.metrics['system_network_bytes_total'] = Counter(
            'system_network_bytes_total',
            'Total network bytes transferred',
            ['interface', 'direction'],
            registry=self.registry
        )

        self.metrics['system_load_average'] = Gauge(
            'system_load_average',
            'System load average',
            ['period'],  # 1m, 5m, 15m
            registry=self.registry
        )

        self.metrics['system_uptime_seconds'] = Gauge(
            'system_uptime_seconds',
            'System uptime in seconds',
            registry=self.registry
        )

        # Business Metrics
        self.metrics['user_sessions_total'] = Counter(
            'user_sessions_total',
            'Total user sessions',
            ['user_type', 'auth_method'],
            registry=self.registry
        )

        self.metrics['user_session_duration_seconds'] = Histogram(
            'user_session_duration_seconds',
            'User session duration in seconds',
            ['user_type'],
            buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800],
            registry=self.registry
        )

        self.metrics['organizations_total'] = Gauge(
            'organizations_total',
            'Total number of organizations',
            ['status'],
            registry=self.registry
        )

        self.metrics['documents_in_system_total'] = Gauge(
            'documents_in_system_total',
            'Total documents in the system',
            ['status', 'file_type'],
            registry=self.registry
        )

        self.metrics['feature_usage_total'] = Counter(
            'feature_usage_total',
            'Total feature usage',
            ['feature_name', 'action', 'user_type'],
            registry=self.registry
        )

    # HTTP Metrics Recording
    def record_http_request(self, method: str, endpoint: str, status_code: int,
                          duration_seconds: float, user_role: str = "anonymous",
                          request_size_bytes: Optional[int] = None,
                          response_size_bytes: Optional[int] = None):
        """Record HTTP request metrics"""
        self.metrics['http_requests_total'].labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            user_role=user_role
        ).inc()

        self.metrics['http_request_duration_seconds'].labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            user_role=user_role
        ).observe(duration_seconds)

        if request_size_bytes is not None:
            self.metrics['http_request_size_bytes'].labels(
                method=method,
                endpoint=endpoint
            ).observe(request_size_bytes)

        if response_size_bytes is not None:
            self.metrics['http_response_size_bytes'].labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code)
            ).observe(response_size_bytes)

    # Document Processing Metrics Recording
    def record_document_processing_start(self, file_type: str, user_role: str = "user"):
        """Record document processing start"""
        self.metrics['document_processing_total'].labels(
            file_type=file_type,
            status="started",
            user_role=user_role
        ).inc()

    def record_document_processing_complete(self, file_type: str, status: str,
                                         duration_seconds: float,
                                         user_role: str = "user",
                                         entities_count: int = 0,
                                         embeddings_count: int = 0,
                                         file_size_bytes: Optional[int] = None):
        """Record document processing completion"""
        self.metrics['document_processing_total'].labels(
            file_type=file_type,
            status=status,
            user_role=user_role
        ).inc()

        self.metrics['document_processing_duration_seconds'].labels(
            file_type=file_type,
            stage="complete",
            status=status
        ).observe(duration_seconds)

        if file_size_bytes is not None:
            self.metrics['document_size_bytes'].labels(
                file_type=file_type
            ).observe(file_size_bytes)

        if entities_count > 0:
            self.metrics['entities_extracted_total'].labels(
                file_type=file_type,
                extraction_method="automatic"
            ).observe(entities_count)

        if embeddings_count > 0:
            self.metrics['embeddings_generated_total'].labels(
                model_name="default",
                file_type=file_type
            ).observe(embeddings_count)

    def update_processing_queue_metrics(self, queue_size: int, active_jobs: int):
        """Update processing queue metrics"""
        self.metrics['document_processing_queue_size'].set(queue_size)
        self.metrics['document_processing_active_jobs'].set(active_jobs)

    # WebSocket Metrics Recording
    def record_websocket_connection(self, client_type: str = "web",
                                  user_role: str = "user",
                                  connected: bool = True):
        """Record WebSocket connection"""
        if connected:
            self.metrics['websocket_connections_total'].labels(
                client_type=client_type,
                user_role=user_role
            ).inc()

            self.metrics['websocket_connections_active'].labels(
                client_type=client_type
            ).inc()
        else:
            self.metrics['websocket_connections_active'].labels(
                client_type=client_type
            ).dec()

    def record_websocket_message(self, message_type: str, direction: str,
                                status: str, duration_seconds: float,
                                message_size_bytes: Optional[int] = None):
        """Record WebSocket message metrics"""
        self.metrics['websocket_messages_total'].labels(
            message_type=message_type,
            direction=direction,
            status=status
        ).inc()

        self.metrics['websocket_message_duration_seconds'].labels(
            message_type=message_type,
            direction=direction
        ).observe(duration_seconds)

        if message_size_bytes is not None:
            self.metrics['websocket_message_size_bytes'].labels(
                message_type=message_type,
                direction=direction
            ).observe(message_size_bytes)

    def record_websocket_error(self, error_type: str, client_type: str = "web"):
        """Record WebSocket error"""
        self.metrics['websocket_errors_total'].labels(
            error_type=error_type,
            client_type=client_type
        ).inc()

    # Database Metrics Recording
    def record_database_query(self, database: str, operation: str, table: str,
                            duration_seconds: float, status: str,
                            rows_affected: Optional[int] = None):
        """Record database query metrics"""
        self.metrics['database_query_total'].labels(
            database=database,
            operation=operation,
            table=table,
            status=status
        ).inc()

        self.metrics['database_query_duration_seconds'].labels(
            database=database,
            operation=operation,
            table=table
        ).observe(duration_seconds)

        if rows_affected is not None:
            self.metrics['database_rows_affected_total'].labels(
                database=database,
                operation=operation,
                table=table
            ).observe(rows_affected)

    def update_database_connection_metrics(self, database: str, active_connections: int,
                                         pool_size: int):
        """Update database connection metrics"""
        self.metrics['database_connections_active'].labels(
            database=database
        ).set(active_connections)

        self.metrics['database_connections_pool_size'].labels(
            database=database
        ).set(pool_size)

    # Cache Metrics Recording
    def record_cache_operation(self, cache_type: str, operation: str,
                             result: str, duration_seconds: float):
        """Record cache operation metrics"""
        self.metrics['cache_operations_total'].labels(
            cache_type=cache_type,
            operation=operation,
            result=result
        ).inc()

        self.metrics['cache_duration_seconds'].labels(
            cache_type=cache_type,
            operation=operation
        ).observe(duration_seconds)

    def update_cache_hit_ratio(self, cache_type: str, hit_ratio: float):
        """Update cache hit ratio"""
        self.metrics['cache_hit_ratio'].labels(
            cache_type=cache_type
        ).set(hit_ratio)

    def update_cache_size(self, cache_type: str, size_bytes: int):
        """Update cache size"""
        self.metrics['cache_size_bytes'].labels(
            cache_type=cache_type
        ).set(size_bytes)

    # Search Metrics Recording
    def record_search_query(self, search_type: str, query_type: str,
                          status: str, duration_seconds: float,
                          results_count: int, precision_score: Optional[float] = None,
                          recall_score: Optional[float] = None):
        """Record search query metrics"""
        self.metrics['search_queries_total'].labels(
            search_type=search_type,
            query_type=query_type,
            status=status
        ).inc()

        self.metrics['search_query_duration_seconds'].labels(
            search_type=search_type,
            query_type=query_type
        ).observe(duration_seconds)

        self.metrics['search_results_total'].labels(
            search_type=search_type,
            query_type=query_type
        ).observe(results_count)

        if precision_score is not None:
            self.metrics['search_precision_score'].labels(
                search_type=search_type
            ).set(precision_score)

        if recall_score is not None:
            self.metrics['search_recall_score'].labels(
                search_type=search_type
            ).set(recall_score)

    # ML Metrics Recording
    def record_ml_inference(self, model_name: str, model_type: str, operation: str,
                          duration_seconds: float, status: str,
                          confidence_score: Optional[float] = None):
        """Record ML inference metrics"""
        self.metrics['ml_inference_requests_total'].labels(
            model_name=model_name,
            model_type=model_type,
            status=status
        ).inc()

        self.metrics['ml_inference_duration_seconds'].labels(
            model_name=model_name,
            model_type=model_type,
            operation=operation
        ).observe(duration_seconds)

        if confidence_score is not None:
            self.metrics['ml_model_confidence_score'].labels(
                model_name=model_name,
                model_type=model_type
            ).observe(confidence_score)

    def update_ml_model_accuracy(self, model_name: str, model_type: str,
                                dataset: str, accuracy_score: float):
        """Update ML model accuracy"""
        self.metrics['ml_model_accuracy_score'].labels(
            model_name=model_name,
            model_type=model_type,
            dataset=dataset
        ).set(accuracy_score)

    # System Metrics Collection
    async def collect_system_metrics(self):
        """Collect system resource metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)

            # Update overall CPU
            self.metrics['system_cpu_percent'].labels(core="overall").set(cpu_percent)

            # Update per-core CPU
            for i, core_percent in enumerate(cpu_per_core):
                self.metrics['system_cpu_percent'].labels(core=f"core_{i}").set(core_percent)

            # Memory metrics
            memory = psutil.virtual_memory()
            self.metrics['system_memory_bytes'].labels(type="total").set(memory.total)
            self.metrics['system_memory_bytes'].labels(type="available").set(memory.available)
            self.metrics['system_memory_bytes'].labels(type="used").set(memory.used)
            self.metrics['system_memory_bytes'].labels(type="free").set(memory.free)

            # Disk metrics
            disk = psutil.disk_usage('/')
            self.metrics['system_disk_bytes'].labels(device="/", type="total").set(disk.total)
            self.metrics['system_disk_bytes'].labels(device="/", type="used").set(disk.used)
            self.metrics['system_disk_bytes'].labels(device="/", type="free").set(disk.free)

            # Network metrics
            network = psutil.net_io_counters()
            self.metrics['system_network_bytes_total'].labels(
                interface="all", direction="sent"
            )._value._value.set(network.bytes_sent)
            self.metrics['system_network_bytes_total'].labels(
                interface="all", direction="recv"
            )._value._value.set(network.bytes_recv)

            # Load average (Unix-like systems)
            try:
                load_avg = psutil.getloadavg()
                self.metrics['system_load_average'].labels(period="1m").set(load_avg[0])
                self.metrics['system_load_average'].labels(period="5m").set(load_avg[1])
                self.metrics['system_load_average'].labels(period="15m").set(load_avg[2])
            except AttributeError:
                # Not available on Windows
                pass

            # Uptime
            self.metrics['system_uptime_seconds'].set(time.time() - self.start_time)

        except Exception as e:
            # Log error but don't crash metrics collection
            pass

    # Business Metrics Recording
    def record_user_session(self, user_type: str, auth_method: str,
                          duration_seconds: Optional[float] = None):
        """Record user session metrics"""
        self.metrics['user_sessions_total'].labels(
            user_type=user_type,
            auth_method=auth_method
        ).inc()

        if duration_seconds is not None:
            self.metrics['user_session_duration_seconds'].labels(
                user_type=user_type
            ).observe(duration_seconds)

    def update_organizations_count(self, active_count: int, total_count: int):
        """Update organization counts"""
        self.metrics['organizations_total'].labels(status="active").set(active_count)
        self.metrics['organizations_total'].labels(status="total").set(total_count)

    def update_documents_count(self, status: str, file_type: str, count: int):
        """Update document counts"""
        self.metrics['documents_in_system_total'].labels(
            status=status,
            file_type=file_type
        ).set(count)

    def record_feature_usage(self, feature_name: str, action: str,
                            user_type: str = "user"):
        """Record feature usage"""
        self.metrics['feature_usage_total'].labels(
            feature_name=feature_name,
            action=action,
            user_type=user_type
        ).inc()

    def start_metrics_server(self, port: int = 8001):
        """Start Prometheus metrics HTTP server"""
        start_http_server(port)
        print(f"Prometheus metrics server started on port {port}")

    def get_metrics(self) -> str:
        """Get current metrics in Prometheus format"""
        return generate_latest(self.registry).decode('utf-8')

    async def start_background_collection(self):
        """Start background metrics collection"""
        if self._collection_tasks:
            return  # Already started

        self._collection_tasks = [
            asyncio.create_task(self._collection_loop())
        ]

    async def stop_background_collection(self):
        """Stop background metrics collection"""
        self._shutdown = True

        for task in self._collection_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._collection_tasks.clear()

    async def _collection_loop(self):
        """Background loop for collecting metrics"""
        while not self._shutdown:
            try:
                await self.collect_system_metrics()
                await asyncio.sleep(self._collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue collection
                await asyncio.sleep(5)  # Brief delay on error

# Global metrics collector instance
prometheus_metrics = PrometheusMetricsCollector()

# Convenience functions
def record_http_request(method: str, endpoint: str, status_code: int,
                      duration_seconds: float, **kwargs):
    """Record HTTP request metrics"""
    prometheus_metrics.record_http_request(method, endpoint, status_code, duration_seconds, **kwargs)

def record_document_processing(file_type: str, status: str, duration_seconds: float, **kwargs):
    """Record document processing metrics"""
    prometheus_metrics.record_document_processing_complete(file_type, status, duration_seconds, **kwargs)

def record_websocket_event(event_type: str, **kwargs):
    """Record WebSocket event metrics"""
    if event_type == "connection":
        prometheus_metrics.record_websocket_connection(**kwargs)
    elif event_type == "message":
        prometheus_metrics.record_websocket_message(**kwargs)
    elif event_type == "error":
        prometheus_metrics.record_websocket_error(**kwargs)

def record_database_operation(database: str, operation: str, table: str,
                            duration_seconds: float, status: str, **kwargs):
    """Record database operation metrics"""
    prometheus_metrics.record_database_query(database, operation, table, duration_seconds, status, **kwargs)

def record_search_performance(search_type: str, duration_seconds: float,
                            results_count: int, **kwargs):
    """Record search performance metrics"""
    prometheus_metrics.record_search_query(
        search_type, "user_query", "success", duration_seconds, results_count, **kwargs
    )