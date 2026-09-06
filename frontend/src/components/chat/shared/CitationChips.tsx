'use client';

import React from 'react';
import { Activity } from 'lucide-react';

import type { Citation } from '@/utils/citationParser';

export interface CitationChipsProps {
  citations: Citation[];
  diagnosticsTraceId?: string;
  onCitationClick?: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
}

/**
 * Footer chips on committed assistant messages: one chip per visible
 * citation (title + relevance %), plus a DIAG link when a retrieval trace
 * id is attached. Shared by the legacy ChatBubble and the assistant-ui
 * message renderer.
 */
export function CitationChips({
  citations,
  diagnosticsTraceId,
  onCitationClick,
}: CitationChipsProps): React.JSX.Element | null {
  if (citations.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {citations.map((citation, idx) => (
        <button
          key={idx}
          type="button"
          onClick={() => {
            if (onCitationClick) {
              onCitationClick(citations, citation, diagnosticsTraceId);
            }
          }}
          className="group/citation flex items-center gap-2 rounded-md border border-(--nous-border-1) bg-(--nous-bg-2) px-2.5 py-1.5 text-[10px] transition-colors hover:border-(--nous-sol)/40 hover:bg-(--nous-aurum) dark:hover:bg-(--nous-ember)"
        >
          <div className="h-1.5 w-1.5 rounded-full bg-(--nous-sol)/40 transition-colors group-hover/citation:bg-(--nous-sol) dark:bg-(--nous-helios)/40 dark:group-hover/citation:bg-(--nous-helios)" />
          <span className="max-w-[180px] truncate text-(--nous-fg-1)">
            {citation.title}
          </span>
          <span className="border-l border-(--nous-border-1) pl-2 text-(--nous-fg-3) tabular-nums">
            {Math.round(citation.score * 100)}%
          </span>
        </button>
      ))}
      {diagnosticsTraceId && (
        <a
          href={`/diagnostics?trace=${encodeURIComponent(diagnosticsTraceId)}`}
          className="ml-auto flex items-center gap-1 rounded-md border border-(--nous-border-1) bg-(--nous-bg-2) px-2 py-1 text-[9px] text-(--nous-fg-3) transition-colors hover:border-(--nous-sol)/40 hover:text-(--nous-sol-safe) dark:hover:text-(--nous-helios)"
          title="View retrieval diagnostics"
        >
          <Activity className="h-3 w-3" />
          <span>DIAG</span>
        </a>
      )}
    </div>
  );
}
