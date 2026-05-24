'use client';

import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Cpu } from 'lucide-react';
import { useState } from 'react';

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
  const selectedModel = models.find((m) => m.id === selectedModelId);

  return (
    <div className="relative">
      <button
        onClick={() => !isLoading && setIsOpen(!isOpen)}
        disabled={isLoading}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-200 whitespace-nowrap',
          'bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]',
          'hover:border-[var(--nous-sol)]/30',
          'active:scale-[0.98]',
          isOpen &&
            'border-[var(--nous-sol)]/50 bg-[var(--nous-sol)]/5',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
        style={{ fontFamily: 'var(--nous-font-mono)' }}
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

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="absolute bottom-full left-0 mb-2 w-80 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-xl z-50"
            >
              <div className="p-2 max-h-80 overflow-y-auto terminal-scrollbar">
                {models.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => {
                      onModelChange(model.id);
                      setIsOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                      model.id === selectedModelId
                        ? 'bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/30'
                        : 'hover:bg-[var(--nous-sol)]/5'
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
                            'text-xs font-medium',
                            model.id === selectedModelId
                              ? 'text-[var(--nous-sol)]'
                              : 'text-[var(--nous-fg-1)]'
                          )}
                          style={{ fontFamily: 'var(--nous-font-mono)' }}
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
                      <p
                        className="text-[10px] text-[var(--nous-fg-3)] mt-0.5"
                        style={{ fontFamily: 'var(--nous-font-mono)' }}
                      >
                        {model.description}
                      </p>
                      <div
                        className="flex items-center gap-3 mt-1 text-[10px] text-[var(--nous-fg-3)]"
                        style={{ fontFamily: 'var(--nous-font-mono)' }}
                      >
                        <span>PARAMS: {model.parameters}</span>
                        <span>RAM: {model.ram}</span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ModelSelector;
