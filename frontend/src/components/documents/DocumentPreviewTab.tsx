'use client';

import React from 'react';
import { Eye } from 'lucide-react';

export function DocumentPreviewTab() {
  return (
    <div className="py-6 flex items-center justify-center min-h-[400px] rounded-xl border border-dashed border-border bg-card/50">
      <div className="text-center">
        <Eye aria-hidden="true" className="w-10 h-10 text-muted-foreground mx-auto mb-4" />
        <p className="text-sm font-medium text-foreground mb-1">Preview not available here</p>
        <p className="text-xs text-muted-foreground mb-4">Open the original file to view its contents.</p>
        <button
          type="button"
          className="px-4 py-2 rounded-lg border border-border bg-card text-sm font-medium text-foreground hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Open original file
        </button>
      </div>
    </div>
  );
}
