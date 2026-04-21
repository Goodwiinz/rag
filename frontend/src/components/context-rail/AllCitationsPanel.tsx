'use client';

import * as React from 'react';
import { BookOpen, FileText } from 'lucide-react';
import { useCitationsForThread } from '@/hooks';

export function AllCitationsPanel() {
  const { allCitations } = useCitationsForThread();

  return (
    <section aria-label="All thread citations">
      <div
        className="flex items-center justify-between mb-2 px-1"
        style={{ fontFamily: 'var(--nous-font-ui)' }}
      >
        <span
          className="text-[10px] uppercase tracking-wider"
          style={{ color: 'var(--nous-fg-3)' }}
        >
          Citations
        </span>
        {allCitations.length > 0 && (
          <span
            className="text-[10px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {allCitations.length} source{allCitations.length === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {allCitations.length === 0 ? (
        <div
          className="rounded-xl border p-4 text-xs"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
            color: 'var(--nous-fg-3)',
            fontFamily: 'var(--nous-font-body)',
          }}
        >
          No citations yet. Citations from every message will collect here.
        </div>
      ) : (
        <ul
          className="rounded-xl border p-2 space-y-1"
          style={{
            borderColor: 'var(--nous-border-1)',
            background: 'var(--nous-bg-2)',
          }}
        >
          {allCitations.map((c, idx) => {
            const external = !c.documentId;
            const Icon = external ? BookOpen : FileText;
            return (
              <li
                key={c.id || c.documentId || c.externalReferenceId || idx}
                className="flex items-start gap-3 px-3 py-2 rounded-lg"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                <Icon
                  className="w-3.5 h-3.5 mt-0.5 shrink-0"
                  style={{
                    color: external
                      ? 'var(--nous-corona)'
                      : 'var(--nous-sol)',
                  }}
                />
                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm truncate"
                    style={{ color: 'var(--nous-fg-1)' }}
                    title={c.title}
                  >
                    {c.title || 'Untitled source'}
                  </p>
                  {c.source && (
                    <p
                      className="text-[11px]"
                      style={{ color: 'var(--nous-fg-3)' }}
                    >
                      {c.source}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
