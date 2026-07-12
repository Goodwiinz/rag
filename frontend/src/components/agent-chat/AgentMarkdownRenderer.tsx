'use client';

import React, { useMemo, Fragment, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import dynamic from 'next/dynamic';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const SyntaxHighlighter = dynamic(
  () => import('react-syntax-highlighter/dist/esm/prism').then((mod) => mod.default),
  {
    loading: () => (
      <pre className="p-4 rounded bg-[var(--nous-bg-1)] text-xs font-mono overflow-x-auto">
        <code>Loading...</code>
      </pre>
    ),
    ssr: false,
  }
);
import { Copy, Check } from 'lucide-react';
import { AgentCitationBadge } from './AgentCitationBadge';
import {
  parseMessageWithCitations,
  getCitationByIndex,
  hasCitations,
} from '@/utils/citationParser';
import type { AgentCitation } from '@/types/agent-chat';
import type { Citation } from '@/utils/citationParser';

interface AgentMarkdownRendererProps {
  content: string;
  citations?: AgentCitation[];
}

/** Map AgentCitation to Citation type used by citationParser */
function toCitation(ac: AgentCitation): Citation {
  return {
    documentId: ac.documentId,
    title: ac.documentTitle,
    content: ac.snippet,
    score: ac.score ?? 0,
  };
}

function CodeBlockCopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <button
      onClick={handleCopy}
      aria-label="Copy code"
      className="absolute top-2 right-2 p-1.5 rounded-md bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors opacity-0 group-hover/code:opacity-100"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

const markdownComponents = {
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
    const codeStr = String(children).replace(/\n$/, '');

    if (!inline && language) {
      return (
        <div className="relative group/code my-3 rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-1.5 bg-muted/60 border-b border-border text-[10px] text-muted-foreground font-mono">
            {language}
          </div>
          <SyntaxHighlighter
            style={oneDark}
            language={language}
            PreTag="div"
            customStyle={{
              margin: 0,
              borderRadius: 0,
              fontSize: '12px',
            }}
          >
            {codeStr}
          </SyntaxHighlighter>
          <CodeBlockCopyButton code={codeStr} />
        </div>
      );
    }

    // Fenced code block without language
    if (!inline && codeStr.includes('\n')) {
      return (
        <div className="relative group/code my-3 rounded-lg overflow-hidden">
          <SyntaxHighlighter
            style={oneDark}
            language="text"
            PreTag="div"
            customStyle={{
              margin: 0,
              borderRadius: '0.5rem',
              fontSize: '12px',
            }}
          >
            {codeStr}
          </SyntaxHighlighter>
          <CodeBlockCopyButton code={codeStr} />
        </div>
      );
    }

    return (
      <code className="rounded bg-muted px-1.5 py-0.5 text-[12px] font-mono text-foreground">
        {children}
      </code>
    );
  },
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:text-primary/80 underline underline-offset-2"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="border-l-2 border-primary/30 pl-3 my-2 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-disc pl-4 my-2 space-y-1">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal pl-4 my-2 space-y-1">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="text-sm text-foreground leading-relaxed">{children}</li>
  ),
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-base font-semibold text-foreground mt-4 mb-2">
      {children}
    </h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-sm font-semibold text-foreground mt-3 mb-1.5">
      {children}
    </h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-sm font-medium text-foreground mt-2 mb-1">
      {children}
    </h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="text-sm text-foreground leading-relaxed my-1.5">{children}</p>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-muted/50">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-3 py-1.5 text-left text-xs font-medium text-muted-foreground border-b border-border">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-3 py-1.5 text-sm text-foreground border-b border-border/50">
      {children}
    </td>
  ),
  hr: () => <hr className="my-3 border-border" />,
};

export function AgentMarkdownRenderer({
  content,
  citations = [],
}: AgentMarkdownRendererProps) {
  const parsedCitations = useMemo(() => citations.map(toCitation), [citations]);

  const hasInlineCitations = useMemo(() => hasCitations(content), [content]);

  // No inline citations — render plain markdown
  if (!hasInlineCitations) {
    return (
      <div className="agent-markdown">
        <ReactMarkdown components={markdownComponents as never}>
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  // Has inline citations — parse and render segments
  const segments = parseMessageWithCitations(content);

  return (
    <div className="agent-markdown">
      {segments.map((segment, index) => {
        if (
          segment.type === 'citation' &&
          segment.citationIndex !== undefined
        ) {
          const citation = getCitationByIndex(
            parsedCitations,
            segment.citationIndex
          );
          const agentCitation = citation
            ? citations[segment.citationIndex - 1]
            : undefined;

          return (
            <AgentCitationBadge
              key={`citation-${index}-${segment.citationIndex}`}
              citationNumber={segment.citationIndex}
              citation={agentCitation}
            />
          );
        }
        return (
          <Fragment key={`text-${index}`}>
            <ReactMarkdown
              components={
                {
                  ...markdownComponents,
                  // In inline-citation mode, avoid wrapping each segment in <p>
                  p: ({ children }: { children?: React.ReactNode }) => (
                    <span>{children}</span>
                  ),
                } as never
              }
            >
              {segment.content}
            </ReactMarkdown>
          </Fragment>
        );
      })}
    </div>
  );
}
