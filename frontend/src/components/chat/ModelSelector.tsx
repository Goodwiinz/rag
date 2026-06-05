'use client';

import { cn } from '@/lib/utils';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ChevronDown, Cpu } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

export interface Model {
  id: string;
  name: string;
  description: string;
  size: string;
  parameters: string;
  ram: string;
  speed: 'Very Fast' | 'Fast' | 'Medium' | 'Slow';
  accuracy: number;
  features: string[];
  tags: string[];
  isRecommended?: boolean;
  isFeatured?: boolean;
  benchmarks?: {
    reasoning: number;
    coding: number;
    math: number;
    language: number;
  };
}

export interface ExtendedModel extends Model {
  isCloud?: boolean;
  provider?: 'openai' | 'local';
}

export const AVAILABLE_MODELS: ExtendedModel[] = [
  {
    id: '',
    name: 'AUTO',
    description: 'Use the deployment configured server-side.',
    size: 'Cloud',
    parameters: 'Server default',
    ram: 'N/A',
    speed: 'Fast',
    accuracy: 0,
    features: ['Server default'],
    tags: ['default'],
    isCloud: true,
    provider: 'openai',
  },
  {
    id: 'model-router',
    name: 'MODEL ROUTER',
    description:
      'Azure model-router selects the underlying model (gpt-5, Claude, Llama, …) per request.',
    size: 'Cloud',
    parameters: 'Auto-routed',
    ram: 'N/A',
    speed: 'Fast',
    accuracy: 0,
    features: ['Auto Routing', 'Multi-Provider', 'Function Calling'],
    tags: ['azure', 'cloud', 'router'],
    isRecommended: true,
    isFeatured: true,
    isCloud: true,
    provider: 'openai',
  },
];

interface ModelSelectorProps {
  models: ExtendedModel[];
  selectedModelId?: string;
  onModelChange: (id: string) => void;
  isLoading?: boolean;
}

export function ModelSelector({
  models,
  selectedModelId,
  onModelChange,
  isLoading,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const selectedModel = models.find((m) => m.id === selectedModelId);
  const reduce = useReducedMotion();

  // Keep the portal mounted across open/close so AnimatePresence sees the exit;
  // also guards createPortal against SSR (no document).
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Roving keyboard selection.
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropdownPos({ top: rect.top - 8, left: rect.left });
      const sel = models.findIndex((m) => m.id === selectedModelId);
      setHighlightedIndex(sel >= 0 ? sel : 0);
    }
  }, [isOpen, models, selectedModelId]);

  useEffect(() => {
    if (isOpen) optionRefs.current[highlightedIndex]?.focus();
  }, [isOpen, highlightedIndex]);

  const closeAndRefocus = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const onListKeyDown = (e: React.KeyboardEvent) => {
    const n = models.length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((i) => (i + 1) % n);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((i) => (i - 1 + n) % n);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setHighlightedIndex(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setHighlightedIndex(n - 1);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeAndRefocus();
    }
  };

  const dropdown = mounted
    ? createPortal(
        <AnimatePresence>
          {isOpen && (
            <motion.div
              key="model-selector-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[9998]"
              onClick={() => setIsOpen(false)}
            />
          )}
          {isOpen && (
            <motion.div
              key="model-selector-dropdown"
              role="listbox"
              id="model-selector-listbox"
              aria-label="Select model"
              onKeyDown={onListKeyDown}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
              className="fixed w-80 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-xl z-[9999]"
              style={{
                top: dropdownPos.top,
                left: dropdownPos.left,
                transform: 'translateY(-100%)',
              }}
            >
              <div className="p-2 max-h-80 overflow-y-auto nous-scrollbar">
                {models.map((model, idx) => (
                  <button
                    key={model.id || model.name}
                    ref={(el) => {
                      optionRefs.current[idx] = el;
                    }}
                    role="option"
                    aria-selected={model.id === selectedModelId}
                    onClick={() => {
                      onModelChange(model.id);
                      closeAndRefocus();
                    }}
                    className={cn(
                      'w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-colors outline-none',
                      model.id === selectedModelId
                        ? 'bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/30'
                        : 'hover:bg-[var(--nous-sol)]/5',
                      idx === highlightedIndex &&
                        'ring-1 ring-[var(--nous-sol)]/40'
                    )}
                  >
                    <Cpu
                      className={cn(
                        'w-4 h-4 mt-0.5',
                        model.id === selectedModelId
                          ? 'text-[var(--nous-sol)]'
                          : 'text-[var(--nous-fg-3)]'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'text-xs font-medium font-nous-mono',
                            model.id === selectedModelId
                              ? 'text-[var(--nous-sol)]'
                              : 'text-[var(--nous-fg-1)]'
                          )}
                        >
                          {model.name}
                        </span>
                        {model.isCloud && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--nous-sol)]/20 text-[var(--nous-sol)] text-[8px] uppercase">
                            Cloud
                          </span>
                        )}
                        {model.isFeatured && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--nous-sol)]/20 text-[var(--nous-sol)] text-[8px] uppercase">
                            Featured
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-[var(--nous-fg-3)] mt-0.5 font-nous-mono">
                        {model.description}
                      </p>
                      <div className="flex items-center gap-3 mt-1 text-[10px] text-[var(--nous-fg-3)] font-nous-mono">
                        <span>PARAMS: {model.parameters}</span>
                        <span>RAM: {model.ram}</span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )
    : null;

  return (
    <div>
      <button
        ref={triggerRef}
        onClick={() => !isLoading && setIsOpen(!isOpen)}
        onKeyDown={(e) => {
          if (!isLoading && !isOpen && e.key === 'ArrowDown') {
            e.preventDefault();
            setIsOpen(true);
          }
        }}
        disabled={isLoading}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls="model-selector-listbox"
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-200 whitespace-nowrap font-nous-mono',
          'bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]',
          'hover:border-[var(--nous-sol)]/30',
          'active:scale-[0.98]',
          isOpen && 'border-[var(--nous-sol)]/50 bg-[var(--nous-sol)]/5',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
      >
        <Cpu
          className={cn(
            'w-3.5 h-3.5 shrink-0 transition-colors text-[var(--nous-sol)]',
            isOpen && 'animate-pulse'
          )}
        />
        <span className="text-[var(--nous-fg-1)] text-xs">
          {selectedModel?.name || 'SELECT MODEL'}
        </span>
        {selectedModel?.isCloud && (
          <span className="px-1 py-0.5 rounded bg-[var(--nous-sol)]/20 text-[var(--nous-sol)] text-[8px] uppercase shrink-0">
            Cloud
          </span>
        )}
        <ChevronDown
          className={cn(
            'w-3 h-3 shrink-0 text-[var(--nous-fg-3)] transition-transform',
            isOpen && 'rotate-180'
          )}
        />
      </button>
      {dropdown}
    </div>
  );
}

export default ModelSelector;
