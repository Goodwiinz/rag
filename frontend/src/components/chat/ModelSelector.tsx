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
    id: 'gpt-4o',
    name: 'GPT-4O',
    description:
      'OpenAI flagship model with superior reasoning and multimodal capabilities',
    size: 'Cloud',
    parameters: 'Cloud API',
    ram: 'N/A',
    speed: 'Fast',
    accuracy: 97,
    features: [
      'Advanced Reasoning',
      'Code Generation',
      'Multimodal',
      'Function Calling',
    ],
    tags: ['openai', 'cloud', 'flagship'],
    isRecommended: true,
    isFeatured: true,
    isCloud: true,
    provider: 'openai',
    benchmarks: { reasoning: 96, coding: 95, math: 94, language: 97 },
  },
  {
    id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC',
    name: 'LLAMA-3.2-1B',
    description: 'Ultra-efficient neural core for rapid transmissions',
    size: '1B',
    parameters: '1.2B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 78,
    features: ['Text Synthesis', 'Query Processing', 'Compression'],
    tags: ['lightweight', 'fast', 'efficient'],
    isRecommended: true,
    benchmarks: { reasoning: 72, coding: 65, math: 70, language: 82 },
  },
  {
    id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC',
    name: 'LLAMA-3.2-3B',
    description: 'Balanced neural architecture for complex reasoning',
    size: '3B',
    parameters: '3.2B',
    ram: '~4GB',
    speed: 'Fast',
    accuracy: 84,
    features: ['Deep Reasoning', 'Code Generation', 'Analysis'],
    tags: ['balanced', 'versatile', 'flagship'],
    isRecommended: true,
    isFeatured: true,
    benchmarks: { reasoning: 81, coding: 78, math: 79, language: 88 },
  },
  {
    id: 'gemma-2-2b-it-q4f16_1-MLC',
    name: 'GEMMA-2-2B',
    description: 'Google neural matrix with multilingual protocols',
    size: '2B',
    parameters: '2.6B',
    ram: '~3GB',
    speed: 'Fast',
    accuracy: 82,
    features: ['Multilingual', 'Code Analysis', 'Translation'],
    tags: ['multilingual', 'google', 'efficient'],
    benchmarks: { reasoning: 79, coding: 80, math: 76, language: 91 },
  },
  {
    id: 'Phi-3.5-mini-instruct-q4f16_1-MLC',
    name: 'PHI-3.5-MINI',
    description: 'Microsoft compact core optimized for instruction parsing',
    size: '3.8B',
    parameters: '3.8B',
    ram: '~4GB',
    speed: 'Medium',
    accuracy: 86,
    features: ['Instruction Parsing', 'Reasoning Engine', 'Code Synthesis'],
    tags: ['microsoft', 'instruction-tuned', 'reliable'],
    benchmarks: { reasoning: 85, coding: 83, math: 82, language: 87 },
  },
  {
    id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC',
    name: 'QWEN2-1.5B',
    description: 'Alibaba neural core with bilingual transmission',
    size: '1.5B',
    parameters: '1.5B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 80,
    features: ['Bilingual', 'Fast Processing', 'Query Response'],
    tags: ['lightweight', 'bilingual', 'alibaba'],
    isRecommended: true,
    benchmarks: { reasoning: 76, coding: 71, math: 74, language: 86 },
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
          'flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-200',
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
            'w-3.5 h-3.5 transition-colors',
            isOpen
              ? 'text-[var(--phosphor-green)] animate-pulse'
              : 'text-[var(--phosphor-green)]'
          )}
        />
        <span className="text-[var(--terminal-text)] text-xs">
          {selectedModel?.name || 'SELECT MODEL'}
        </span>
        {selectedModel?.isCloud && (
          <span className="px-1 py-0.5 rounded bg-[var(--amber-gold)]/20 text-[var(--amber-gold)] text-[8px] uppercase">
            Cloud
          </span>
        )}
        <ChevronDown
          className={cn(
            'w-3 h-3 text-[var(--terminal-text-muted)] transition-transform',
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
