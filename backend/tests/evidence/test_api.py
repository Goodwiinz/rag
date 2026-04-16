"""
Integration tests for Evidence Agreement Meter API endpoints
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.evidence import StanceClassificationModel
from src.models.base import Base  # Use the models/base.py Base, not core/database


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_evidence.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Mock user for testing
class MockUser:
    """Mock user object for testing"""
    def __init__(self):
        self.id = uuid4()
        self.organization_id = uuid4()
        self.is_active = True
        self.email = "test@example.com"
        
    def has_permission(self, role):
        return True
        
    def can_view_analytics(self):
        return True


def override_get_current_user():
    """Override authentication for testing"""
    return MockUser()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture(scope="module")
def test_client():
    """Test client with database override.

    Disables FastAPI lifespan events (which try to connect to real services)
    so tests don't hang in CI when PostgreSQL/Redis/Neo4j are unavailable.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _no_lifespan

    # Only create the specific tables we need for testing (avoid PostgreSQL-specific types)
    StanceClassificationModel.__table__.create(bind=engine, checkfirst=True)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        StanceClassificationModel.__table__.drop(bind=engine, checkfirst=True)
        app.router.lifespan_context = original_lifespan


@pytest.fixture
def mock_auth():
    """Mock authentication dependency (already set at app level)"""
    yield


@pytest.fixture
def sample_source_ids():
    """Sample source UUIDs for testing"""
    return [str(uuid4()) for _ in range(3)]


class TestEvidenceMeterEndpoint:
    """Test /api/v1/evidence/meter endpoint"""
    
    @patch('src.api.evidence.router.stance_classifier')
    @patch('src.api.evidence.router.consensus_calculator')
    @patch('src.api.evidence.router.cache_service')
    def test_get_evidence_meter_success(self, mock_cache, mock_consensus, mock_classifier, test_client, mock_auth, sample_source_ids):
        """Test successful evidence meter generation"""
        # Mock cache miss (async method)
        mock_cache.get_evidence_meter = AsyncMock(return_value=None)
        mock_cache.set_evidence_meter = AsyncMock(return_value=None)
        
        # Mock stance classifications
        mock_classifications = [
            {
                "source_id": sample_source_ids[0],
                "stance": "supporting",
                "confidence": 0.90,
                "justification_excerpt": "Strong supporting evidence"
            },
            {
                "source_id": sample_source_ids[1], 
                "stance": "supporting",
                "confidence": 0.85,
                "justification_excerpt": "Additional support"
            },
            {
                "source_id": sample_source_ids[2],
                "stance": "opposing",
                "confidence": 0.80,
                "justification_excerpt": "Contradictory findings"
            }
        ]
        mock_classifier.classify_sources_batch = AsyncMock(return_value=mock_classifications)
        mock_classifier.model_version = "gpt-4o-mini-2024-07-18"
        
        # Mock consensus calculation
        from src.api.evidence.schemas import EvidenceMeter, ConsensusLevel
        mock_meter = EvidenceMeter(
            claim="Test claim",
            claim_hash="abc123",
            total_sources=3,
            supporting=2,
            opposing=1,
            neutral=0,
            not_addressed=0,
            consensus_level=ConsensusLevel.MODERATE_AGREEMENT,
            average_confidence=0.85,
            retracted_sources=0,
            cached=False,
            reproducibility_hash="test_hash"
        )
        mock_consensus.calculate_consensus.return_value = mock_meter
        mock_consensus._generate_claim_hash.return_value = "abc123"
        
        # Make request
        response = test_client.get(
            "/api/v1/evidence/meter",
            params={
                "claim": "Test claim",
                "source_ids": ",".join(sample_source_ids)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["claim"] == "Test claim"
        assert data["total_sources"] == 3
        assert data["supporting"] == 2
        assert data["opposing"] == 1
        assert data["consensus_level"] == "moderate_agreement"
        assert data["average_confidence"] == 0.85
    
    def test_get_evidence_meter_missing_claim(self, test_client, mock_auth):
        """Test meter endpoint with missing claim parameter"""
        response = test_client.get("/api/v1/evidence/meter")
        
        assert response.status_code == 422  # Validation error
    
    def test_get_evidence_meter_invalid_source_ids(self, test_client, mock_auth):
        """Test meter endpoint with invalid source IDs"""
        response = test_client.get(
            "/api/v1/evidence/meter",
            params={
                "claim": "Test claim",
                "source_ids": "invalid-uuid,another-invalid"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        # Check both possible error response formats
        detail = data.get("detail") or data.get("error", {}).get("message", "")
        assert "Invalid source ID format" in detail
    
    def test_get_evidence_meter_no_sources(self, test_client, mock_auth):
        """Test meter endpoint with no source IDs (MVP requirement)"""
        response = test_client.get(
            "/api/v1/evidence/meter",
            params={"claim": "Test claim"}
        )
        
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail") or data.get("error", {}).get("message", "")
        assert "source_ids parameter required" in detail
    
    @patch('src.api.evidence.router.cache_service')
    def test_get_evidence_meter_cached_result(self, mock_cache, test_client, mock_auth, sample_source_ids):
        """Test meter endpoint returning cached result"""
        # Mock cache hit
        cached_data = {
            "claim": "Test claim",
            "claim_hash": "abc123",
            "total_sources": 3,
            "supporting": 2,
            "opposing": 1,
            "neutral": 0,
            "not_addressed": 0,
            "consensus_level": "moderate_agreement",
            "average_confidence": 0.85,
            "retracted_sources": 0,
            "cached": True,
            "reproducibility_hash": "test_hash"
        }
        mock_cache.get_evidence_meter = AsyncMock(return_value=cached_data)
        
        response = test_client.get(
            "/api/v1/evidence/meter",
            params={
                "claim": "Test claim",
                "source_ids": ",".join(sample_source_ids)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True


class TestEvidenceBreakdownEndpoint:
    """Test /api/v1/evidence/breakdown endpoint"""
    
    def test_get_evidence_breakdown_success(self, test_client, mock_auth):
        """Test successful evidence breakdown retrieval"""
        # Create test stance classifications in database
        db = TestingSessionLocal()
        
        claim_hash = "test_claim_hash_123"
        source_ids = [uuid4() for _ in range(2)]
        
        classifications = [
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[0],
                stance="supporting",
                confidence=0.90,
                justification_excerpt="Strong evidence",
                model_version="gpt-4o-mini-2024-07-18"
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[1],
                stance="opposing", 
                confidence=0.85,
                justification_excerpt="Contradictory evidence",
                model_version="gpt-4o-mini-2024-07-18"
            )
        ]
        
        for classification in classifications:
            db.add(classification)
        db.commit()
        
        try:
            response = test_client.get(
                "/api/v1/evidence/breakdown",
                params={"claim_hash": claim_hash}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["claim_hash"] == claim_hash
            assert len(data["sources"]) == 2
            assert data["sources"][0]["confidence"] >= data["sources"][1]["confidence"]  # Sorted by confidence
            
        finally:
            db.close()
    
    def test_get_evidence_breakdown_with_stance_filter(self, test_client, mock_auth):
        """Test breakdown endpoint with stance filter"""
        # Create test data
        db = TestingSessionLocal()
        
        claim_hash = "test_filter_hash_456"
        source_ids = [uuid4() for _ in range(3)]
        
        classifications = [
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[0],
                stance="supporting",
                confidence=0.90,
                justification_excerpt="Support 1",
                model_version="gpt-4o-mini-2024-07-18"
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[1],
                stance="supporting",
                confidence=0.85,
                justification_excerpt="Support 2", 
                model_version="gpt-4o-mini-2024-07-18"
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[2],
                stance="opposing",
                confidence=0.80,
                justification_excerpt="Opposition",
                model_version="gpt-4o-mini-2024-07-18"
            )
        ]
        
        for classification in classifications:
            db.add(classification)
        db.commit()
        
        try:
            # Filter for supporting stances only
            response = test_client.get(
                "/api/v1/evidence/breakdown",
                params={
                    "claim_hash": claim_hash,
                    "stance_filter": "supporting"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert len(data["sources"]) == 2  # Only supporting sources
            for source in data["sources"]:
                assert source["stance"] == "supporting"
                
        finally:
            db.close()
    
    def test_get_evidence_breakdown_not_found(self, test_client, mock_auth):
        """Test breakdown endpoint with non-existent claim hash"""
        response = test_client.get(
            "/api/v1/evidence/breakdown",
            params={"claim_hash": "nonexistent_hash"}
        )
        
        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail") or data.get("error", {}).get("message", "")
        assert "No classifications found" in detail
    
    def test_get_evidence_breakdown_missing_claim_hash(self, test_client, mock_auth):
        """Test breakdown endpoint with missing claim_hash parameter"""
        response = test_client.get("/api/v1/evidence/breakdown")
        
        assert response.status_code == 422  # Validation error


class TestClassifyEndpoint:
    """Test /api/v1/evidence/classify endpoint"""
    
    @patch('src.api.evidence.router.stance_classifier')
    @patch('src.api.evidence.router.consensus_calculator')
    def test_classify_sources_success(self, mock_consensus, mock_classifier, test_client, mock_auth, sample_source_ids):
        """Test successful source classification"""
        # Mock stance classifications
        mock_classifications = [
            {
                "source_id": sample_source_ids[0],
                "stance": "supporting",
                "confidence": 0.90,
                "justification_excerpt": "Strong evidence"
            },
            {
                "source_id": sample_source_ids[1],
                "stance": "neutral",
                "confidence": 0.75,
                "justification_excerpt": "Neutral statement"
            }
        ]
        mock_classifier.classify_sources_batch = AsyncMock(return_value=mock_classifications)
        mock_classifier.model_version = "gpt-4o-mini-2024-07-18"
        mock_consensus._generate_claim_hash.return_value = "test_hash"
        
        # Convert to UUIDs for request
        uuid_source_ids = [str(uuid4()) for _ in range(2)]
        
        response = test_client.post(
            "/api/v1/evidence/classify",
            params={"claim": "Test claim"},
            json=uuid_source_ids
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["status"] == "completed"
        assert data["claim_hash"] == "test_hash"
        assert data["classifications_created"] == 2
        assert data["total_sources"] == 2


class TestHealthEndpoint:
    """Test /api/v1/evidence/health endpoint"""
    
    @patch('src.api.evidence.router.cache_service')
    @patch('src.api.evidence.router.consensus_calculator')
    @patch('src.api.evidence.router.stance_classifier')
    def test_health_check_healthy(self, mock_classifier, mock_consensus, mock_cache, test_client):
        """Test healthy service status"""
        # Mock healthy components
        mock_cache._ensure_connected = Mock(return_value=True)
        mock_consensus._generate_claim_hash.return_value = "test_hash"
        mock_classifier.model_version = "gpt-4o-mini-2024-07-18"
        
        response = test_client.get("/api/v1/evidence/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["cache_connected"] is True
        assert data["model_version"] == "gpt-4o-mini-2024-07-18"
        assert all(component == "operational" or component == "degraded" 
                  for component in data["components"].values())
    
    @patch('src.api.evidence.router.cache_service')
    def test_health_check_cache_disconnected(self, mock_cache, test_client):
        """Test service status with cache disconnected"""
        mock_cache._ensure_connected = Mock(return_value=False)
        
        response = test_client.get("/api/v1/evidence/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["cache_connected"] is False
        assert data["components"]["cache_service"] == "degraded"