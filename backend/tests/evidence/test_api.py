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
from src.core.database import get_db_sync
from src.core.dependencies import get_current_user
from src.models.evidence import StanceClassificationModel
from src.api.evidence.router import stance_classifier
from src.models.base import Base  # Use the models/base.py Base, not core/database

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_evidence.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Stable org identities so tests can seed rows and assert cross-tenant isolation.
# (A fresh uuid4() per request would make the scoped /breakdown filter never match.)
TEST_ORG_ID = uuid4()
TEST_ORG_ID_B = uuid4()
TEST_USER_ID = uuid4()
TEST_USER_ID_B = uuid4()


# Mock user for testing
class MockUser:
    """Mock user object for testing"""

    def __init__(self, organization_id=TEST_ORG_ID, user_id=TEST_USER_ID):
        self.id = user_id
        self.organization_id = organization_id
        self.is_active = True
        self.email = "test@example.com"

    def has_permission(self, role):
        return True

    def can_view_analytics(self):
        return True


# The authenticated user, fixed for the default test org. Tests that need the
# second tenant swap this override (see test_breakdown_isolated_by_organization).
_active_user = MockUser()


def override_get_current_user():
    """Override authentication for testing"""
    return _active_user


def set_active_user(user: MockUser) -> None:
    """Swap the authenticated user mid-test (for cross-tenant assertions)."""
    global _active_user
    _active_user = user


app.dependency_overrides[get_db_sync] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture(scope="module")
def test_client():
    """Test client with database override"""
    # Only create the specific tables we need for testing (avoid PostgreSQL-specific types)
    StanceClassificationModel.__table__.create(bind=engine, checkfirst=True)
    with TestClient(app) as client:
        yield client
    StanceClassificationModel.__table__.drop(bind=engine, checkfirst=True)


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

    @patch("src.api.evidence.router.stance_classifier")
    @patch("src.api.evidence.router.consensus_calculator")
    @patch("src.api.evidence.router.cache_service")
    def test_get_evidence_meter_success(
        self,
        mock_cache,
        mock_consensus,
        mock_classifier,
        test_client,
        mock_auth,
        sample_source_ids,
    ):
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
                "justification_excerpt": "Strong supporting evidence",
            },
            {
                "source_id": sample_source_ids[1],
                "stance": "supporting",
                "confidence": 0.85,
                "justification_excerpt": "Additional support",
            },
            {
                "source_id": sample_source_ids[2],
                "stance": "opposing",
                "confidence": 0.80,
                "justification_excerpt": "Contradictory findings",
            },
        ]
        mock_classifier.classify_sources_batch = AsyncMock(
            return_value=mock_classifications
        )
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
            reproducibility_hash="test_hash",
        )
        mock_consensus.calculate_consensus.return_value = mock_meter
        mock_consensus._generate_claim_hash.return_value = "abc123"

        # Make request
        response = test_client.get(
            "/api/v1/evidence/meter",
            params={"claim": "Test claim", "source_ids": ",".join(sample_source_ids)},
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
                "source_ids": "invalid-uuid,another-invalid",
            },
        )

        assert response.status_code == 400
        data = response.json()
        # Check both possible error response formats
        detail = data.get("detail") or data.get("error", {}).get("message", "")
        assert "Invalid source ID format" in detail

    def test_get_evidence_meter_no_sources(self, test_client, mock_auth):
        """Test meter endpoint with no source IDs (MVP requirement)"""
        response = test_client.get(
            "/api/v1/evidence/meter", params={"claim": "Test claim"}
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail") or data.get("error", {}).get("message", "")
        assert "source_ids parameter required" in detail

    @patch("src.api.evidence.router.cache_service")
    def test_get_evidence_meter_cached_result(
        self, mock_cache, test_client, mock_auth, sample_source_ids
    ):
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
            "reproducibility_hash": "test_hash",
        }
        mock_cache.get_evidence_meter = AsyncMock(return_value=cached_data)

        response = test_client.get(
            "/api/v1/evidence/meter",
            params={"claim": "Test claim", "source_ids": ",".join(sample_source_ids)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True


class TestEvidenceBreakdownEndpoint:
    """Test /api/v1/evidence/breakdown endpoint"""

    def test_get_evidence_breakdown_success(self, test_client, mock_auth):
        """Test successful evidence breakdown retrieval"""
        set_active_user(MockUser())  # default org
        # Create test stance classifications in database
        db = TestingSessionLocal()

        claim_hash = "test_claim_hash_123"
        source_ids = [uuid4() for _ in range(2)]

        classifications = [
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[0],
                organization_id=TEST_ORG_ID,
                stance="supporting",
                confidence=0.90,
                justification_excerpt="Strong evidence",
                model_version="gpt-4o-mini-2024-07-18",
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[1],
                organization_id=TEST_ORG_ID,
                stance="opposing",
                confidence=0.85,
                justification_excerpt="Contradictory evidence",
                model_version="gpt-4o-mini-2024-07-18",
            ),
        ]

        for classification in classifications:
            db.add(classification)
        db.commit()

        try:
            response = test_client.get(
                "/api/v1/evidence/breakdown", params={"claim_hash": claim_hash}
            )

            assert response.status_code == 200
            data = response.json()

            assert data["claim_hash"] == claim_hash
            assert len(data["sources"]) == 2
            assert (
                data["sources"][0]["confidence"] >= data["sources"][1]["confidence"]
            )  # Sorted by confidence

        finally:
            db.close()

    def test_get_evidence_breakdown_with_stance_filter(self, test_client, mock_auth):
        """Test breakdown endpoint with stance filter"""
        set_active_user(MockUser())  # default org
        # Create test data
        db = TestingSessionLocal()

        claim_hash = "test_filter_hash_456"
        source_ids = [uuid4() for _ in range(3)]

        classifications = [
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[0],
                organization_id=TEST_ORG_ID,
                stance="supporting",
                confidence=0.90,
                justification_excerpt="Support 1",
                model_version="gpt-4o-mini-2024-07-18",
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[1],
                organization_id=TEST_ORG_ID,
                stance="supporting",
                confidence=0.85,
                justification_excerpt="Support 2",
                model_version="gpt-4o-mini-2024-07-18",
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=source_ids[2],
                organization_id=TEST_ORG_ID,
                stance="opposing",
                confidence=0.80,
                justification_excerpt="Opposition",
                model_version="gpt-4o-mini-2024-07-18",
            ),
        ]

        for classification in classifications:
            db.add(classification)
        db.commit()

        try:
            # Filter for supporting stances only
            response = test_client.get(
                "/api/v1/evidence/breakdown",
                params={"claim_hash": claim_hash, "stance_filter": "supporting"},
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
        set_active_user(MockUser())  # default org
        response = test_client.get(
            "/api/v1/evidence/breakdown", params={"claim_hash": "nonexistent_hash"}
        )

        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail") or data.get("error", {}).get("message", "")
        assert "No classifications found" in detail

    def test_breakdown_isolated_by_organization(self, test_client, mock_auth):
        """REGRESSION: /breakdown must only return the caller's org classifications.

        Before the fix, /breakdown was scoped only by claim_hash + model_version
        (a deterministic SHA-256 of public claim text), so an attacker could read
        another org's source_id + justification_excerpt by computing the hash.
        This test fails before the fix (both orgs' rows returned) and passes after.
        """
        db = TestingSessionLocal()
        claim_hash = "shared_claim_hash_tenant_regression"
        model_version = stance_classifier.model_version

        org_a_source = uuid4()
        org_b_source = uuid4()
        org_a_excerpt = "ORG_A_SECRET_EXCERPT_DO_NOT_LEAK"
        org_b_excerpt = "ORG_B_SECRET_EXCERPT_DO_NOT_LEAK"

        rows = [
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=org_a_source,
                organization_id=TEST_ORG_ID,
                stance="supporting",
                confidence=0.9,
                justification_excerpt=org_a_excerpt,
                model_version=model_version,
            ),
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=org_b_source,
                organization_id=TEST_ORG_ID_B,
                stance="opposing",
                confidence=0.8,
                justification_excerpt=org_b_excerpt,
                model_version=model_version,
            ),
        ]
        for row in rows:
            db.add(row)
        db.commit()
        db.close()

        try:
            # --- As Org A: must see ONLY Org A's row ---
            set_active_user(MockUser(organization_id=TEST_ORG_ID))
            resp_a = test_client.get(
                "/api/v1/evidence/breakdown", params={"claim_hash": claim_hash}
            )
            assert resp_a.status_code == 200, resp_a.text
            sources_a = resp_a.json()["sources"]
            assert len(sources_a) == 1, f"expected 1 source for org A, got {sources_a}"
            assert sources_a[0]["source_id"] == str(org_a_source)
            assert sources_a[0]["justification_excerpt"] == org_a_excerpt
            # Org A must never see Org B's content
            assert all(s["source_id"] != str(org_b_source) for s in sources_a)
            assert org_b_excerpt not in resp_a.text

            # --- As Org B: must see ONLY Org B's row ---
            set_active_user(MockUser(organization_id=TEST_ORG_ID_B))
            resp_b = test_client.get(
                "/api/v1/evidence/breakdown", params={"claim_hash": claim_hash}
            )
            assert resp_b.status_code == 200, resp_b.text
            sources_b = resp_b.json()["sources"]
            assert len(sources_b) == 1, f"expected 1 source for org B, got {sources_b}"
            assert sources_b[0]["source_id"] == str(org_b_source)
            assert sources_b[0]["justification_excerpt"] == org_b_excerpt
            assert all(s["source_id"] != str(org_a_source) for s in sources_b)
            assert org_a_excerpt not in resp_b.text

        finally:
            set_active_user(MockUser())  # reset to default org for any later tests

    def test_breakdown_rejects_null_org_user(self, test_client, mock_auth):
        """A user without an org must never see any classifications.

        SQLAlchemy compiles ``Column == None`` to ``IS NULL`` — without an explicit
        guard a NULL-org user would match every NULL-org row (a shared bucket across all
        such users). The endpoint must fail closed instead. Seeds a NULL-org row to prove
        it is not returned even to the NULL-org user themselves.
        """
        db = TestingSessionLocal()
        claim_hash = "null_org_claim_hash_regression"
        model_version = stance_classifier.model_version
        secret_excerpt = "NULL_ORG_BUCKET_SHOULD_NOT_LEAK"

        db.add(
            StanceClassificationModel(
                claim_hash=claim_hash,
                source_id=uuid4(),
                organization_id=None,
                stance="supporting",
                confidence=0.9,
                justification_excerpt=secret_excerpt,
                model_version=model_version,
            )
        )
        db.commit()
        db.close()

        try:
            set_active_user(MockUser(organization_id=None))
            resp = test_client.get(
                "/api/v1/evidence/breakdown", params={"claim_hash": claim_hash}
            )
            assert resp.status_code == 404
            assert secret_excerpt not in resp.text
        finally:
            set_active_user(MockUser())  # reset to default org

    def test_get_evidence_breakdown_missing_claim_hash(self, test_client, mock_auth):
        """Test breakdown endpoint with missing claim_hash parameter"""
        response = test_client.get("/api/v1/evidence/breakdown")

        assert response.status_code == 422  # Validation error


class TestClassifyEndpoint:
    """Test /api/v1/evidence/classify endpoint"""

    @patch("src.api.evidence.router.stance_classifier")
    @patch("src.api.evidence.router.consensus_calculator")
    def test_classify_sources_success(
        self, mock_consensus, mock_classifier, test_client, mock_auth, sample_source_ids
    ):
        """Test successful source classification"""
        # Mock stance classifications
        mock_classifications = [
            {
                "source_id": sample_source_ids[0],
                "stance": "supporting",
                "confidence": 0.90,
                "justification_excerpt": "Strong evidence",
            },
            {
                "source_id": sample_source_ids[1],
                "stance": "neutral",
                "confidence": 0.75,
                "justification_excerpt": "Neutral statement",
            },
        ]
        mock_classifier.classify_sources_batch = AsyncMock(
            return_value=mock_classifications
        )
        mock_classifier.model_version = "gpt-4o-mini-2024-07-18"
        mock_consensus._generate_claim_hash.return_value = "test_hash"

        # Convert to UUIDs for request
        uuid_source_ids = [str(uuid4()) for _ in range(2)]

        response = test_client.post(
            "/api/v1/evidence/classify",
            params={"claim": "Test claim"},
            json=uuid_source_ids,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["status"] == "completed"
        assert data["claim_hash"] == "test_hash"
        assert data["classifications_created"] == 2
        assert data["total_sources"] == 2


class TestHealthEndpoint:
    """Test /api/v1/evidence/health endpoint"""

    @patch("src.api.evidence.router.cache_service")
    @patch("src.api.evidence.router.consensus_calculator")
    @patch("src.api.evidence.router.stance_classifier")
    def test_health_check_healthy(
        self, mock_classifier, mock_consensus, mock_cache, test_client
    ):
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
        assert all(
            component == "operational" or component == "degraded"
            for component in data["components"].values()
        )

    @patch("src.api.evidence.router.cache_service")
    def test_health_check_cache_disconnected(self, mock_cache, test_client):
        """Test service status with cache disconnected"""
        mock_cache._ensure_connected = Mock(return_value=False)

        response = test_client.get("/api/v1/evidence/health")

        assert response.status_code == 200
        data = response.json()

        assert data["cache_connected"] is False
        assert data["components"]["cache_service"] == "degraded"
