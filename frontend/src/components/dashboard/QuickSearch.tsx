'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  FileText,
  Image,
  Video,
  Music,
  Clock,
  TrendingUp,
} from 'lucide-react';
import { useRouter } from 'next/navigation';

interface QuickSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SearchResult {
  id: string;
  title: string;
  type: 'document' | 'image' | 'video' | 'audio';
  url: string;
  lastViewed: string;
  popularity: number;
}

const mockSearchResults: SearchResult[] = [
  {
    id: '1',
    title: 'Q4 Financial Report 2024',
    type: 'document',
    url: '/documents/1',
    lastViewed: '2 hours ago',
    popularity: 95,
  },
  {
    id: '2',
    title: 'Product Demo Video',
    type: 'video',
    url: '/documents/2',
    lastViewed: '1 day ago',
    popularity: 87,
  },
  {
    id: '3',
    title: 'Team Meeting Notes',
    type: 'document',
    url: '/documents/3',
    lastViewed: '3 hours ago',
    popularity: 76,
  },
  {
    id: '4',
    title: 'Design Mockups',
    type: 'image',
    url: '/documents/4',
    lastViewed: '1 week ago',
    popularity: 65,
  },
];

export const QuickSearch: React.FC<QuickSearchProps> = ({
  isOpen,
  onClose,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>(mockSearchResults);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (!isOpen) {
          onClose();
        }
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
        setQuery('');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (query.trim() === '') {
      setResults(mockSearchResults);
    } else {
      const filtered = mockSearchResults.filter((result) =>
        result.title.toLowerCase().includes(query.toLowerCase())
      );
      setResults(filtered);
    }
  }, [query]);

  const getTypeIcon = (type: SearchResult['type']) => {
    switch (type) {
      case 'document':
        return <FileText className="h-4 w-4 text-blue-500" />;
      case 'image':
        return <Image className="h-4 w-4 text-green-500" />;
      case 'video':
        return <Video className="h-4 w-4 text-purple-500" />;
      case 'audio':
        return <Music className="h-4 w-4 text-orange-500" />;
    }
  };

  const handleResultClick = (url: string) => {
    router.push(url);
    onClose();
    setQuery('');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.2 }}
            className="fixed top-20 left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl"
          >
            <div className="relative overflow-hidden rounded-2xl bg-white/95 backdrop-blur-xl border border-amber-200/20 shadow-2xl">
              <div className="absolute inset-0 bg-gradient-to-br from-amber-50/50 to-orange-50/30" />
              <div className="relative">
                <div className="p-4 border-b border-border/50">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <input
                      ref={inputRef}
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search documents, images, videos..."
                      className="w-full pl-10 pr-4 py-3 bg-white/50 border border-border/50 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50 transition-all"
                    />
                    <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-1 text-xs font-mono rounded-md bg-gray-100 border border-border">
                      ESC
                    </kbd>
                  </div>
                </div>

                <div className="max-h-96 overflow-y-auto">
                  <AnimatePresence mode="wait">
                    {results.length > 0 ? (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="p-2"
                      >
                        {results.map((result, index) => (
                          <motion.button
                            key={result.id}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            onClick={() => handleResultClick(result.url)}
                            className="w-full p-3 rounded-xl hover:bg-white/50 transition-colors group text-left"
                          >
                            <div className="flex items-center gap-3">
                              <div className="p-2 rounded-lg bg-gray-100/50 group-hover:bg-gray-100 transition-colors">
                                {getTypeIcon(result.type)}
                              </div>
                              <div className="flex-1 min-w-0">
                                <h3 className="font-medium text-foreground truncate">
                                  {result.title}
                                </h3>
                                <div className="flex items-center gap-3 mt-1">
                                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <Clock className="h-3 w-3" />
                                    {result.lastViewed}
                                  </span>
                                  {result.popularity > 80 && (
                                    <span className="flex items-center gap-1 text-xs text-amber-600">
                                      <TrendingUp className="h-3 w-3" />
                                      Popular
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </motion.button>
                        ))}
                      </motion.div>
                    ) : (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="p-8 text-center"
                      >
                        <div className="text-muted-foreground mb-2">
                          <Search className="h-12 w-12 mx-auto" />
                        </div>
                        <p className="text-muted-foreground">
                          No results found
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                          Try adjusting your search terms
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
