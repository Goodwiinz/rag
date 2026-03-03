"""
Unit tests for ConsensusCalculator service
"""

import pytest
from uuid import uuid4

from src.services.evidence.consensus_calculator import ConsensusCalculator
from src.api.evidence.schemas import ConsensusLevel


@pytest.fixture
def consensus_calculator():
    """ConsensusCalculator instance"""
    return ConsensusCalculator()


@pytest.fixture
def sample_claim():
    """Sample claim for testing"""
    return "Machine learning improves medical diagnosis"


@pytest.fixture
def sample_classifications_strong_agreement():
    """Sample classifications with strong agreement"""
    return [
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.90,
            "justification_excerpt": "ML algorithms showed 95% accuracy"
        },
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.85,
            "justification_excerpt": "Significant improvement in diagnostic speed"
        },
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.88,
            "justification_excerpt": "Reduced false negative rates"
        },
        {
            "source_id": str(uuid4()),
            "stance": "opposing",
            "confidence": 0.75,
            "justification_excerpt": "No significant improvement found"
        },
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.80,
            "justification_excerpt": "Study confirmed positive outcomes"
        }
    ]


@pytest.fixture
def sample_classifications_mixed():
    """Sample classifications with mixed results"""
    return [
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.85
        },
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.80
        },
        {
            "source_id": str(uuid4()),
            "stance": "opposing",
            "confidence": 0.88
        },
        {
            "source_id": str(uuid4()),
            "stance": "opposing",
            "confidence": 0.92
        },
        {
            "source_id": str(uuid4()),
            "stance": "neutral",
            "confidence": 0.75
        }
    ]


@pytest.fixture
def sample_classifications_insufficient():
    """Sample classifications with insufficient data"""
    return [
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.85
        },
        {
            "source_id": str(uuid4()),
            "stance": "neutral",
            "confidence": 0.70
        }
    ]


@pytest.fixture
def sample_classifications_not_addressed():
    """Sample classifications where most sources don't address claim"""
    return [
        {
            "source_id": str(uuid4()),
            "stance": "not_addressed",
            "confidence": 0.90
        },
        {
            "source_id": str(uuid4()),
            "stance": "not_addressed",
            "confidence": 0.85
        },
        {
            "source_id": str(uuid4()),
            "stance": "not_addressed",
            "confidence": 0.88
        },
        {
            "source_id": str(uuid4()),
            "stance": "supporting",
            "confidence": 0.75
        }
    ]


class TestConsensusCalculator:
    """Test ConsensusCalculator service"""

    def test_normalize_claim(self, consensus_calculator):
        """Test claim normalization"""
        claim1 = "  Machine Learning  improves    diagnosis  "
        claim2 = "machine learning improves diagnosis"
        claim3 = "MACHINE LEARNING IMPROVES DIAGNOSIS"

        normalized1 = consensus_calculator._normalize_claim(claim1)
        normalized2 = consensus_calculator._normalize_claim(claim2)
        normalized3 = consensus_calculator._normalize_claim(claim3)

        assert normalized1 == normalized2 == normalized3
        assert normalized1 == "machine learning improves diagnosis"

    def test_generate_claim_hash(self, consensus_calculator):
        """Test claim hash generation"""
        claim1 = "Machine learning improves diagnosis"
        claim2 = "machine learning improves diagnosis"  # Same normalized
        claim3 = "Deep learning improves diagnosis"      # Different

        hash1 = consensus_calculator._generate_claim_hash(claim1)
        hash2 = consensus_calculator._generate_claim_hash(claim2)
        hash3 = consensus_calculator._generate_claim_hash(claim3)

        assert hash1 == hash2  # Same after normalization
        assert hash1 != hash3  # Different claims
        assert len(hash1) == 64  # SHA256 hex length

    def test_determine_consensus_level_insufficient_data(self, consensus_calculator):
        """Test consensus level with insufficient data"""
        # Less than 3 sources
        level = consensus_calculator._determine_consensus_level(2, 1, 1, 0, 0)
        assert level == ConsensusLevel.INSUFFICIENT_DATA

        # No relevant sources (all neutral/not_addressed)
        level = consensus_calculator._determine_consensus_level(5, 0, 0, 3, 2)
        assert level == ConsensusLevel.INSUFFICIENT_DATA

        # Majority not addressed
        level = consensus_calculator._determine_consensus_level(5, 1, 1, 0, 3)
        assert level == ConsensusLevel.INSUFFICIENT_DATA

    def test_determine_consensus_level_strong_agreement(self, consensus_calculator):
        """Test strong agreement consensus level"""
        # 80% agreement (4 supporting, 1 opposing)
        level = consensus_calculator._determine_consensus_level(6, 4, 1, 1, 0)
        assert level == ConsensusLevel.STRONG_AGREEMENT

        # 100% agreement
        level = consensus_calculator._determine_consensus_level(5, 4, 0, 1, 0)
        assert level == ConsensusLevel.STRONG_AGREEMENT

    def test_determine_consensus_level_moderate_agreement(self, consensus_calculator):
        """Test moderate agreement consensus level"""
        # 70% agreement (7 supporting, 3 opposing)
        level = consensus_calculator._determine_consensus_level(10, 7, 3, 0, 0)
        assert level == ConsensusLevel.MODERATE_AGREEMENT

        # 60% agreement
        level = consensus_calculator._determine_consensus_level(8, 3, 2, 3, 0)
        assert level == ConsensusLevel.MODERATE_AGREEMENT

    def test_determine_consensus_level_mixed(self, consensus_calculator):
        """Test mixed consensus level"""
        # 50% agreement
        level = consensus_calculator._determine_consensus_level(6, 2, 2, 2, 0)
        assert level == ConsensusLevel.MIXED

        # 45% agreement
        level = consensus_calculator._determine_consensus_level(10, 4, 5, 1, 0)
        assert level == ConsensusLevel.MIXED

    def test_determine_consensus_level_low_agreement(self, consensus_calculator):
        """Test low agreement consensus level"""
        # 25% agreement (1 supporting, 3 opposing)
        level = consensus_calculator._determine_consensus_level(6, 1, 3, 2, 0)
        assert level == ConsensusLevel.LOW_AGREEMENT

        # 10% agreement
        level = consensus_calculator._determine_consensus_level(12, 1, 9, 2, 0)
        assert level == ConsensusLevel.LOW_AGREEMENT

    def test_generate_reproducibility_hash(self, consensus_calculator):
        """Test reproducibility hash generation"""
        claim_hash = "abc123456789"
        source_ids = ["id1", "id3", "id2"]  # Unsorted
        model_version = "gpt-4o-mini-2024-07-18"

        hash1 = consensus_calculator._generate_reproducibility_hash(claim_hash, source_ids, model_version)

        # Test with same data in different order
        source_ids_shuffled = ["id2", "id1", "id3"]
        hash2 = consensus_calculator._generate_reproducibility_hash(claim_hash, source_ids_shuffled, model_version)

        assert hash1 == hash2  # Should be same regardless of order
        assert "meter_v1" in hash1
        assert "3src" in hash1  # Source count
        assert "gpt" in hash1   # Model prefix

    def test_calculate_consensus_strong_agreement(self, consensus_calculator, sample_claim, sample_classifications_strong_agreement):
        """Test consensus calculation with strong agreement"""
        meter = consensus_calculator.calculate_consensus(
            sample_claim, sample_classifications_strong_agreement
        )

        assert meter.claim == sample_claim
        assert meter.total_sources == 5
        assert meter.supporting == 4
        assert meter.opposing == 1
        assert meter.neutral == 0
        assert meter.not_addressed == 0
        assert meter.consensus_level == ConsensusLevel.STRONG_AGREEMENT
        assert 0.80 <= meter.average_confidence <= 0.90
        assert meter.retracted_sources == 0
        assert not meter.cached  # Set by calculate_consensus

    def test_calculate_consensus_mixed(self, consensus_calculator, sample_claim, sample_classifications_mixed):
        """Test consensus calculation with mixed results"""
        meter = consensus_calculator.calculate_consensus(
            sample_claim, sample_classifications_mixed
        )

        assert meter.supporting == 2
        assert meter.opposing == 2
        assert meter.neutral == 1
        assert meter.consensus_level == ConsensusLevel.MIXED

    def test_calculate_consensus_insufficient(self, consensus_calculator, sample_claim, sample_classifications_insufficient):
        """Test consensus calculation with insufficient data"""
        meter = consensus_calculator.calculate_consensus(
            sample_claim, sample_classifications_insufficient
        )

        assert meter.total_sources == 2
        assert meter.consensus_level == ConsensusLevel.INSUFFICIENT_DATA

    def test_calculate_consensus_not_addressed(self, consensus_calculator, sample_claim, sample_classifications_not_addressed):
        """Test consensus calculation with mostly not_addressed stances"""
        meter = consensus_calculator.calculate_consensus(
            sample_claim, sample_classifications_not_addressed
        )

        assert meter.not_addressed == 3
        assert meter.supporting == 1
        assert meter.consensus_level == ConsensusLevel.INSUFFICIENT_DATA

    def test_calculate_consensus_with_retracted_sources(self, consensus_calculator, sample_claim, sample_classifications_strong_agreement):
        """Test consensus calculation excluding retracted sources"""
        # Mark first source as retracted
        retracted_ids = [sample_classifications_strong_agreement[0]["source_id"]]

        meter = consensus_calculator.calculate_consensus(
            sample_claim, sample_classifications_strong_agreement, retracted_ids
        )

        assert meter.total_sources == 4  # Excluded 1 retracted
        assert meter.retracted_sources == 1
        assert meter.supporting == 3  # Reduced from 4 to 3

    def test_calculate_consensus_with_none_classifications(self, consensus_calculator, sample_claim):
        """Test consensus calculation with None values in classifications"""
        classifications = [
            {"source_id": str(uuid4()), "stance": "supporting", "confidence": 0.85},
            None,  # Failed classification
            {"source_id": str(uuid4()), "stance": "opposing", "confidence": 0.80},
            None,  # Another failed classification
        ]

        meter = consensus_calculator.calculate_consensus(sample_claim, classifications)

        assert meter.total_sources == 2  # Only valid classifications
        assert meter.supporting == 1
        assert meter.opposing == 1

    def test_analyze_consensus_trends(self, consensus_calculator, sample_classifications_strong_agreement):
        """Test consensus trend analysis"""
        analysis = consensus_calculator.analyze_consensus_trends(sample_classifications_strong_agreement)

        assert "total_classifications" in analysis
        assert "confidence_distribution" in analysis
        assert "stance_avg_confidence" in analysis
        assert "quality_metrics" in analysis

        assert analysis["total_classifications"] == 5
        assert "high_confidence_pct" in analysis["confidence_distribution"]
        assert "supporting" in analysis["stance_avg_confidence"]

    def test_analyze_consensus_trends_empty(self, consensus_calculator):
        """Test consensus trend analysis with empty input"""
        analysis = consensus_calculator.analyze_consensus_trends([])

        assert "error" in analysis

    def test_format_consensus_description(self, consensus_calculator, sample_claim):
        """Test consensus description formatting"""
        # Create test meter with strong agreement
        from src.api.evidence.schemas import EvidenceMeter

        meter = EvidenceMeter(
            claim=sample_claim,
            claim_hash="test_hash",
            total_sources=5,
            supporting=4,
            opposing=1,
            neutral=0,
            not_addressed=0,
            consensus_level=ConsensusLevel.STRONG_AGREEMENT,
            average_confidence=0.85,
            retracted_sources=0,
            cached=False,
            reproducibility_hash="test_hash"
        )

        description = consensus_calculator.format_consensus_description(meter)

        assert "4 of 5 sources agree" in description

    def test_format_consensus_description_insufficient(self, consensus_calculator, sample_claim):
        """Test consensus description for insufficient data"""
        from src.api.evidence.schemas import EvidenceMeter

        meter = EvidenceMeter(
            claim=sample_claim,
            claim_hash="test_hash",
            total_sources=2,
            supporting=1,
            opposing=0,
            neutral=1,
            not_addressed=0,
            consensus_level=ConsensusLevel.INSUFFICIENT_DATA,
            average_confidence=0.70,
            retracted_sources=0,
            cached=False,
            reproducibility_hash="test_hash"
        )

        description = consensus_calculator.format_consensus_description(meter)

        assert "Limited evidence (2 sources)" in description

    def test_get_consensus_emoji(self, consensus_calculator):
        """Test consensus emoji mapping"""
        assert consensus_calculator.get_consensus_emoji(ConsensusLevel.STRONG_AGREEMENT) == "🟢"
        assert consensus_calculator.get_consensus_emoji(ConsensusLevel.MODERATE_AGREEMENT) == "🟡"
        assert consensus_calculator.get_consensus_emoji(ConsensusLevel.MIXED) == "🟡"
        assert consensus_calculator.get_consensus_emoji(ConsensusLevel.LOW_AGREEMENT) == "🔴"
        assert consensus_calculator.get_consensus_emoji(ConsensusLevel.INSUFFICIENT_DATA) == "⚪"