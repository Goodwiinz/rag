'use client';

import React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import dynamic from 'next/dynamic';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const SyntaxHighlighter = dynamic(
  () =>
    import('react-syntax-highlighter/dist/esm/prism').then(
      (mod) => mod.default
    ),
  {
    loading: () => (
      <pre className="p-4 rounded-lg bg-(--nous-bg-1) text-xs font-mono overflow-x-auto">
        <code>Loading...</code>
      </pre>
    ),
    ssr: false,
  }
);

/** remark plugins every chat message renders with (GFM: tables, task lists,
 * strikethrough, autolinks). Shared so the plain and citation-segmented
 * paths can't drift apart again. */
const REMARK_PLUGINS = [remarkGfm];

/**
 * One markdown component config for all assistant-message rendering.
 *
 * react-markdown v9+ no longer passes `inline` to the `code` renderer, so
 * block-vs-inline is detected from the fence's `language-*` class (fenced
 * blocks) or an embedded newline (fenced blocks without a language). Fenced
 * code goes through the lazy syntax highlighter; inline spans get the NOUS
 * pill styling.
 */
const baseComponents: Components = {
  code({ className, children }) {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const value = String(children).replace(/\n$/, '');
    if (language) {
      return (
        <SyntaxHighlighter style={oneDark} language={language} PreTag="div">
          {value}
        </SyntaxHighlighter>
      );
    }
    if (value.includes('\n')) {
      return (
        <pre className="p-4 rounded-lg bg-(--nous-bg-1) text-xs font-mono overflow-x-auto">
          <code>{value}</code>
        </pre>
      );
    }
    return (
      <code className="rounded bg-(--nous-bg-2) px-1.5 py-0.5 text-[11px] font-mono text-(--nous-sol)">
        {children}
      </code>
    );
  },
  // The code renderer above emits its own block containers; a wrapping <pre>
  // from the default renderer would nest pre-in-pre.
  pre({ children }) {
    return <>{children}</>;
  },
  // SECURITY (audit #21): LLM-authored links open with
  // rel="noopener noreferrer" so a malicious target can't reach back via
  // window.opener (reverse tabnabbing).
  a({ href, children }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-(--nous-sol) hover:text-(--nous-helios) underline"
      >
        {children}
      </a>
    );
  },
  // GFM tables can exceed the bubble width; scroll them instead of breaking
  // the chat column layout.
  table({ children }) {
    return (
      <div className="overflow-x-auto">
        <table>{children}</table>
      </div>
    );
  },
};

/** Variant for citation text segments: paragraphs unwrap to spans so a
 * <CitationLink> can sit inline between two markdown fragments. */
const inlineComponents: Components = {
  ...baseComponents,
  p({ children }) {
    return <span>{children}</span>;
  },
};

export interface ChatMarkdownProps {
  content: string;
  /** Unwrap paragraphs to spans (citation-segment interleaving). */
  inline?: boolean;
}

/** The single markdown renderer for chat message bodies. */
export function ChatMarkdown({
  content,
  inline = false,
}: ChatMarkdownProps): React.ReactElement {
  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      components={inline ? inlineComponents : baseComponents}
    >
      {content}
    </ReactMarkdown>
  );
}

export default ChatMarkdown;
