'use client';

import React, { useMemo, Fragment } from 'react';
import { cn } from '@/lib/utils';
import { ChatMarkdown } from './ChatMarkdown';
import { CitationLink } from './CitationLink';
import {
  Citation,
  parseMessageWithCitations,
  getCitationByIndex,
  hasCitations,
} from '@/utils/citationParser';

interface CitationRendererProps {
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
  activeCitationIndex?: number;
  className?: string;
}

export function CitationRenderer({
  content,
  citations = [],
  onCitationClick,
  activeCitationIndex,
  className,
}: CitationRendererProps): React.ReactElement {
  const segments = useMemo(() => {
    return parseMessageWithCitations(content);
  }, [content]);

  const hasInlineCitations = useMemo(() => {
    return hasCitations(content);
  }, [content]);

  if (!hasInlineCitations) {
    return (
      <div
        className={cn('prose prose-sm dark:prose-invert max-w-none', className)}
      >
        <ChatMarkdown content={content} />
      </div>
    );
  }

  return (
    <div
      className={cn('prose prose-sm dark:prose-invert max-w-none', className)}
    >
      {segments.map((segment, index) => {
        if (
          segment.type === 'citation' &&
          segment.citationIndex !== undefined
        ) {
          const citation = getCitationByIndex(citations, segment.citationIndex);
          return (
            <CitationLink
              key={`citation-${index}-${segment.citationIndex}`}
              citationNumber={segment.citationIndex}
              citation={citation}
              onClick={onCitationClick}
              isActive={activeCitationIndex === segment.citationIndex}
            />
          );
        }
        return (
          <Fragment key={`text-${index}`}>
            <ChatMarkdown content={segment.content} inline />
          </Fragment>
        );
      })}
    </div>
  );
}

export default CitationRenderer;
