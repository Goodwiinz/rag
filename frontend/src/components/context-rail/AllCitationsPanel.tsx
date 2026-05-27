'use client';

import { BookOpen, FileText } from 'lucide-react';
import { useCitationsForThread } from '@/hooks';
import { CollapsibleCard } from './CollapsibleCard';

export function AllCitationsPanel() {
  const { allCitations } = useCitationsForThread();

  if (allCitations.length === 0) return null;

  return (
    <CollapsibleCard
      title="Citations"
      badge={`${allCitations.length} source${allCitations.length === 1 ? '' : 's'}`}
    >
      <ul className="space-y-1">
        {allCitations.map((c, idx) => {
          const external = !c.documentId;
          const Icon = external ? BookOpen : FileText;
          return (
            <li
              key={c.id || c.documentId || c.externalReferenceId || idx}
              className="flex items-start gap-3 py-1.5"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              <Icon
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{
                  color: external ? 'var(--nous-corona)' : 'var(--nous-sol)',
                }}
              />
              <div className="flex-1 min-w-0">
                <p
                  className="text-[14px] truncate"
                  style={{ color: 'var(--nous-fg-1)' }}
                  title={c.title}
                >
                  {c.title || 'Untitled source'}
                </p>
                {c.source && (
                  <p
                    className="text-[12px] mt-0.5"
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
    </CollapsibleCard>
  );
}
