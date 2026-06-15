'use client';

import React from 'react';
import { FileText, Tag } from 'lucide-react';
import type { Document } from '@/types';

interface DocumentOverviewTabProps {
  document: Document;
}

export function DocumentOverviewTab({ document }: DocumentOverviewTabProps) {
  const summary =
    document.content_summary ||
    document.content_preview ||
    document.description;

  return (
    <div className="py-6">
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h3 className="text-sm font-medium text-foreground mb-4 flex items-center gap-2">
          <FileText
            aria-hidden="true"
            className="w-4 h-4 text-muted-foreground"
          />
          Content summary
        </h3>
        {/* The document's own words are content, not chrome: render at full
            foreground. Only the empty-state fallback recedes to muted. */}
        <p
          className={
            summary
              ? 'text-sm leading-relaxed text-foreground'
              : 'text-sm leading-relaxed text-muted-foreground'
          }
        >
          {summary || 'No summary available for this document yet.'}
        </p>

        {document.tags && document.tags.length > 0 && (
          <div className="mt-6 pt-6 border-t border-border">
            <div className="flex flex-wrap gap-2">
              {document.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-1 rounded bg-muted text-xs text-muted-foreground border border-border inline-flex items-center gap-1.5"
                >
                  <Tag aria-hidden="true" className="w-3 h-3 text-primary" />
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
