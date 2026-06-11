'use client';

import React from 'react';

interface DocumentMetadataTabProps {
  metadata: Record<string, unknown>;
}

export function DocumentMetadataTab({ metadata }: DocumentMetadataTabProps) {
  return (
    <div className="py-6">
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <table className="w-full text-sm text-left">
          <thead className="bg-muted/30 text-xs text-muted-foreground border-b border-border">
            <tr>
              <th className="px-6 py-3 font-medium">Property</th>
              <th className="px-6 py-3 font-medium">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-sm">
            {Object.entries(metadata || {}).map(([key, value]) => (
              <tr key={key} className="hover:bg-muted/30 transition-colors">
                <td className="px-6 py-3 font-medium text-foreground align-top">{key}</td>
                <td className="px-6 py-3 text-muted-foreground break-words">
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </td>
              </tr>
            ))}
            {(!metadata || Object.keys(metadata).length === 0) && (
              <tr>
                <td colSpan={2} className="px-6 py-10 text-center text-sm text-muted-foreground">
                  No metadata extracted yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
