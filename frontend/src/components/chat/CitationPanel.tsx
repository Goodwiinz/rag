'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BookOpen,
  FileText,
  Search,
  SortAsc,
  SortDesc,
  X,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { Citation } from '@/utils/citationParser';
import { CitationPreview } from './CitationPreview';

interface CitationPanelProps {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
  onCitationClick?: (citation: Citation) => void;
  activeCitationId?: string;
  className?: string;
}

type SortBy = 'relevance' | 'title';
type SortOrder = 'asc' | 'desc';

/**
 * Citation panel sidebar component
 * Shows all citations for a message with filtering and sorting
 */
export function CitationPanel({
  citations,
  isOpen,
  onClose,
  onCitationClick,
  activeCitationId,
  className,
}: CitationPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('relevance');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [expandedCitationId, setExpandedCitationId] = useState<string | null>(null);

  // Filter and sort citations
  const filteredCitations = useMemo(() => {
    let result = [...citations];

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.title.toLowerCase().includes(query) ||
          c.content?.toLowerCase().includes(query) ||
          c.source?.toLowerCase().includes(query)
      );
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'relevance') {
        comparison = b.score - a.score;
      } else {
        comparison = a.title.localeCompare(b.title);
      }
      return sortOrder === 'desc' ? comparison : -comparison;
    });

    return result;
  }, [citations, searchQuery, sortBy, sortOrder]);

  const toggleSort = () => {
    if (sortBy === 'relevance') {
      setSortBy('title');
      setSortOrder('asc');
    } else {
      setSortBy('relevance');
      setSortOrder('desc');
    }
  };

  const handleCitationToggle = (citationId: string) => {
    setExpandedCitationId((prev) => (prev === citationId ? null : citationId));
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className={cn(
            'fixed right-0 top-0 bottom-0 z-50',
            'w-96 max-w-[90vw]',
            'bg-[#0a0a0a] border-l border-[#00ff9f]/20',
            'shadow-[-10px_0_30px_rgba(0,255,159,0.05)]',
            'flex flex-col',
            className
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#00ff9f]/10 bg-[#0f0f0f]">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-[#00ff9f]" />
              <h2 className="text-sm font-medium text-white">Sources</h2>
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 h-5 bg-[#00ff9f]/10 text-[#00ff9f] border-[#00ff9f]/20"
              >
                {citations.length}
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 w-8 p-0 text-gray-400 hover:text-white hover:bg-gray-800"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* Search and Sort */}
          <div className="px-4 py-3 border-b border-[#00ff9f]/10 space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <Input
                type="text"
                placeholder="Search sources..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={cn(
                  'pl-9 h-9 text-sm',
                  'bg-[#080808] border-[#1a1a1a]',
                  'text-white placeholder:text-gray-500',
                  'focus:border-[#00ff9f]/30 focus:ring-[#00ff9f]/10'
                )}
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">
                {filteredCitations.length} of {citations.length} sources
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleSort}
                className="h-7 text-xs text-gray-400 hover:text-white"
              >
                {sortBy === 'relevance' ? 'By Relevance' : 'By Title'}
                {sortOrder === 'desc' ? (
                  <SortDesc className="w-3 h-3 ml-1" />
                ) : (
                  <SortAsc className="w-3 h-3 ml-1" />
                )}
              </Button>
            </div>
          </div>

          {/* Citations List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
            {filteredCitations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-center">
                <FileText className="w-10 h-10 text-gray-600 mb-2" />
                <p className="text-sm text-gray-500">
                  {searchQuery ? 'No sources match your search' : 'No sources available'}
                </p>
              </div>
            ) : (
              filteredCitations.map((citation) => (
                <CitationPreview
                  key={citation.documentId}
                  citation={citation}
                  isExpanded={expandedCitationId === citation.documentId}
                  onToggle={() => handleCitationToggle(citation.documentId)}
                  onNavigate={onCitationClick}
                  className={cn(
                    activeCitationId === citation.documentId &&
                      'ring-1 ring-[#00ff9f]/50'
                  )}
                />
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-[#00ff9f]/10 bg-[#080808]">
            <p className="text-[10px] text-gray-600 text-center font-mono">
              SOURCES RETRIEVED VIA RAG PIPELINE
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default CitationPanel;
