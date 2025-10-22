"""
Automated Optimization System for the Multimodal Enterprise RAG System

This module provides self-tuning and auto-scaling capabilities that automatically
optimize system performance based on real-time metrics and machine learning.
"""

import asyncio
import json
import logging
import time
import statistics
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import deque, defaultdict
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import redis
import aiofiles
import subprocess
import psutil
import yaml
import requests
from contextlib import asynccontextmanager
import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class OptimizationAction:
    """Represents an optimization action"""
    id: str
    name: str
    description: str
    action_type: str  # 'config', 'scale', 'cache', 'index', 'cleanup'
    target_component: str
    parameters: Dict[str, Any]
    expected_impact: Dict[str, float]
    rollback_parameters: Optional[Dict[str, Any]]
    confidence_score: float
    execution_time: Optional[float] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None

@dataclass
class PerformancePattern:
    """Represents a detected performance pattern"""
    pattern_id: str
    pattern_type: str  # 'seasonal', 'trend', 'anomaly', 'correlation'
    description: str
    confidence: float
    metrics: List[str]
    time_range: Tuple[datetime, datetime]
    parameters: Dict[str, Any]
    recommendations: List[str]

@dataclass
class OptimizationTarget:
    """Optimization target definition"""
    name: str
    description: str
    metric_name: str
    target_value: float
    acceptable_range: Tuple[float, float]
    priority: int  # 1-10, 1 being highest
    optimization_strategies: List[str]

class MLPerformancePredictor:
    """Machine learning-based performance prediction"""

    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.feature_columns: List[str] = []
        self.target_columns: List[str] = []
        self.anomaly_detector: IsolationForest = None
        self.is_trained = False
        self.model_update_interval = 3600  # 1 hour
        self.last_model_update = 0

    async def initialize(self):
        """Initialize the ML predictor"""
        self.feature_columns = [
            'cpu_percent', 'memory_percent', 'disk_percent',
            'connections_active', 'requests_per_second',
            'avg_response_time', 'cache_hit_ratio'
        ]
        self.target_columns = [
            'response_time_p95', 'error_rate', 'throughput'
        ]

        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42
        )

        await self._train_initial_models()
        self.is_trained = True
        logger.info("ML Performance Predictor initialized")

    async def _train_initial_models(self):
        """Train initial ML models"""
        # Generate synthetic training data for initial models
        # In production, this would use historical data
        synthetic_data = self._generate_synthetic_training_data()

        if len(synthetic_data) > 100:
            await self.update_models(synthetic_data)

    def _generate_synthetic_training_data(self) -> pd.DataFrame:
        """Generate synthetic training data"""
        np.random.seed(42)
        n_samples = 1000

        # Generate realistic system metrics
        cpu_percent = np.random.beta(2, 5, n_samples) * 100
        memory_percent = np.random.beta(2, 3, n_samples) * 100
        disk_percent = np.random.uniform(20, 80, n_samples)
        connections_active = np.random.poisson(50, n_samples)
        requests_per_second = np.random.exponential(100, n_samples)

        # Simulate relationships
        avg_response_time = 50 + cpu_percent * 2 + memory_percent * 1.5 + np.random.normal(0, 20, n_samples)
        avg_response_time = np.maximum(10, avg_response_time)

        cache_hit_ratio = np.random.beta(5, 2, n_samples) * 0.3 + 0.7

        # Calculate target variables
        response_time_p95 = avg_response_time * (1 + np.random.exponential(0.3, n_samples))
        error_rate = np.maximum(0, 0.001 + (cpu_percent / 100) ** 2 + np.random.normal(0, 0.01, n_samples))
        throughput = requests_per_second * (1 - error_rate) * cache_hit_ratio

        return pd.DataFrame({
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'disk_percent': disk_percent,
            'connections_active': connections_active,
            'requests_per_second': requests_per_second,
            'avg_response_time': avg_response_time,
            'cache_hit_ratio': cache_hit_ratio,
            'response_time_p95': response_time_p95,
            'error_rate': error_rate,
            'throughput': throughput
        })

    async def update_models(self, data: pd.DataFrame):
        """Update ML models with new data"""
        try:
            # Prepare features
            X = data[self.feature_columns]
            y_response_time = data['response_time_p95']
            y_error_rate = data['error_rate']
            y_throughput = data['throughput']

            # Scale features
            if 'scaler_features' not in self.scalers:
                self.scalers['scaler_features'] = StandardScaler()
                X_scaled = self.scalers['scaler_features'].fit_transform(X)
            else:
                X_scaled = self.scalers['scaler_features'].transform(X)

            # Train regression models
            for target_name, y_data in [
                ('response_time', y_response_time),
                ('error_rate', y_error_rate),
                ('throughput', y_throughput)
            ]:
                model = RandomForestRegressor(
                    n_estimators=100,
                    random_state=42,
                    n_jobs=-1
                )

                X_train, X_test, y_train, y_test = train_test_split(
                    X_scaled, y_data, test_size=0.2, random_state=42
                )

                model.fit(X_train, y_train)
                score = model.score(X_test, y_test)

                self.models[target_name] = {
                    'model': model,
                    'score': score,
                    'feature_importance': dict(zip(self.feature_columns, model.feature_importances_))
                }

                logger.info(f"Updated {target_name} model with R² score: {score:.3f}")

            # Train anomaly detector
            self.anomaly_detector.fit(X_scaled)

            self.last_model_update = time.time()
            logger.info("ML models updated successfully")

        except Exception as e:
            logger.error(f"Error updating ML models: {e}")

    async def predict_performance(self, current_metrics: Dict[str, Any]) -> Dict[str, float]:
        """Predict future performance based on current metrics"""
        if not self.is_trained:
            return {}

        try:
            # Prepare features
            feature_data = []
            for col in self.feature_columns:
                value = current_metrics.get(col, 0)
                feature_data.append(value)

            X = np.array([feature_data])
            X_scaled = self.scalers['scaler_features'].transform(X)

            predictions = {}
            for target_name, model_data in self.models.items():
                prediction = model_data['model'].predict(X_scaled)[0]
                predictions[target_name] = float(prediction)

            return predictions

        except Exception as e:
            logger.error(f"Error predicting performance: {e}")
            return {}

    def detect_anomalies(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalies in metrics"""
        if not self.is_trained or len(metrics) < 10:
            return []

        try:
            # Prepare data
            data = []
            for metric in metrics[-100:]:  # Use last 100 data points
                feature_data = []
                for col in self.feature_columns:
                    value = metric.get(col, 0)
                    feature_data.append(value)
                data.append(feature_data)

            if not data:
                return []

            X = np.array(data)
            X_scaled = self.scalers['scaler_features'].transform(X)

            # Detect anomalies
            anomaly_labels = self.anomaly_detector.predict(X_scaled)
            anomaly_scores = self.anomaly_detector.decision_function(X_scaled)

            anomalies = []
            for i, (label, score) in enumerate(zip(anomaly_labels, anomaly_scores)):
                if label == -1:  # Anomaly detected
                    anomalies.append({
                        'timestamp': metrics[-len(data) + i].get('timestamp', datetime.now().isoformat()),
                        'score': float(score),
                        'metrics': metrics[-len(data) + i],
                        'severity': 'high' if score < -0.5 else 'medium'
                    })

            return anomalies

        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []

class AutomatedOptimizer:
    """Main automated optimization engine"""

    def __init__(self):
        self.ml_predictor = MLPerformancePredictor()
        self.optimization_targets: Dict[str, OptimizationTarget] = {}
        self.optimization_history: List[OptimizationAction] = []
        self.performance_patterns: List[PerformancePattern] = []
        self.active_optimizations: Dict[str, OptimizationAction] = {}
        self.is_running = False
        self.optimization_interval = 300  # 5 minutes
        self.redis_client: Optional[redis.Redis] = None
        self.system_config: Dict[str, Any] = {}

    async def initialize(self, redis_url: Optional[str] = None, config_file: Optional[str] = None):
        """Initialize the automated optimizer"""
        if redis_url:
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()

        # Load configuration
        if config_file:
            await self._load_config(config_file)
        else:
            self._setup_default_config()

        # Initialize ML predictor
        await self.ml_predictor.initialize()

        # Setup optimization targets
        self._setup_optimization_targets()

        logger.info("Automated Optimizer initialized")

    async def _load_config(self, config_file: str):
        """Load configuration from file"""
        try:
            async with aiofiles.open(config_file, 'r') as f:
                content = await f.read()
                self.system_config = yaml.safe_load(content)
        except Exception as e:
            logger.error(f"Error loading config file {config_file}: {e}")
            self._setup_default_config()

    def _setup_default_config(self):
        """Setup default system configuration"""
        self.system_config = {
            'optimization': {
                'enabled': True,
                'auto_apply': False,  # Require manual approval by default
                'confidence_threshold': 0.7,
                'max_concurrent_optimizations': 3,
                'rollback_timeout': 300  # 5 minutes
            },
            'components': {
                'database': {
                    'enabled': True,
                    'config_file': '/etc/postgresql/postgresql.conf',
                    'restart_command': 'systemctl restart postgresql'
                },
                'application': {
                    'enabled': True,
                    'config_file': 'config.yaml',
                    'restart_command': 'systemctl restart rag-app'
                },
                'cache': {
                    'enabled': True,
                    'redis_url': 'redis://localhost:6379'
                }
            },
            'ml': {
                'model_update_interval': 3600,
                'prediction_window': 300,  # 5 minutes
                'anomaly_threshold': 0.1
            }
        }

    def _setup_optimization_targets(self):
        """Setup optimization targets"""
        self.optimization_targets = {
            'response_time': OptimizationTarget(
                name='Response Time',
                description='95th percentile response time',
                metric_name='response_time_p95',
                target_value=200.0,
                acceptable_range=(150.0, 300.0),
                priority=1,
                optimization_strategies=['config', 'scale', 'cache', 'index']
            ),
            'error_rate': OptimizationTarget(
                name='Error Rate',
                description='Application error rate',
                metric_name='error_rate',
                target_value=0.001,
                acceptable_range=(0.0, 0.01),
                priority=1,
                optimization_strategies=['config', 'scale', 'cleanup']
            ),
            'throughput': OptimizationTarget(
                name='Throughput',
                description='Requests per second',
                metric_name='throughput',
                target_value=1000.0,
                acceptable_range=(800.0, 1500.0),
                priority=2,
                optimization_strategies=['scale', 'cache', 'config']
            ),
            'cpu_usage': OptimizationTarget(
                name='CPU Usage',
                description='System CPU usage percentage',
                metric_name='cpu_percent',
                target_value=70.0,
                acceptable_range=(50.0, 85.0),
                priority=3,
                optimization_strategies=['scale', 'config']
            ),
            'memory_usage': OptimizationTarget(
                name='Memory Usage',
                description='System memory usage percentage',
                metric_name='memory_percent',
                target_value=75.0,
                acceptable_range=(60.0, 90.0),
                priority=3,
                optimization_strategies=['scale', 'cleanup', 'config']
            )
        }

    async def start_optimization(self):
        """Start the automated optimization loop"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting automated optimization loop")

        # Start optimization tasks
        asyncio.create_task(self._optimization_loop())
        asyncio.create_task(self._pattern_detection_loop())
        asyncio.create_task(self._ml_model_update_loop())

    async def stop_optimization(self):
        """Stop the automated optimization loop"""
        self.is_running = False
        logger.info("Stopping automated optimization loop")

    async def _optimization_loop(self):
        """Main optimization loop"""
        while self.is_running:
            try:
                # Get current metrics
                current_metrics = await self._collect_current_metrics()

                if current_metrics:
                    # Predict future performance
                    predictions = await self.ml_predictor.predict_performance(current_metrics)

                    # Detect performance issues
                    issues = await self._detect_performance_issues(current_metrics, predictions)

                    # Generate optimization recommendations
                    recommendations = await self._generate_optimization_recommendations(current_metrics, predictions, issues)

                    # Apply optimizations if auto-apply is enabled
                    if self.system_config['optimization']['auto_apply']:
                        await self._apply_optimizations(recommendations)

                await asyncio.sleep(self.optimization_interval)

            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _pattern_detection_loop(self):
        """Detect performance patterns"""
        while self.is_running:
            try:
                # Collect historical data
                historical_data = await self._collect_historical_data(hours=24)

                if len(historical_data) > 100:
                    # Detect patterns
                    patterns = await self._detect_performance_patterns(historical_data)
                    self.performance_patterns = patterns

                    # Update ML models if enough data
                    if time.time() - self.ml_predictor.last_model_update > self.ml_predictor.model_update_interval:
                        df = pd.DataFrame(historical_data)
                        await self.ml_predictor.update_models(df)

                await asyncio.sleep(3600)  # Check patterns every hour

            except Exception as e:
                logger.error(f"Error in pattern detection loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _ml_model_update_loop(self):
        """Update ML models periodically"""
        while self.is_running:
            try:
                # Collect recent data for model training
                recent_data = await self._collect_historical_data(hours=6)

                if len(recent_data) > 500:
                    df = pd.DataFrame(recent_data)
                    await self.ml_predictor.update_models(df)

                await asyncio.sleep(self.ml_predictor.model_update_interval)

            except Exception as e:
                logger.error(f"Error in ML model update loop: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error

    async def _collect_current_metrics(self) -> Optional[Dict[str, Any]]:
        """Collect current system metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Application metrics (would be collected from your application)
            app_metrics = await self._collect_application_metrics()

            # Database metrics (would be collected from your database)
            db_metrics = await self._collect_database_metrics()

            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': (disk.used / disk.total) * 100,
                'connections_active': app_metrics.get('active_connections', 0),
                'requests_per_second': app_metrics.get('requests_per_second', 0),
                'avg_response_time': app_metrics.get('avg_response_time', 0),
                'cache_hit_ratio': app_metrics.get('cache_hit_ratio', 0),
                **db_metrics
            }

            return metrics

        except Exception as e:
            logger.error(f"Error collecting current metrics: {e}")
            return None

    async def _collect_application_metrics(self) -> Dict[str, Any]:
        """Collect application-specific metrics"""
        # This would integrate with your application monitoring
        # For now, return placeholder data
        return {
            'active_connections': 45,
            'requests_per_second': 120.5,
            'avg_response_time': 85.2,
            'cache_hit_ratio': 0.85,
            'error_rate': 0.002
        }

    async def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect database metrics"""
        # This would connect to your database and collect metrics
        # For now, return placeholder data
        return {
            'db_connections_active': 15,
            'db_connections_idle': 35,
            'db_queries_per_second': 95.2,
            'db_avg_query_time': 45.8,
            'db_cache_hit_ratio': 0.92,
            'db_slow_queries': 2
        }

    async def _collect_historical_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Collect historical performance data"""
        if not self.redis_client:
            return []

        try:
            # Get data from Redis
            pattern = "metrics:snapshot:*"
            keys = await self.redis_client.keys(pattern)

            cutoff_time = datetime.now() - timedelta(hours=hours)
            data = []

            for key in keys:
                try:
                    json_data = await self.redis_client.get(key)
                    if json_data:
                        snapshot = json.loads(json_data)
                        timestamp = datetime.fromisoformat(snapshot['timestamp'].replace('Z', '+00:00'))

                        if timestamp > cutoff_time:
                            # Flatten the snapshot into metrics
                            metrics = {
                                'timestamp': snapshot['timestamp'],
                                **snapshot.get('systemMetrics', {}),
                                **snapshot.get('applicationMetrics', {}),
                                **snapshot.get('databaseMetrics', {}),
                                **snapshot.get('networkMetrics', {})
                            }
                            data.append(metrics)
                except Exception as e:
                    logger.error(f"Error processing key {key}: {e}")

            return sorted(data, key=lambda x: x['timestamp'])

        except Exception as e:
            logger.error(f"Error collecting historical data: {e}")
            return []

    async def _detect_performance_issues(
        self,
        current_metrics: Dict[str, Any],
        predictions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect current and predicted performance issues"""
        issues = []

        # Check current metrics against targets
        for target_name, target in self.optimization_targets.items():
            current_value = current_metrics.get(target.metric_name)
            predicted_value = predictions.get(target_name)

            if current_value is not None:
                # Check if current value is outside acceptable range
                if current_value < target.acceptable_range[0] or current_value > target.acceptable_range[1]:
                    severity = 'high' if target.priority <= 2 else 'medium'
                    issues.append({
                        'type': 'current',
                        'target': target_name,
                        'current_value': current_value,
                        'target_value': target.target_value,
                        'severity': severity,
                        'description': f"{target.name} is {current_value:.2f} (target: {target.target_value:.2f})"
                    })

            # Check predicted values
            if predicted_value is not None:
                if predicted_value < target.acceptable_range[0] or predicted_value > target.acceptable_range[1]:
                    severity = 'high' if target.priority <= 2 else 'medium'
                    issues.append({
                        'type': 'predicted',
                        'target': target_name,
                        'predicted_value': predicted_value,
                        'target_value': target.target_value,
                        'severity': severity,
                        'description': f"{target.name} predicted to be {predicted_value:.2f} (target: {target.target_value:.2f})"
                    })

        # Detect anomalies
        historical_data = await self._collect_historical_data(hours=1)
        if len(historical_data) > 10:
            anomalies = self.ml_predictor.detect_anomalies(historical_data)
            for anomaly in anomalies:
                issues.append({
                    'type': 'anomaly',
                    'severity': anomaly['severity'],
                    'description': f"Performance anomaly detected (score: {anomaly['score']:.3f})",
                    'anomaly_data': anomaly
                })

        return issues

    async def _generate_optimization_recommendations(
        self,
        current_metrics: Dict[str, Any],
        predictions: Dict[str, Any],
        issues: List[Dict[str, Any]]
    ) -> List[OptimizationAction]:
        """Generate optimization recommendations based on detected issues"""
        recommendations = []

        for issue in issues:
            target_name = issue.get('target')
            if target_name and target_name in self.optimization_targets:
                target = self.optimization_targets[target_name]

                # Generate recommendations based on issue type and target strategies
                for strategy in target.optimization_strategies:
                    action = await self._create_optimization_action(
                        strategy, target, issue, current_metrics
                    )
                    if action:
                        recommendations.append(action)

        # Remove duplicate recommendations
        seen_actions = set()
        unique_recommendations = []
        for rec in recommendations:
            action_key = (rec.action_type, rec.target_component, str(sorted(rec.parameters.items())))
            if action_key not in seen_actions:
                seen_actions.add(action_key)
                unique_recommendations.append(rec)

        # Sort by confidence and priority
        unique_recommendations.sort(key=lambda x: (x.confidence_score, -self.optimization_targets.get(x.name.split()[0], OptimizationTarget('', '', '', 0, (0, 0), 5, [])).priority), reverse=True)

        return unique_recommendations[:5]  # Return top 5 recommendations

    async def _create_optimization_action(
        self,
        strategy: str,
        target: OptimizationTarget,
        issue: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> Optional[OptimizationAction]:
        """Create a specific optimization action"""
        try:
            if strategy == 'config':
                return await self._create_config_optimization(target, issue, current_metrics)
            elif strategy == 'scale':
                return await self._create_scaling_optimization(target, issue, current_metrics)
            elif strategy == 'cache':
                return await self._create_cache_optimization(target, issue, current_metrics)
            elif strategy == 'index':
                return await self._create_index_optimization(target, issue, current_metrics)
            elif strategy == 'cleanup':
                return await self._create_cleanup_optimization(target, issue, current_metrics)

        except Exception as e:
            logger.error(f"Error creating optimization action for {strategy}: {e}")
            return None

    async def _create_config_optimization(
        self,
        target: OptimizationTarget,
        issue: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> OptimizationAction:
        """Create configuration optimization action"""
        if target.metric_name in ['response_time_p95', 'avg_response_time']:
            # Optimize database connection pool
            return OptimizationAction(
                id=f"config_db_pool_{int(time.time())}",
                name="Optimize Database Connection Pool",
                description="Increase database connection pool size to improve response time",
                action_type="config",
                target_component="database",
                parameters={
                    "max_connections": min(200, current_metrics.get('connections_active', 50) * 2),
                    "min_connections": max(10, current_metrics.get('connections_active', 50) // 2),
                    "connection_timeout": 30
                },
                expected_impact={"response_time": -15.0, "throughput": 10.0},
                rollback_parameters={
                    "max_connections": 100,
                    "min_connections": 20,
                    "connection_timeout": 30
                },
                confidence_score=0.8
            )

        elif target.metric_name == 'memory_percent':
            # Optimize application memory settings
            return OptimizationAction(
                id=f"config_memory_{int(time.time())}",
                name="Optimize Memory Configuration",
                description="Adjust memory settings to reduce memory usage",
                action_type="config",
                target_component="application",
                parameters={
                    "heap_size": "1g",
                    "gc_settings": {
                        "g1_heap_region_size": "16m",
                        "max_gcpause_millis": "200"
                    }
                },
                expected_impact={"memory_usage": -20.0},
                rollback_parameters={
                    "heap_size": "2g",
                    "gc_settings": {
                        "g1_heap_region_size": "32m",
                        "max_gcpause_millis": "400"
                    }
                },
                confidence_score=0.7
            )

        return None

    async def _create_scaling_optimization(
        self,
        target: OptimizationTarget,
        issue: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> OptimizationAction:
        """Create scaling optimization action"""
        if target.metric_name in ['cpu_percent', 'throughput']:
            # Scale up application instances
            current_instances = current_metrics.get('app_instances', 2)
            new_instances = min(8, current_instances + 1)

            return OptimizationAction(
                id=f"scale_app_{int(time.time())}",
                name="Scale Application Instances",
                description=f"Increase application instances from {current_instances} to {new_instances}",
                action_type="scale",
                target_component="application",
                parameters={
                    "instances": new_instances,
                    "cpu_threshold": 80,
                    "memory_threshold": 85
                },
                expected_impact={"cpu_usage": -30.0, "throughput": 50.0},
                rollback_parameters={"instances": current_instances},
                confidence_score=0.85
            )

        return None

    async def _create_cache_optimization(
        self,
        target: OptimizationTarget,
        issue: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> OptimizationAction:
        """Create cache optimization action"""
        current_cache_size = current_metrics.get('cache_size_mb', 100)
        new_cache_size = min(1024, current_cache_size * 2)

        return OptimizationAction(
            id=f"cache_optimize_{int(time.time())}",
            name="Optimize Cache Configuration",
            description=f"Increase cache size from {current_cache_size}MB to {new_cache_size}MB",
            action_type="cache",
            target_component="cache",
            parameters={
                "max_memory": f"{new_cache_size}mb",
                "ttl": 3600,
                "eviction_policy": "allkeys-lru"
            },
            expected_impact={"cache_hit_ratio": 15.0, "response_time": -20.0},
            rollback_parameters={
                "max_memory": f"{current_cache_size}mb",
                "ttl": 3600,
                "eviction_policy": "allkeys-lru"
            },
            confidence_score=0.75
        )

    async def _create_index_optimization(
        self,
        target: OptimizationTarget,
        issue: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> OptimizationAction:
        """Create index optimization action"""
        return OptimizationAction(
            id=f"index_optimize_{int(time.time())}",
            name="Optimize Database Indexes",
            description="Create missing indexes to improve query performance",
            action_type="index",
            target_component="database",
            parameters={
                "indexes_to_create": [
                    "CREATE INDEX CONCURRENTLY idx_documents_created_at ON documents (created_at DESC)",
                    "CREATE INDEX CONCURRENTLY idx_search_results_query_score ON search_results (query_id, score)"
                ]
            },
            expected_impact={"response_time": -25.0, "query_time": -40.0},
            rollback_parameters={
                "indexes_to_drop": ["idx_documents_created_at", "idx_search_results_query_score"]
            },
            confidence_score=0.9
        )

    async def _create_cleanup_optimization(
        self,
        target: OptimizationTarget,
        issue: Dict[str, Any],
        current_metrics: Dict[str, Any]
    ) -> OptimizationAction:
        """Create cleanup optimization action"""
        return OptimizationAction(
            id=f"cleanup_optimize_{int(time.time())}",
            name="Cleanup System Resources",
            description="Clean up old logs, temporary files, and unused resources",
            action_type="cleanup",
            target_component="system",
            parameters={
                "cleanup_logs_older_than": 7,  # days
                "cleanup_temp_files": True,
                "cleanup_cache_entries": True,
                "vaccum_database": True
            },
            expected_impact={"disk_usage": -10.0, "memory_usage": -5.0},
            rollback_parameters={},
            confidence_score=0.8
        )

    async def _apply_optimizations(self, recommendations: List[OptimizationAction]):
        """Apply optimization recommendations"""
        max_concurrent = self.system_config['optimization']['max_concurrent_optimizations']
        confidence_threshold = self.system_config['optimization']['confidence_threshold']

        # Filter by confidence threshold
        high_confidence_recs = [
            rec for rec in recommendations
            if rec.confidence_score >= confidence_threshold
        ]

        # Apply up to max_concurrent optimizations
        for rec in high_confidence_recs[:max_concurrent]:
            if rec.id not in self.active_optimizations:
                try:
                    await self._execute_optimization(rec)
                except Exception as e:
                    logger.error(f"Error executing optimization {rec.id}: {e}")

    async def _execute_optimization(self, action: OptimizationAction):
        """Execute a single optimization action"""
        logger.info(f"Executing optimization: {action.name}")
        self.active_optimizations[action.id] = action

        start_time = time.time()

        try:
            success = await self._apply_action(action)

            action.execution_time = time.time() - start_time
            action.success = success

            if success:
                # Schedule rollback check
                asyncio.create_task(self._monitor_optimization_result(action))
                logger.info(f"Optimization {action.id} executed successfully")
            else:
                logger.error(f"Optimization {action.id} failed")
                del self.active_optimizations[action.id]

            self.optimization_history.append(action)

        except Exception as e:
            action.execution_time = time.time() - start_time
            action.success = False
            action.error_message = str(e)
            logger.error(f"Error executing optimization {action.id}: {e}")
            del self.active_optimizations[action.id]
            self.optimization_history.append(action)

    async def _apply_action(self, action: OptimizationAction) -> bool:
        """Apply the specific optimization action"""
        if action.action_type == "config":
            return await self._apply_config_change(action)
        elif action.action_type == "scale":
            return await self._apply_scaling(action)
        elif action.action_type == "cache":
            return await self._apply_cache_change(action)
        elif action.action_type == "index":
            return await self._apply_index_change(action)
        elif action.action_type == "cleanup":
            return await self._apply_cleanup(action)

        return False

    async def _apply_config_change(self, action: OptimizationAction) -> bool:
        """Apply configuration changes"""
        try:
            if action.target_component == "database":
                # Update PostgreSQL configuration
                config_file = self.system_config['components']['database']['config_file']

                # This would update the actual PostgreSQL configuration file
                # For now, simulate the change
                logger.info(f"Would update {config_file} with: {action.parameters}")

                # In a real implementation:
                # 1. Read current config
                # 2. Update parameters
                # 3. Write new config
                # 4. Restart database if needed

                return True

            elif action.target_component == "application":
                # Update application configuration
                config_file = self.system_config['components']['application']['config_file']

                logger.info(f"Would update {config_file} with: {action.parameters}")

                # This would update your application configuration
                return True

        except Exception as e:
            logger.error(f"Error applying config change: {e}")
            return False

        return False

    async def _apply_scaling(self, action: OptimizationAction) -> bool:
        """Apply scaling changes"""
        try:
            if action.target_component == "application":
                # Scale application using container orchestration
                instances = action.parameters.get("instances", 2)

                logger.info(f"Would scale application to {instances} instances")

                # In a real implementation with Kubernetes:
                # kubectl scale deployment rag-app --replicas={instances}

                # Or with Docker Swarm:
                # docker service scale rag-app={instances}

                return True

        except Exception as e:
            logger.error(f"Error applying scaling: {e}")
            return False

        return False

    async def _apply_cache_change(self, action: OptimizationAction) -> bool:
        """Apply cache configuration changes"""
        try:
            if self.redis_client:
                # Update Redis configuration
                max_memory = action.parameters.get("max_memory", "256mb")

                await self.redis_client.config_set("maxmemory", max_memory)
                await self.redis_client.config_set("maxmemory-policy", action.parameters.get("eviction_policy", "allkeys-lru"))

                logger.info(f"Updated Redis maxmemory to {max_memory}")
                return True

        except Exception as e:
            logger.error(f"Error applying cache change: {e}")
            return False

        return False

    async def _apply_index_change(self, action: OptimizationAction) -> bool:
        """Apply database index changes"""
        try:
            # Connect to database and create indexes
            # This is a placeholder for actual database operations

            indexes = action.parameters.get("indexes_to_create", [])
            for index_sql in indexes:
                logger.info(f"Would create index: {index_sql}")
                # In a real implementation:
                # await connection.execute(index_sql)

            return True

        except Exception as e:
            logger.error(f"Error applying index change: {e}")
            return False

    async def _apply_cleanup(self, action: OptimizationAction) -> bool:
        """Apply cleanup operations"""
        try:
            # Clean up old logs
            cleanup_logs_older_than = action.parameters.get("cleanup_logs_older_than", 7)
            logger.info(f"Would clean up logs older than {cleanup_logs_older_than} days")

            # Clean temporary files
            if action.parameters.get("cleanup_temp_files", False):
                logger.info("Would clean up temporary files")

            # Clean cache entries
            if action.parameters.get("cleanup_cache_entries", False) and self.redis_client:
                # Clean old cache entries
                logger.info("Would clean up old cache entries")

            # Vaccum database
            if action.parameters.get("vaccum_database", False):
                logger.info("Would run database VACUUM")

            return True

        except Exception as e:
            logger.error(f"Error applying cleanup: {e}")
            return False

    async def _monitor_optimization_result(self, action: OptimizationAction):
        """Monitor the result of an optimization and rollback if needed"""
        rollback_timeout = self.system_config['optimization']['rollback_timeout']

        # Wait for the optimization to take effect
        await asyncio.sleep(60)

        # Check if optimization improved performance
        current_metrics = await self._collect_current_metrics()
        if not current_metrics:
            return

        # Evaluate the optimization impact
        improvement = await self._evaluate_optimization_impact(action, current_metrics)

        if improvement < 0:  # Performance degraded
            logger.warning(f"Optimization {action.id} degraded performance, initiating rollback")
            await self._rollback_optimization(action)

        # Remove from active optimizations
        if action.id in self.active_optimizations:
            del self.active_optimizations[action.id]

    async def _evaluate_optimization_impact(
        self,
        action: OptimizationAction,
        current_metrics: Dict[str, Any]
    ) -> float:
        """Evaluate the impact of an optimization"""
        # Calculate improvement based on expected impact
        total_expected_impact = 0
        total_actual_impact = 0

        for metric, expected_change in action.expected_impact.items():
            current_value = current_metrics.get(metric)
            if current_value is not None:
                # For simplicity, assume baseline value and calculate improvement
                # In a real implementation, you'd compare with pre-optimization metrics
                baseline_value = current_value * (1 + (expected_change / 100))
                actual_change = ((baseline_value - current_value) / baseline_value) * 100

                total_expected_impact += abs(expected_change)
                total_actual_impact += actual_change

        if total_expected_impact > 0:
            return (total_actual_impact / total_expected_impact) * 100
        return 0

    async def _rollback_optimization(self, action: OptimizationAction):
        """Rollback an optimization action"""
        if not action.rollback_parameters:
            logger.warning(f"No rollback parameters available for {action.id}")
            return

        logger.info(f"Rolling back optimization: {action.name}")

        try:
            # Create rollback action
            rollback_action = OptimizationAction(
                id=f"rollback_{action.id}",
                name=f"Rollback: {action.name}",
                description=f"Rollback optimization: {action.description}",
                action_type=action.action_type,
                target_component=action.target_component,
                parameters=action.rollback_parameters,
                expected_impact={},
                rollback_parameters=None,
                confidence_score=1.0
            )

            success = await self._apply_action(rollback_action)

            if success:
                logger.info(f"Successfully rolled back optimization {action.id}")
            else:
                logger.error(f"Failed to rollback optimization {action.id}")

        except Exception as e:
            logger.error(f"Error during rollback of {action.id}: {e}")

    async def _detect_performance_patterns(self, data: List[Dict[str, Any]]) -> List[PerformancePattern]:
        """Detect performance patterns in historical data"""
        patterns = []

        try:
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

            # Detect seasonal patterns (daily/weekly)
            for metric in ['cpu_percent', 'memory_percent', 'avg_response_time']:
                if metric in df.columns:
                    # Daily pattern
                    daily_pattern = self._detect_seasonal_pattern(df[metric], 'daily')
                    if daily_pattern:
                        patterns.append(daily_pattern)

                    # Weekly pattern
                    weekly_pattern = self._detect_seasonal_pattern(df[metric], 'weekly')
                    if weekly_pattern:
                        patterns.append(weekly_pattern)

            # Detect trends
            for metric in ['cpu_percent', 'memory_percent', 'throughput']:
                if metric in df.columns:
                    trend = self._detect_trend(df[metric])
                    if trend:
                        patterns.append(trend)

            # Detect correlations
            correlations = self._detect_correlations(df)
            patterns.extend(correlations)

        except Exception as e:
            logger.error(f"Error detecting performance patterns: {e}")

        return patterns

    def _detect_seasonal_pattern(self, series: pd.Series, period: str) -> Optional[PerformancePattern]:
        """Detect seasonal patterns in time series"""
        try:
            if len(series) < 24:  # Need at least 24 data points
                return None

            # Simple seasonality detection using autocorrelation
            if period == 'daily':
                lag = 24  # Assuming hourly data
            elif period == 'weekly':
                lag = 24 * 7  # Weekly pattern
            else:
                return None

            autocorr = series.autocorr(lag=lag)

            if abs(autocorr) > 0.3:  # Significant correlation
                return PerformancePattern(
                    pattern_id=f"{period}_{series.name}_{int(time.time())}",
                    pattern_type="seasonal",
                    description=f"Strong {period} seasonality detected in {series.name}",
                    confidence=abs(autocorr),
                    metrics=[series.name],
                    time_range=(series.index.min(), series.index.max()),
                    parameters={"period": period, "autocorrelation": autocorr},
                    recommendations=[f"Consider {period}-based resource scaling for {series.name}"]
                )

        except Exception as e:
            logger.error(f"Error detecting seasonal pattern: {e}")

        return None

    def _detect_trend(self, series: pd.Series) -> Optional[PerformancePattern]:
        """Detect trends in time series"""
        try:
            if len(series) < 10:
                return None

            # Simple linear trend detection
            x = np.arange(len(series))
            slope, intercept = np.polyfit(x, series, 1)

            # Calculate R-squared
            y_pred = slope * x + intercept
            ss_res = np.sum((series - y_pred) ** 2)
            ss_tot = np.sum((series - np.mean(series)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)

            if abs(slope) > 0.1 and r_squared > 0.3:  # Significant trend
                trend_direction = "increasing" if slope > 0 else "decreasing"

                return PerformancePattern(
                    pattern_id=f"trend_{series.name}_{int(time.time())}",
                    pattern_type="trend",
                    description=f"{trend_direction.capitalize()} trend detected in {series.name}",
                    confidence=abs(r_squared),
                    metrics=[series.name],
                    time_range=(series.index.min(), series.index.max()),
                    parameters={"slope": slope, "r_squared": r_squared, "direction": trend_direction},
                    recommendations=[f"Monitor {series.name} trend and plan capacity accordingly"]
                )

        except Exception as e:
            logger.error(f"Error detecting trend: {e}")

        return None

    def _detect_correlations(self, df: pd.DataFrame) -> List[PerformancePattern]:
        """Detect correlations between metrics"""
        patterns = []

        try:
            numeric_columns = df.select_dtypes(include=[np.number]).columns

            if len(numeric_columns) < 2:
                return patterns

            correlation_matrix = df[numeric_columns].corr()

            # Find strong correlations
            for i in range(len(correlation_matrix.columns)):
                for j in range(i + 1, len(correlation_matrix.columns)):
                    corr_value = correlation_matrix.iloc[i, j]

                    if abs(corr_value) > 0.7:  # Strong correlation
                        metric1 = correlation_matrix.columns[i]
                        metric2 = correlation_matrix.columns[j]

                        patterns.append(PerformancePattern(
                            pattern_id=f"correlation_{metric1}_{metric2}_{int(time.time())}",
                            pattern_type="correlation",
                            description=f"Strong correlation ({corr_value:.3f}) between {metric1} and {metric2}",
                            confidence=abs(corr_value),
                            metrics=[metric1, metric2],
                            time_range=(df.index.min(), df.index.max()),
                            parameters={"correlation": corr_value, "metric1": metric1, "metric2": metric2},
                            recommendations=[f"Consider joint optimization of {metric1} and {metric2}"]
                        ))

        except Exception as e:
            logger.error(f"Error detecting correlations: {e}")

        return patterns

    # Public API methods
    async def get_optimization_recommendations(self) -> List[OptimizationAction]:
        """Get current optimization recommendations"""
        current_metrics = await self._collect_current_metrics()
        if not current_metrics:
            return []

        predictions = await self.ml_predictor.predict_performance(current_metrics)
        issues = await self._detect_performance_issues(current_metrics, predictions)
        recommendations = await self._generate_optimization_recommendations(current_metrics, predictions, issues)

        return recommendations

    async def get_performance_patterns(self) -> List[PerformancePattern]:
        """Get detected performance patterns"""
        return self.performance_patterns

    async def get_optimization_history(self, limit: int = 50) -> List[OptimizationAction]:
        """Get optimization history"""
        return self.optimization_history[-limit:]

    async def apply_manual_optimization(self, action_id: str) -> bool:
        """Manually apply a specific optimization"""
        recommendations = await self.get_optimization_recommendations()
        action = next((r for r in recommendations if r.id == action_id), None)

        if action:
            await self._execute_optimization(action)
            return True

        return False

    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system optimization status"""
        current_metrics = await self._collect_current_metrics()
        predictions = await self.ml_predictor.predict_performance(current_metrics) if current_metrics else {}
        issues = await self._detect_performance_issues(current_metrics, predictions) if current_metrics else []

        return {
            "is_running": self.is_running,
            "active_optimizations": len(self.active_optimizations),
            "total_optimizations": len(self.optimization_history),
            "success_rate": sum(1 for opt in self.optimization_history if opt.success) / max(1, len(self.optimization_history)),
            "current_metrics": current_metrics,
            "predictions": predictions,
            "active_issues": len(issues),
            "detected_patterns": len(self.performance_patterns),
            "ml_models_trained": self.ml_predictor.is_trained,
            "last_model_update": self.ml_predictor.last_model_update
        }

# Global optimizer instance
automated_optimizer = AutomatedOptimizer()

# Startup and shutdown functions
async def initialize_automated_optimization(redis_url: Optional[str] = None, config_file: Optional[str] = None):
    """Initialize automated optimization system"""
    await automated_optimizer.initialize(redis_url, config_file)
    await automated_optimizer.start_optimization()
    logger.info("Automated optimization system initialized")

async def shutdown_automated_optimization():
    """Shutdown automated optimization system"""
    await automated_optimizer.stop_optimization()
    logger.info("Automated optimization system shutdown")