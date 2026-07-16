import { useCallback, useEffect, useState } from 'react';

import { Citation } from '@/utils/citationParser';

// ============================================
// HOOK PARAMS
// ============================================

export interface UseCitationPanelParams {
  setInput: React.Dispatch<React.SetStateAction<string>>;
  chatInputRef: React.RefObject<HTMLTextAreaElement>;
}

export interface UseCitationPanelReturn {
  isCitationPanelOpen: boolean;
  setIsCitationPanelOpen: React.Dispatch<React.SetStateAction<boolean>>;
  citationPanelCitations: Citation[];
  activeCitationId: string | undefined;
  citationTraceId: string | undefined;
  handleCitationClick: (
    citations: Citation[],
    clickedCitation: Citation,
    traceId?: string
  ) => void;
  handleCiteSource: (citation: Citation) => void;
}

// ============================================
// HOOK
// ============================================

/**
 * Citation panel state: which citations are shown, which one is active, and
 * the diagnostics trace id — plus the two ways the panel opens (a click on an
 * in-transcript citation, or the layout's ContextRail bridging a synthetic
 * citation via the 'open-citation-panel' window event, since the rail lives
 * outside this page's component tree).
 */
export function useCitationPanel({
  setInput,
  chatInputRef,
}: UseCitationPanelParams): UseCitationPanelReturn {
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState(false);
  const [citationPanelCitations, setCitationPanelCitations] = useState<
    Citation[]
  >([]);
  const [activeCitationId, setActiveCitationId] = useState<string | undefined>(
    undefined
  );
  const [citationTraceId, setCitationTraceId] = useState<string | undefined>(
    undefined
  );

  // Open the citation panel for a synthetic citation handed over from the
  // layout's ContextRail (document/external preview clicks). The rail lives
  // in the layout component, so it cannot reach this page's panel state
  // directly — same window-event idiom as 'populate-chat-input'.
  useEffect(() => {
    const handleOpenCitationPanel = (event: CustomEvent<Citation>): void => {
      const citation = event.detail;
      if (!citation?.title) return;
      setCitationPanelCitations([citation]);
      setActiveCitationId(citation.documentId || citation.externalReferenceId);
      setCitationTraceId(undefined);
      setIsCitationPanelOpen(true);
    };

    window.addEventListener(
      'open-citation-panel',
      handleOpenCitationPanel as EventListener
    );
    return () => {
      window.removeEventListener(
        'open-citation-panel',
        handleOpenCitationPanel as EventListener
      );
    };
  }, []);

  const handleCitationClick = useCallback(
    (citations: Citation[], clickedCitation: Citation, traceId?: string) => {
      setCitationPanelCitations(citations);
      setActiveCitationId(
        clickedCitation.documentId || clickedCitation.externalReferenceId
      );
      setCitationTraceId(traceId);
      setIsCitationPanelOpen(true);
    },
    []
  );

  // Insert a reference to a source into the composer (the panel "Cite" action).
  const handleCiteSource = useCallback(
    (citation: Citation) => {
      setInput((cur) =>
        cur ? `${cur} "${citation.title}"` : `"${citation.title}" `
      );
      chatInputRef.current?.focus();
      setIsCitationPanelOpen(false);
    },
    [setInput, chatInputRef]
  );

  return {
    isCitationPanelOpen,
    setIsCitationPanelOpen,
    citationPanelCitations,
    activeCitationId,
    citationTraceId,
    handleCitationClick,
    handleCiteSource,
  };
}
