"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, CornerDownLeft } from "lucide-react";
import { useRouter } from "next/navigation";

interface QuickSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

export const QuickSearch: React.FC<QuickSearchProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState("");
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
        setQuery("");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const runSearch = () => {
    const q = query.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
    onClose();
    setQuery("");
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
            role="dialog"
            aria-modal="true"
            aria-label="Quick search"
            className="fixed top-20 left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl"
          >
            <div className="relative overflow-hidden rounded-2xl bg-white/95 backdrop-blur-xl border border-amber-200/20 shadow-2xl">
              <div className="absolute inset-0 bg-gradient-to-br from-amber-50/50 to-orange-50/30" />
              <div className="relative">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    runSearch();
                  }}
                  className="p-4 border-b border-gray-200/50"
                >
                  <div className="relative">
                    <Search
                      aria-hidden="true"
                      className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400"
                    />
                    <input
                      ref={inputRef}
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search all documents…"
                      aria-label="Search query"
                      className="w-full pl-10 pr-16 py-3 bg-white/50 border border-gray-200/50 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50 transition-all"
                    />
                    <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-1 text-xs font-mono rounded-md bg-gray-100 border border-gray-200">
                      ESC
                    </kbd>
                  </div>
                </form>

                <div className="p-2">
                  {query.trim() ? (
                    <button
                      type="button"
                      onClick={runSearch}
                      className="w-full p-3 rounded-xl hover:bg-white/50 transition-colors group text-left flex items-center gap-3"
                    >
                      <div className="p-2 rounded-lg bg-gray-100/50 group-hover:bg-gray-100 transition-colors">
                        <Search
                          aria-hidden="true"
                          className="h-4 w-4 text-amber-600"
                        />
                      </div>
                      <span className="flex-1 min-w-0 truncate font-medium text-gray-800">
                        Search documents for “{query.trim()}”
                      </span>
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <CornerDownLeft aria-hidden="true" className="h-3 w-3" />
                        Enter
                      </span>
                    </button>
                  ) : (
                    <p className="p-6 text-center text-sm text-gray-500">
                      Type a query and press Enter to search across your
                      documents.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
