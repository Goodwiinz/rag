/**
 * Hook for fetching and managing Evidence Meter data
 */

import { useQuery } from '@tanstack/react-query';
import { getAPIClient } from '@/services/api-client';
import type { EvidenceMeterData, EvidenceBreakdownData, Stance } from '@/types/evidence';

interface UseEvidenceMeterOptions {
  claim: string;
  sourceIds?: string[];
  queryId?: string;
  enabled?: boolean;
}

interface UseEvidenceBreakdownOptions {
  claimHash: string;
  stanceFilter?: Stance;
  enabled?: boolean;
}

/**
 * Fetch evidence meter data for a claim
 */
export function useEvidenceMeter({
  claim,
  sourceIds,
  queryId,
  enabled = true,
}: UseEvidenceMeterOptions) {
  return useQuery<EvidenceMeterData>({
    queryKey: ['evidence-meter', claim, sourceIds, queryId],
    queryFn: async () => {
      const api = getAPIClient();
      const params = new URLSearchParams();
      params.set('claim', claim);
      
      if (sourceIds?.length) {
        sourceIds.forEach(id => params.append('source_ids', id));
      }
      
      if (queryId) {
        params.set('query_id', queryId);
      }
      
      const data = await api.get<EvidenceMeterData>(
        `/api/v1/evidence/meter?${params.toString()}`
      );
      
      return data;
    },
    enabled: enabled && !!claim,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Fetch evidence breakdown for a claim hash
 */
export function useEvidenceBreakdown({
  claimHash,
  stanceFilter,
  enabled = true,
}: UseEvidenceBreakdownOptions) {
  return useQuery<EvidenceBreakdownData>({
    queryKey: ['evidence-breakdown', claimHash, stanceFilter],
    queryFn: async () => {
      const api = getAPIClient();
      const params = new URLSearchParams();
      params.set('claim_hash', claimHash);
      
      if (stanceFilter) {
        params.set('stance_filter', stanceFilter);
      }
      
      const data = await api.get<EvidenceBreakdownData>(
        `/api/v1/evidence/breakdown?${params.toString()}`
      );
      
      return data;
    },
    enabled: enabled && !!claimHash,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Get consensus display text
 */
export function getConsensusText(data: EvidenceMeterData): string {
  const { supporting, opposing, neutral, total_sources, consensus_level } = data;
  const relevant = supporting + opposing + neutral;
  
  if (total_sources === 0) {
    return 'No sources found';
  }
  
  if (relevant < 3) {
    return `Limited evidence (${relevant} source${relevant === 1 ? '' : 's'})`;
  }
  
  switch (consensus_level) {
    case 'strong_agreement':
      return `${supporting} of ${relevant} sources agree`;
    case 'moderate_agreement':
      return `${supporting} of ${relevant} sources agree`;
    case 'mixed':
      return `Mixed evidence (${supporting}/${opposing}/${neutral})`;
    case 'low_agreement':
      return `Low agreement (${supporting} of ${relevant} support)`;
    case 'insufficient_data':
      return `Insufficient data (${relevant} sources)`;
    default:
      return `${supporting} of ${relevant} sources agree`;
  }
}

/**
 * Get consensus level color class
 */
export function getConsensusColor(consensus_level: string): string {
  switch (consensus_level) {
    case 'strong_agreement':
      return 'text-green-600 dark:text-green-400';
    case 'moderate_agreement':
      return 'text-green-500 dark:text-green-300';
    case 'mixed':
      return 'text-yellow-600 dark:text-yellow-400';
    case 'low_agreement':
      return 'text-red-500 dark:text-red-400';
    case 'insufficient_data':
      return 'text-gray-500 dark:text-gray-400';
    default:
      return 'text-gray-600 dark:text-gray-300';
  }
}

/**
 * Get consensus emoji indicator
 */
export function getConsensusEmoji(consensus_level: string): string {
  switch (consensus_level) {
    case 'strong_agreement':
    case 'moderate_agreement':
      return '🟢';
    case 'mixed':
      return '🟡';
    case 'low_agreement':
      return '🔴';
    case 'insufficient_data':
      return '⚪';
    default:
      return '⚪';
  }
}
