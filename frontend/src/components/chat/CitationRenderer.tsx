'use client';

import React, { useMemo, Fragment } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '@/lib/utils';
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
}: CitationRendererProps) {
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
        <ReactMarkdown>{content}</ReactMarkdown>
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
            <ReactMarkdown
              components={{
                p: ({ children }) => <span>{children}</span>,
                code({
                  inline,
                  className,
                  children,
                }: {
                  inline?: boolean;
                  className?: string;
                  children?: React.ReactNode;
                }) {
                  const match = /language-(\w+)/.exec(className || '');
                  const language = match ? match[1] : '';
                  return !inline && language ? (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={language}
                      PreTag="div"
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className="rounded bg-[#1a1a1a] px-1.5 py-0.5 text-[11px] font-mono text-[#00ff9f]">
                      {children}
                    </code>
                  );
                },
                a: ({
                  href,
                  children,
                }: {
                  href?: string;
                  children?: React.ReactNode;
                }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#00d4ff] hover:text-[#00ff9f] underline"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {segment.content}
            </ReactMarkdown>
          </Fragment>
        );
      })}
    </div>
  );
}

export default CitationRenderer;
