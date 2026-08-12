'use client';

import React from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { BookOpen, X } from 'lucide-react';
import { IconButton } from '@/components/ui/icon-button';
import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/utils';
import { Citation, getCitationIdentifier } from '@/utils/citationParser';
import { CitationPanelBody } from './CitationPanelBody';

interface CitationPanelProps {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
  /** Open the source document for a citation. */
  onCitationClick?: (citation: Citation) => void;
  /** Insert a reference to the source into the composer. */
  onCite?: (citation: Citation) => void;
  /** Retrieval trace id for the answer these sources grounded. */
  diagnosticsTraceId?: string;
  activeCitationId?: string;
  className?: string;
}

/**
 * Legacy positioned wrapper around CitationPanelBody: a fixed right-docked
 * overlay (bottom sheet on mobile). The chat split-view now shows sources in
 * the ArtifactPanel instead; this wrapper remains for any host that still
 * wants the overlay treatment and to keep the '@/components/chat' barrel
 * surface stable (the ChatPage test suites mock exactly that specifier).
 */
export function CitationPanel({
  citations,
  isOpen,
  onClose,
  onCitationClick,
  onCite,
  diagnosticsTraceId,
  activeCitationId,
  className,
}: CitationPanelProps) {
  const reduce = useReducedMotion();
  const isMobile = useIsMobile();

  const groupCount = new Set(citations.map((c) => getCitationIdentifier(c)))
    .size;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.aside
          aria-label="Sources"
          initial={
            reduce
              ? { opacity: 0 }
              : isMobile
                ? { y: '100%', opacity: 0 }
                : { x: '100%', opacity: 0 }
          }
          animate={{ x: 0, y: 0, opacity: 1 }}
          exit={
            reduce
              ? { opacity: 0 }
              : isMobile
                ? { y: '100%', opacity: 0 }
                : { x: '100%', opacity: 0 }
          }
          transition={{ type: 'spring', damping: 26, stiffness: 300 }}
          className={cn(
            'fixed z-50 flex flex-col bg-(--nous-bg-1)',
            // Desktop / tablet: right-docked full-height column.
            'sm:right-0 sm:top-0 sm:bottom-0 sm:w-[400px] sm:max-w-[90vw]',
            'sm:border-l sm:border-(--nous-border-1) sm:rounded-none',
            // Mobile: bottom sheet — full width, capped height, rounded top —
            // so the transcript stays visible instead of being covered by a
            // fixed right-edge column.
            'max-sm:inset-x-0 max-sm:bottom-0 max-sm:h-[75dvh] max-sm:w-full',
            'max-sm:rounded-t-(--nous-radius-xl) max-sm:border-t max-sm:border-(--nous-border-1)',
            className
          )}
          style={{
            boxShadow: isMobile
              ? '0 -12px 40px rgba(var(--nous-erebus-rgb), 0.18)'
              : '-20px 0 60px rgba(var(--nous-erebus-rgb), 0.18)',
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2 border-b border-(--nous-border-1) bg-(--nous-bg-2) px-4 py-3">
            <div className="flex items-center gap-2">
              <BookOpen
                className="h-4 w-4"
                style={{ color: 'var(--nous-sol)' }}
                aria-hidden
              />
              <h2
                className="font-nous-ui text-sm font-semibold"
                style={{ color: 'var(--nous-fg-1)' }}
              >
                Sources
              </h2>
              <span
                className="font-nous-mono text-[10px] tabular-nums rounded-full px-1.5 py-0.5"
                style={{
                  background: 'var(--nous-sol-subtle)',
                  color: 'var(--nous-fg-accent-safe)',
                }}
              >
                {groupCount}
              </span>
            </div>
            <IconButton
              icon={<X className="h-4 w-4" />}
              label="Close sources panel"
              onClick={onClose}
              className="h-8 w-8 text-(--nous-fg-3) hover:bg-(--nous-aurum) hover:text-(--nous-fg-1)"
            />
          </div>

          <CitationPanelBody
            citations={citations}
            onCitationClick={onCitationClick}
            onCite={onCite}
            diagnosticsTraceId={diagnosticsTraceId}
            activeCitationId={activeCitationId}
          />
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

export default CitationPanel;
