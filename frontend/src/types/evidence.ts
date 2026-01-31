/**
 * Types for Evidence Agreement Meter feature
 */

/** Stance classification for a source on a claim */
export type Stance = 'supporting' | 'opposing' | 'neutral' | 'not_addressed';

/** Overall consensus level based on agreement */
export type ConsensusLevel = 
  | 'strong_agreement' 
  | 'moderate_agreement' 
  | 'mixed' 
  | 'low_agreement' 
  | 'insufficient_data';

/** Classification for a single source */
export interface StanceClassification {
  source_id: string;
  title: string;
  stance: Stance;
  confidence: number;
  justification_excerpt: string;
  is_retracted: boolean;
}

/** Evidence meter data from API */
export interface EvidenceMeterData {
  claim: string;
  claim_hash: string;
  total_sources: number;
  supporting: number;
  opposing: number;
  neutral: number;
  not_addressed: number;
  consensus_level: ConsensusLevel;
  average_confidence: number;
  retracted_sources: number;
  cached: boolean;
  reproducibility_hash: string;
}

/** Evidence breakdown data from API */
export interface EvidenceBreakdownData {
  claim: string;
  sources: StanceClassification[];
}

/** Props for EvidenceMeter component */
export interface EvidenceMeterProps {
  claim: string;
  sourceIds?: string[];
  queryId?: string;
  className?: string;
  onSourceClick?: (sourceId: string) => void;
}

/** Props for EvidenceBreakdown component */
export interface EvidenceBreakdownProps {
  claimHash: string;
  claim: string;
  sources: StanceClassification[];
  onSourceClick?: (sourceId: string) => void;
  className?: string;
}

/** Props for StanceBadge component */
export interface StanceBadgeProps {
  stance: Stance;
  confidence?: number;
  showConfidence?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/** Props for ConfidenceIndicator component */
export interface ConfidenceIndicatorProps {
  confidence: number;
  threshold?: number;
  className?: string;
}

/** Segment data for animated meter */
export interface MeterSegment {
  stance: Exclude<Stance, 'not_addressed'>;
  count: number;
  percentage: number;
  color: string;
}
