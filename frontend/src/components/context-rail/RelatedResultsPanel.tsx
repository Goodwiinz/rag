'use client';

import * as React from 'react';
import { FileText } from 'lucide-react';
import { useCitationsForThread } from '@/hooks';

function scoreColor(percent: number): string {
  if (percent >= 70) return 'var(--nous-terra)';
  if (percent >= 50) return 'var(--nous-corona)';
  return 'var(--nous-fg-3)';
}

export function RelatedResultsPanel() {
  const { relatedResults } = useCitationsForThread();

  return (
    <section aria-label="Related results">
      <div
        className="text-[10px] uppercase tracking-wider mb-2 px-1"
        style={{
          color: 'var(--nous-fg-3)',
          fontFamily: 'var(--nous-font-ui)',
        }}
      >
        Related Results
      </div>

      {relatedResults.length === 0 ? (
        <div
          className="rounded-xl border p-4 text-xs"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
            color: 'var(--nous-fg-3)',
            fontFamily: 'var(--nous-font-body)',
          }}
        >
          No related results yet. Ask a question to pull relevant documents.
        </div>
      ) : (
        <ul
          className="rounded-xl border p-2 space-y-1"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
          }}
        >
          {relatedResults.map((doc, idx) => {
            const pct = doc.score ? Math.round(doc.score * 100) : 0;
            return (
              <li
                key={doc.documentId || doc.externalReferenceId || idx}
                className="flex items-start gap-3 px-3 py-2 rounded-lg"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                <FileText
                  className="w-3.5 h-3.5 mt-0.5 shrink-0"
                  style={{ color: 'var(--nous-sol)' }}
                />
                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm truncate"
                    style={{ color: 'var(--nous-fg-1)' }}
                    title={doc.title}
                  >
                    {doc.title || 'Untitled document'}
                  </p>
                  <p
                    className="text-[11px]"
                    style={{ color: scoreColor(pct) }}
                  >
                    {pct}% match
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
