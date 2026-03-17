'use client';

import React from 'react';
import { AlertTriangle, Check, X } from 'lucide-react';

interface ConfirmationAction {
  name: string;
  args: Record<string, unknown>;
}

interface ConfirmationCardProps {
  tools: ConfirmationAction[];
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  ingest_arxiv_papers: 'Ingest ArXiv Papers',
  add_document_to_project: 'Add Document to Project',
  create_project_note: 'Create Project Note',
  create_draft: 'Generate Draft',
};

export function ConfirmationCard({
  tools,
  message,
  onConfirm,
  onCancel,
  isLoading,
}: ConfirmationCardProps) {
  return (
    <div className="border border-amber-500/30 rounded-lg bg-amber-500/5 text-sm my-2 overflow-hidden">
      <div className="flex items-start gap-2 px-3 py-2.5">
        <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-foreground font-medium text-xs">{message}</p>
          <ul className="mt-1.5 space-y-1">
            {tools.map((tool, i) => (
              <li
                key={i}
                className="text-xs text-muted-foreground flex items-center gap-1.5"
              >
                <span className="w-1 h-1 rounded-full bg-amber-500 shrink-0" />
                <span className="font-medium">
                  {TOOL_LABELS[tool.name] || tool.name}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex items-center gap-2 px-3 py-2 border-t border-amber-500/20">
        <button
          onClick={onConfirm}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          aria-label="Confirm agent action"
        >
          <Check className="h-3 w-3" />
          Confirm
        </button>
        <button
          onClick={onCancel}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border hover:bg-muted disabled:opacity-50 transition-colors"
          aria-label="Cancel agent action"
        >
          <X className="h-3 w-3" />
          Cancel
        </button>
      </div>
    </div>
  );
}
