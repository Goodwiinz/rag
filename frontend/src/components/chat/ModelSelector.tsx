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

// Only `model-router` is provisioned in the Azure resource. The router
// auto-selects the underlying model (gpt-5, claude-*, llama-*, etc.) per
// request, so we don't expose individual model picks here. Empty `id`
// falls back to the deployment configured server-side via
// AZURE_OPENAI_CHAT_DEPLOYMENT_NAME.
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
          'bg-[var(--terminal-surface)] border-[var(--terminal-border)]',
          'hover:border-[var(--phosphor-green)]/30',
          'active:scale-[0.98]',
          isOpen &&
            'border-[var(--phosphor-green)]/50 bg-[var(--phosphor-green)]/5',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <Cpu
          className={cn(
            'w-3.5 h-3.5 shrink-0 transition-colors',
            isOpen
              ? 'text-[var(--phosphor-green)] animate-pulse'
              : 'text-[var(--phosphor-green)]'
          )}
        />
        <span className="text-[var(--terminal-text)] text-xs">
          {selectedModel?.name || 'SELECT MODEL'}
        </span>
        {selectedModel?.isCloud && (
          <span className="px-1 py-0.5 rounded bg-[var(--amber-gold)]/20 text-[var(--amber-gold)] text-[8px] uppercase shrink-0">
            Cloud
          </span>
        )}
        <ChevronDown
          className={cn(
            'w-3 h-3 shrink-0 text-[var(--terminal-text-muted)] transition-transform',
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
              className="absolute bottom-full left-0 mb-2 w-80 terminal-window z-50"
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
                      'w-full flex items-start gap-3 px-3 py-2.5 rounded text-left transition-colors',
                      model.id === selectedModelId
                        ? 'bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30'
                        : 'hover:bg-[var(--terminal-elevated)]'
                    )}
                  >
                    <Cpu
                      className={cn(
                        'w-4 h-4 mt-0.5',
                        model.id === selectedModelId
                          ? 'text-[var(--phosphor-green)]'
                          : 'text-[var(--terminal-text-muted)]'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'text-xs font-medium',
                            model.id === selectedModelId
                              ? 'text-[var(--phosphor-green)]'
                              : 'text-[var(--terminal-text)]'
                          )}
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}
                        >
                          {model.name}
                        </span>
                        {model.isCloud && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--amber-gold)]/20 text-[var(--amber-gold)] text-[8px] uppercase">
                            Cloud
                          </span>
                        )}
                        {model.isFeatured && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--phosphor-green)]/20 text-[var(--phosphor-green)] text-[8px] uppercase">
                            Featured
                          </span>
                        )}
                      </div>
                      <p
                        className="text-[10px] text-[var(--terminal-text-muted)] mt-0.5"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {model.description}
                      </p>
                      <div
                        className="flex items-center gap-3 mt-1 text-[10px] text-[var(--terminal-text-dim)]"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
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
