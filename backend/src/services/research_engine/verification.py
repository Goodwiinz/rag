"""Verification utilities for research engine quality checks."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityMark:
    """Result of a quality check on a step output."""

    check_type: str
    passed: bool
    details: Optional[str] = None


def run_source_grounding_check(claim: str, source_text: str) -> QualityMark:
    """Deterministic check if a claim is grounded in source text.

    - Extract numbers from claim using regex.
    - If no numbers: check word overlap ratio > 0.5 between claim and source.
    - If numbers: check all claim numbers appear in source numbers.
    """
    number_pattern = r"\d+\.?\d*%?"

    claim_numbers = re.findall(number_pattern, claim)
    source_numbers = re.findall(number_pattern, source_text)

    if not claim_numbers:
        # Word overlap check
        claim_words = set(claim.lower().split())
        source_words = set(source_text.lower().split())
        if not claim_words:
            return QualityMark(
                check_type="source_grounding",
                passed=False,
                details="Empty claim",
            )
        overlap = len(claim_words & source_words) / len(claim_words)
        passed = overlap > 0.5
        return QualityMark(
            check_type="source_grounding",
            passed=passed,
            details=f"Word overlap ratio: {overlap:.2f}",
        )

    # Number grounding check
    source_numbers_set = set(source_numbers)
    all_present = all(n in source_numbers_set for n in claim_numbers)
    return QualityMark(
        check_type="source_grounding",
        passed=all_present,
        details=f"Claim numbers: {claim_numbers}, source numbers: {list(source_numbers_set)}",
    )
