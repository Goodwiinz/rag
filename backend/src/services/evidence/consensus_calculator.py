"""
Consensus Calculator for Evidence Agreement Meter

Aggregates stance classifications to compute consensus levels and metrics
"""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from ...api.evidence.schemas import ConsensusLevel, EvidenceMeter, Stance

logger = logging.getLogger(__name__)


class ConsensusCalculator:
    """Service for calculating consensus metrics from stance classifications"""
    
    def __init__(self):
        self.model_version = "gpt-4o-mini-2024-07-18"
    
    def _normalize_claim(self, claim: str) -> str:
        """Normalize claim text for consistent hashing"""
        # Convert to lowercase, strip whitespace, normalize spaces
        normalized = " ".join(claim.lower().strip().split())
        return normalized
    
    def _generate_claim_hash(self, claim: str) -> str:
        """Generate SHA256 hash of normalized claim"""
        normalized = self._normalize_claim(claim)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def _determine_consensus_level(
        self, total_sources: int, supporting: int, opposing: int, neutral: int, not_addressed: int
    ) -> ConsensusLevel:
        """Determine consensus level based on stance distribution"""
        
        # Handle insufficient evidence case (<3 sources)
        if total_sources < 3:
            return ConsensusLevel.INSUFFICIENT_DATA
        
        # Calculate relevant sources (supporting + opposing, excluding neutral and not_addressed)
        relevant_sources = supporting + opposing
        
        # Handle "Not Addressed" stance - if most sources don't address the claim
        if not_addressed > (total_sources // 2):
            return ConsensusLevel.INSUFFICIENT_DATA
        
        # If no sources take a position, insufficient data
        if relevant_sources == 0:
            return ConsensusLevel.INSUFFICIENT_DATA
        
        # Calculate agreement ratio
        agreement_ratio = supporting / relevant_sources
        
        # Classify consensus level with enhanced logic
        if agreement_ratio >= 0.8:
            return ConsensusLevel.STRONG_AGREEMENT
        elif agreement_ratio >= 0.6:
            return ConsensusLevel.MODERATE_AGREEMENT
        elif agreement_ratio >= 0.4:
            return ConsensusLevel.MIXED
        else:
            return ConsensusLevel.LOW_AGREEMENT
    
    def _generate_reproducibility_hash(
        self, claim_hash: str, source_ids: List[str], model_version: str
    ) -> str:
        """Generate hash for reproducibility tracking"""
        # Sort source IDs for consistent ordering
        sorted_sources = sorted(source_ids)
        source_hash = hashlib.sha256(
            "|".join(sorted_sources).encode('utf-8')
        ).hexdigest()[:16]
        
        components = [
            "meter_v1",
            claim_hash[:16], 
            f"{len(sorted_sources)}src",
            source_hash,
            model_version.split("-")[0]  # e.g. "gpt-4o-mini" from "gpt-4o-mini-2024-07-18"
        ]
        
        return "_".join(components)
    
    def calculate_consensus(
        self, claim: str, classifications: List[Dict], retracted_source_ids: Optional[List[str]] = None
    ) -> EvidenceMeter:
        """
        Calculate consensus metrics from stance classifications
        
        Args:
            claim: Original claim text
            classifications: List of classification dicts from stance_classifier
            retracted_source_ids: Optional list of retracted source IDs to exclude
            
        Returns:
            EvidenceMeter with computed consensus metrics
        """
        
        claim_hash = self._generate_claim_hash(claim)
        retracted_ids = set(retracted_source_ids or [])
        
        # Filter out retracted sources and None classifications
        valid_classifications = [
            c for c in classifications 
            if c is not None and c.get("source_id") not in retracted_ids
        ]
        
        # Count stance distributions
        stance_counts = {
            "supporting": 0,
            "opposing": 0,
            "neutral": 0,
            "not_addressed": 0,
        }
        
        confidence_scores = []
        source_ids = []
        
        for classification in valid_classifications:
            stance = classification.get("stance")
            confidence = classification.get("confidence", 0.0)
            source_id = classification.get("source_id")
            
            if stance in stance_counts:
                stance_counts[stance] += 1
                confidence_scores.append(confidence)
                source_ids.append(source_id)
            else:
                logger.warning(f"Unknown stance value: {stance}")
        
        total_sources = len(valid_classifications)
        supporting = stance_counts["supporting"]
        opposing = stance_counts["opposing"] 
        neutral = stance_counts["neutral"]
        not_addressed = stance_counts["not_addressed"]
        
        # Calculate metrics
        average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        consensus_level = self._determine_consensus_level(total_sources, supporting, opposing, neutral, not_addressed)
        
        # Generate reproducibility hash
        reproducibility_hash = self._generate_reproducibility_hash(
            claim_hash, source_ids, self.model_version
        )
        
        return EvidenceMeter(
            claim=claim,
            claim_hash=claim_hash,
            total_sources=total_sources,
            supporting=supporting,
            opposing=opposing,
            neutral=neutral,
            not_addressed=not_addressed,
            consensus_level=consensus_level,
            average_confidence=average_confidence,
            retracted_sources=len(retracted_ids),
            cached=False,  # Will be set by caller if from cache
            reproducibility_hash=reproducibility_hash
        )
    
    def analyze_consensus_trends(self, classifications: List[Dict]) -> Dict:
        """
        Analyze trends in consensus data
        
        Args:
            classifications: List of classification dicts
            
        Returns:
            Dict with trend analysis
        """
        
        if not classifications:
            return {"error": "No classifications provided"}
        
        # Group by confidence ranges
        confidence_ranges = {
            "high": 0,      # >=0.85
            "medium": 0,    # 0.7-0.85
            "low": 0        # <0.7
        }
        
        stance_confidence = {
            "supporting": [],
            "opposing": [],
            "neutral": [],
            "not_addressed": []
        }
        
        for classification in classifications:
            if not classification:
                continue
                
            confidence = classification.get("confidence", 0.0)
            stance = classification.get("stance")
            
            # Categorize confidence
            if confidence >= 0.85:
                confidence_ranges["high"] += 1
            elif confidence >= 0.7:
                confidence_ranges["medium"] += 1
            else:
                confidence_ranges["low"] += 1
            
            # Track stance-specific confidence
            if stance in stance_confidence:
                stance_confidence[stance].append(confidence)
        
        # Calculate stance-specific averages
        stance_avg_confidence = {}
        for stance, confidences in stance_confidence.items():
            if confidences:
                stance_avg_confidence[stance] = sum(confidences) / len(confidences)
            else:
                stance_avg_confidence[stance] = 0.0
        
        total = len(classifications)
        
        return {
            "total_classifications": total,
            "confidence_distribution": {
                "high_confidence_pct": (confidence_ranges["high"] / total * 100) if total > 0 else 0,
                "medium_confidence_pct": (confidence_ranges["medium"] / total * 100) if total > 0 else 0,
                "low_confidence_pct": (confidence_ranges["low"] / total * 100) if total > 0 else 0,
            },
            "stance_avg_confidence": stance_avg_confidence,
            "quality_metrics": {
                "high_confidence_count": confidence_ranges["high"],
                "needs_review": confidence_ranges["low"],  # Low confidence classifications
                "review_threshold": 0.7
            }
        }
    
    def format_consensus_description(self, meter: EvidenceMeter) -> str:
        """
        Generate human-readable consensus description
        
        Args:
            meter: EvidenceMeter instance
            
        Returns:
            Formatted consensus description
        """
        
        if meter.consensus_level == ConsensusLevel.INSUFFICIENT_DATA:
            return f"Limited evidence ({meter.total_sources} sources)"
        
        relevant_sources = meter.supporting + meter.opposing
        if relevant_sources == 0:
            return f"No clear positions found ({meter.total_sources} sources reviewed)"
        
        if meter.consensus_level == ConsensusLevel.STRONG_AGREEMENT:
            return f"{meter.supporting} of {relevant_sources} sources agree"
        elif meter.consensus_level == ConsensusLevel.MODERATE_AGREEMENT:
            return f"{meter.supporting} of {relevant_sources} sources support (moderate agreement)"
        elif meter.consensus_level == ConsensusLevel.MIXED:
            return f"Mixed evidence ({meter.supporting} support, {meter.opposing} oppose)"
        else:  # LOW_AGREEMENT
            return f"Low agreement ({meter.supporting} of {relevant_sources} sources support)"
    
    def get_consensus_emoji(self, consensus_level: ConsensusLevel) -> str:
        """Get emoji indicator for consensus level"""
        emoji_map = {
            ConsensusLevel.STRONG_AGREEMENT: "🟢",
            ConsensusLevel.MODERATE_AGREEMENT: "🟡", 
            ConsensusLevel.MIXED: "🟡",
            ConsensusLevel.LOW_AGREEMENT: "🔴",
            ConsensusLevel.INSUFFICIENT_DATA: "⚪"
        }
        return emoji_map.get(consensus_level, "❓")