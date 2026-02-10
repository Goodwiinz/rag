# Feature Specification: Evidence Agreement Meter

**Created**: 2025-02-01  
**Status**: Draft  
**Priority**: P1 (Quick Win)

## Overview

Visual indicator showing consensus level across retrieved sources for any research claim. Displays "8 of 10 sources agree" style feedback, providing researchers with immediate insight into evidence strength and disagreement.

**Competitive Reference**: Consensus.app's killer feature. High user trust impact with relatively low implementation complexity.

---

## User Scenarios & Testing

### User Story 1 - View Consensus on a Claim (Priority: P1)

As a researcher, I want to see how many sources agree with a claim so I can quickly assess evidence strength without reading every paper.

**Why this priority**: Core differentiator for research trust. Answers the question "should I trust this?"

**Acceptance Scenarios**:
1. **Given** a search returns 10 relevant sources, **When** I view the answer, **Then** I see "🟢 8 of 10 sources agree" (or similar visual indicator)
2. **Given** sources have mixed positions, **When** I view the answer, **Then** I see "🟡 Mixed evidence (5 agree, 3 disagree, 2 neutral)"
3. **Given** sources contradict the claim, **When** I view the answer, **Then** I see "🔴 Low agreement (2 of 10 sources support)"

---

### User Story 2 - Drill Down into Disagreement (Priority: P1)

As a researcher, I want to see which sources agree and which disagree so I can investigate the controversy.

**Why this priority**: Agreement meter is useless without transparency into the underlying positions.

**Acceptance Scenarios**:
1. **Given** I see "Mixed evidence", **When** I click the meter, **Then** I see a breakdown panel listing sources grouped by position (Supporting, Opposing, Neutral)
2. **Given** the breakdown panel is open, **When** I click a source, **Then** I navigate to that source's detail view with the relevant excerpt highlighted
3. **Given** a source is marked "Opposing", **When** I view its position, **Then** I see the specific excerpt that contradicts the main claim

---

### User Story 3 - Understand Confidence Level (Priority: P2)

As a researcher, I want to know how confident the system is in its stance classification so I can account for uncertainty.

**Why this priority**: Stance detection isn't perfect. Researchers need to know when to verify manually.

**Acceptance Scenarios**:
1. **Given** stance classification confidence is >85%, **When** I view the meter, **Then** no confidence warning is shown
2. **Given** stance classification confidence is <85%, **When** I view the meter, **Then** I see "⚠️ Classification confidence: 72%"
3. **Given** a source has ambiguous stance, **When** I view the breakdown, **Then** that source is marked "Uncertain" with explanation

---

### User Story 4 - Evidence Meter in Systematic Reviews (Priority: P2)

As a researcher conducting a systematic review, I want to see agreement patterns across my entire corpus so I can identify research gaps and consensus areas.

**Why this priority**: Strategic value for professional researchers. Enables higher-tier pricing.

**Acceptance Scenarios**:
1. **Given** I have a systematic review workspace with 50+ papers, **When** I query a claim, **Then** the evidence meter analyzes all 50 papers (not just top 10)
2. **Given** agreement varies by publication year, **When** I view advanced breakdown, **Then** I see a timeline showing how consensus evolved
3. **Given** I'm in systematic review mode, **When** I export results, **Then** the evidence meter data is included in structured format

---

## Edge Cases

- What happens when only 1-2 sources are retrieved? → Show "Limited evidence (2 sources)" with warning
- What happens when sources don't address the claim directly? → Mark as "Not Addressed" rather than forcing a stance
- What happens when the claim is compound ("X AND Y")? → Split into sub-claims with separate meters where possible
- How does system handle sources in different languages? → Analyze in original language, display unified meter
- What if a source is retracted? → Exclude from count, show separate "⚠️ 1 retracted source found"

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST classify each source's stance on a claim as Supporting, Opposing, Neutral, or Not Addressed
- **FR-002**: System MUST compute agreement ratio (supporting / total relevant sources)
- **FR-003**: System MUST extract the specific excerpt from each source that justifies its stance classification
- **FR-004**: System MUST provide confidence score (0-100%) for each stance classification
- **FR-005**: System MUST visually indicate consensus level using color coding (green/yellow/red)
- **FR-006**: System MUST allow drilling down from meter to individual source positions
- **FR-007**: System MUST handle retracted sources separately (exclude from meter, show warning)
- **FR-008**: System MUST include evidence meter data in API responses for programmatic access
- **FR-009**: System MUST cache stance classifications to enable fast re-queries

### Non-Functional Requirements

- **NFR-001**: Stance classification latency MUST be <500ms per source (can run in parallel)
- **NFR-002**: UI update MUST occur within 100ms of receiving meter data
- **NFR-003**: Meter MUST be accessible (WCAG 2.1 AA compliant colors and screen reader support)

---

## Key Entities

- **EvidenceMeter**: The aggregate visualization (agreement count, total sources, consensus level)
- **StanceClassification**: Individual source classification (source_id, stance, confidence, excerpt, claim_id)
- **ConsensusLevel**: Enum (Strong Agreement, Moderate Agreement, Mixed, Low Agreement, Insufficient Data)
- **Stance**: Enum (Supporting, Opposing, Neutral, Not Addressed)

---

## Success Criteria

- **SC-001**: 85% of stance classifications match human annotator labels on test set (100 source-claim pairs)
- **SC-002**: Users report 4.0+ satisfaction (5-point scale) on "evidence meter helps me trust results" survey question
- **SC-003**: Evidence meter loads in <2 seconds for queries with up to 20 sources
- **SC-004**: Click-through rate on meter (to see breakdown) is >30% indicating user engagement
- **SC-005**: Zero critical accessibility violations on evidence meter component
