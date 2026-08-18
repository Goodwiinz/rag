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
  /** Tint the trailing text while a turn is still arriving. */
  freshTail?: boolean;
}

/** Split a message into fenced-code chunks and prose chunks. Citation
 * markers are only parsed in prose: bracketed indexing inside a code fence
 * (`arr[1]`) must render as code, not get carved out into a citation chip
 * that truncates the block. An unterminated final fence (mid-stream) stays
 * one code chunk. */
function splitOnCodeFences(
  content: string
): Array<{ type: 'code' | 'prose'; content: string }> {
  const chunks: Array<{ type: 'code' | 'prose'; content: string }> = [];
  let buf: string[] = [];
  let inFence = false;

  const flush = (type: 'code' | 'prose'): void => {
    if (buf.length > 0) {
      chunks.push({ type, content: buf.join('\n') });
      buf = [];
    }
  };

  for (const line of content.split('\n')) {
    if (line.trimStart().startsWith('```')) {
      if (inFence) {
        buf.push(line);
        flush('code');
        inFence = false;
      } else {
        flush('prose');
        inFence = true;
        buf.push(line);
      }
    } else {
      buf.push(line);
    }
  }
  flush(inFence ? 'code' : 'prose');
  return chunks;
}

export function CitationRenderer({
  content,
  citations = [],
  onCitationClick,
  activeCitationIndex,
  className,
  freshTail = false,
}: CitationRendererProps): React.ReactElement {
  const chunks = useMemo(() => splitOnCodeFences(content), [content]);

  // Bare bracketed numbers only resolve against the sources this message
  // actually carries (round-3 M11) — same rule as the agent panel's renderer.
  const citationCount = citations.length;
  const hasInlineCitations = useMemo(
    () =>
      chunks.some(
        (chunk) =>
          chunk.type === 'prose' &&
          hasCitations(chunk.content, { citationCount })
      ),
    [chunks, citationCount]
  );

  if (!hasInlineCitations) {
    return (
      <div
        className={cn('prose prose-sm dark:prose-invert max-w-none', className)}
      >
        <ChatMarkdown freshTail={freshTail} content={content} />
      </div>
    );
  }

  return (
    <div
      className={cn('prose prose-sm dark:prose-invert max-w-none', className)}
    >
      {chunks.map((chunk, chunkIndex) => {
        if (chunk.type === 'code') {
          return (
            <ChatMarkdown key={`code-${chunkIndex}`} content={chunk.content} />
          );
        }
        return (
          <Fragment key={`prose-${chunkIndex}`}>
            {parseMessageWithCitations(chunk.content, { citationCount }).map(
              (segment, index, segments) => {
                if (
                  segment.type === 'citation' &&
                  segment.citationIndex !== undefined
                ) {
                  const citation = getCitationByIndex(
                    citations,
                    segment.citationIndex
                  );
                  return (
                    <CitationLink
                      key={`citation-${chunkIndex}-${index}-${segment.citationIndex}`}
                      citationNumber={segment.citationIndex}
                      citation={citation}
                      onClick={onCitationClick}
                      isActive={activeCitationIndex === segment.citationIndex}
                    />
                  );
                }
                return (
                  <Fragment key={`text-${chunkIndex}-${index}`}>
                    {/* Only the final segment of the final chunk holds text
                      that just arrived; tinting every segment's tail would
                      light up the whole message. */}
                    <ChatMarkdown
                      freshTail={
                        freshTail &&
                        chunkIndex === chunks.length - 1 &&
                        index === segments.length - 1
                      }
                      content={segment.content}
                      inline
                    />
                  </Fragment>
                );
              }
            )}
          </Fragment>
        );
      })}
    </div>
  );
}

export default CitationRenderer;
