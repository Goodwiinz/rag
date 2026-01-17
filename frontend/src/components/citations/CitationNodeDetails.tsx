'use client';

/**
 * Citation Node Details Component
 *
 * Displays detailed information about a selected citation node in the graph.
 * Shows metadata, citation counts, and action buttons.
 */

import React from 'react';
import { ExternalLink, Plus, FileText, Copy, X } from 'lucide-react';
import type { GraphNode } from './CitationGraph';

export interface CitationNodeDetailsProps {
  node: GraphNode | null;
  onClose?: () => void;
  onAddToCollection?: (node: GraphNode) => void;
  onViewDocument?: (documentId: string) => void;
}

export const CitationNodeDetails: React.FC<CitationNodeDetailsProps> = ({
  node,
  onClose,
  onAddToCollection,
  onViewDocument,
}) => {
  if (!node) {
    return (
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
        <p className="text-gray-500 font-mono text-sm text-center">
          Click a node to view details
        </p>
      </div>
    );
  }

  const handleCopyDoi = () => {
    if (node.doi) {
      navigator.clipboard.writeText(node.doi);
    }
  };

  const handleCopyArxiv = () => {
    if (node.arxiv_id) {
      navigator.clipboard.writeText(node.arxiv_id);
    }
  };

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-[#1a1a1a]">
        <div className="flex-1 min-w-0">
          <h3 className="font-mono text-[#00ff9f] text-sm font-medium truncate">
            {node.title || 'Untitled'}
          </h3>
          {node.year && (
            <p className="text-xs text-gray-500 mt-1 font-mono">{node.year}</p>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Authors */}
        {node.authors && node.authors.length > 0 && (
          <div>
            <label className="text-xs text-gray-500 font-mono uppercase tracking-wide">
              Authors
            </label>
            <p className="text-sm text-gray-300 font-mono mt-1">
              {node.authors.join(', ')}
            </p>
          </div>
        )}

        {/* Venue */}
        {node.venue && (
          <div>
            <label className="text-xs text-gray-500 font-mono uppercase tracking-wide">
              Venue
            </label>
            <p className="text-sm text-gray-300 font-mono mt-1">{node.venue}</p>
          </div>
        )}

        {/* Citation Stats */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#1a1a1a] rounded p-3">
            <div className="text-2xl font-mono text-[#00ff9f]">
              {node.citation_count || 0}
            </div>
            <div className="text-xs text-gray-500 font-mono">Citations</div>
          </div>
          {node.influence_score !== undefined && (
            <div className="bg-[#1a1a1a] rounded p-3">
              <div className="text-2xl font-mono text-[#ffb700]">
                {node.influence_score.toFixed(1)}
              </div>
              <div className="text-xs text-gray-500 font-mono">Influence</div>
            </div>
          )}
        </div>

        {/* Identifiers */}
        <div className="space-y-2">
          {node.doi && (
            <div className="flex items-center justify-between bg-[#1a1a1a] rounded p-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono">DOI:</span>
                <a
                  href={`https://doi.org/${node.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#00d4ff] font-mono hover:underline flex items-center gap-1"
                >
                  {node.doi}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              <button
                onClick={handleCopyDoi}
                className="p-1 text-gray-500 hover:text-gray-300"
                title="Copy DOI"
              >
                <Copy className="h-3 w-3" />
              </button>
            </div>
          )}

          {node.arxiv_id && (
            <div className="flex items-center justify-between bg-[#1a1a1a] rounded p-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono">arXiv:</span>
                <a
                  href={`https://arxiv.org/abs/${node.arxiv_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#00d4ff] font-mono hover:underline flex items-center gap-1"
                >
                  {node.arxiv_id}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              <button
                onClick={handleCopyArxiv}
                className="p-1 text-gray-500 hover:text-gray-300"
                title="Copy arXiv ID"
              >
                <Copy className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Type Badge */}
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-1 rounded text-xs font-mono ${
              node.is_uploaded !== false
                ? 'bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30'
                : 'bg-[#ffb700]/10 text-[#ffb700] border border-[#ffb700]/30'
            }`}
          >
            {node.is_uploaded !== false ? 'Uploaded Document' : 'External Reference'}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-[#1a1a1a] flex gap-2">
        {node.document_id && onViewDocument && (
          <button
            onClick={() => onViewDocument(node.document_id!)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors"
          >
            <FileText className="h-4 w-4" />
            View Document
          </button>
        )}

        {node.is_uploaded === false && onAddToCollection && (
          <button
            onClick={() => onAddToCollection(node)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-[#ffb700]/10 text-[#ffb700] border border-[#ffb700]/30 rounded font-mono text-sm hover:bg-[#ffb700]/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add to Collection
          </button>
        )}
      </div>
    </div>
  );
};

export default CitationNodeDetails;
