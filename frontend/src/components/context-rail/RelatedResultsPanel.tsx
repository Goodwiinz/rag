'use client';

import { FileText } from 'lucide-react';
import { useCitationsForThread } from '@/hooks';
import { CollapsibleCard } from './CollapsibleCard';

function scoreColor(percent: number): string {
  if (percent >= 70) return 'var(--nous-terra)';
  if (percent >= 50) return 'var(--nous-corona)';
  return 'var(--nous-fg-3)';
}

export function RelatedResultsPanel() {
  const { relatedResults } = useCitationsForThread();

  if (relatedResults.length === 0) return null;

  return (
    <CollapsibleCard title="Related results">
      <ul className="space-y-1">
        {relatedResults.map((doc, idx) => {
          const pct = doc.score ? Math.round(doc.score * 100) : 0;
          return (
            <li
              key={doc.documentId || doc.externalReferenceId || idx}
              className="flex items-start gap-3 py-1.5"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              <FileText
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{ color: 'var(--nous-sol)' }}
              />
              <div className="flex-1 min-w-0">
                <p
                  className="text-[14px] truncate"
                  style={{ color: 'var(--nous-fg-1)' }}
                  title={doc.title}
                >
                  {doc.title || 'Untitled document'}
                </p>
                <p
                  className="text-[12px] mt-0.5"
                  style={{ color: scoreColor(pct) }}
                >
                  {pct}% match
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </CollapsibleCard>
  );
}
