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
import { THEME } from '@/theme/constants';
import { Citation, getCitationIdentifier } from '@/utils/citationParser';
import { CitationPreview } from './CitationPreview';

// Terminal Observatory theme colors
// Using THEME.colors instead of local constants

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
 * Terminal Observatory themed
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
            'w-[400px] max-w-[90vw]',
            'bg-[#050505] border-l border-[#1a1a1a]',
            'flex flex-col',
            className
          )}
          style={{
            boxShadow: `-20px 0 60px rgba(0, 255, 159, 0.03)`
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a1a]"
            style={{ backgroundColor: '#0a0a0a' }}
          >
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5" style={{ color: THEME.colors.primary }} />
              <h2 className="text-sm font-medium" style={{ color: THEME.colors.primary }}>
                Sources
              </h2>
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 h-5 border-0"
                style={{
                  backgroundColor: `${THEME.colors.primary}15`,
                  color: THEME.colors.primary
                }}
              >
                {citations.length}
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 w-8 p-0 text-gray-500 hover:text-white hover:bg-[#1a1a1a]"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* Search and Sort */}
          <div className="px-4 py-3 border-b border-[#1a1a1a] space-y-3" style={{ backgroundColor: '#080808' }}>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600" />
              <Input
                type="text"
                placeholder="Search sources..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={cn(
                  'pl-9 h-9 text-sm font-mono',
                  'bg-[#0a0a0a] border-[#1a1a1a]',
                  'text-gray-300 placeholder:text-gray-600',
                  'focus:border-primary/30 focus:ring-primary/10'
                )}
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[10px] text-gray-600 font-mono">
                {filteredCitations.length} of {citations.length} sources
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleSort}
                className="h-7 text-[10px] text-gray-500 hover:text-white hover:bg-[#1a1a1a] font-mono"
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
          <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin scrollbar-thumb-[#1a1a1a] scrollbar-track-transparent">
            {filteredCitations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-center">
                <FileText className="w-10 h-10 text-gray-700 mb-2" />
                <p className="text-xs text-gray-600 font-mono">
                  {searchQuery ? 'No sources match your search' : 'No sources available'}
                </p>
              </div>
            ) : (
              filteredCitations.map((citation, index) => {
                const citationId = getCitationIdentifier(citation);
                return (
                  <CitationPreview
                    key={`${citationId}-${index}`}
                    citation={citation}
                    isExpanded={expandedCitationId === citationId}
                    onToggle={() => handleCitationToggle(citationId)}
                    onNavigate={onCitationClick}
                    className={cn(
                      activeCitationId === citationId &&
                        'ring-1 ring-primary/50'
                    )}
                  />
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2.5 border-t border-[#1a1a1a]" style={{ backgroundColor: '#050505' }}>
            <p
              className="text-[9px] text-center font-mono uppercase tracking-widest"
              style={{ color: `${THEME.colors.primary}40` }}
            >
              Sources Retrieved via RAG Pipeline
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default CitationPanel;
