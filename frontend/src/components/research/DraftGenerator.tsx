'use client';

/**
 * DraftGenerator Component
 * Form for configuring and generating literature review drafts
 */

import React, { useState, useId, useRef } from 'react';
import { Sparkles, Plus, X, Loader2 } from 'lucide-react';

export interface DraftGeneratorProps {
  onGenerate: (config: GenerationConfig) => void;
  loading?: boolean;
  documentCount?: number;
}

export interface GenerationConfig {
  themes: string[];
  style: 'academic' | 'technical' | 'summary';
  maxSections: number;
  includeAbstract: boolean;
}

export const DraftGenerator: React.FC<DraftGeneratorProps> = ({
  onGenerate,
  loading = false,
  documentCount = 0,
}) => {
  const [themes, setThemes] = useState<string[]>([]);
  const [themeInput, setThemeInput] = useState('');
  const [style, setStyle] = useState<GenerationConfig['style']>('academic');
  const [maxSections, setMaxSections] = useState(5);
  const [includeAbstract, setIncludeAbstract] = useState(true);

  // Refs for managing focus in the radio group
  const styleButtonsRef = useRef<(HTMLButtonElement | null)[]>([]);

  // Generate unique IDs for accessibility
  const themesInputId = useId();
  const maxSectionsId = useId();
  const includeAbstractId = useId();
  const writingStyleLabelId = useId();

  const handleAddTheme = (): void => {
    const trimmed = themeInput.trim();
    if (trimmed && !themes.includes(trimmed)) {
      setThemes([...themes, trimmed]);
      setThemeInput('');
    }
  };

  const handleRemoveTheme = (theme: string): void => {
    setThemes(themes.filter((t) => t !== theme));
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTheme();
    }
  };

  const handleStyleKeyDown = (e: React.KeyboardEvent, index: number) => {
    const styles = ['academic', 'technical', 'summary'] as const;
    let nextIndex = index;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (index + 1) % styles.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (index - 1 + styles.length) % styles.length;
    }

    if (nextIndex !== index) {
      setStyle(styles[nextIndex]);
      styleButtonsRef.current[nextIndex]?.focus();
    }
  };

  const handleGenerate = (): void => {
    if (themes.length === 0) return;
    onGenerate({
      themes,
      style,
      maxSections,
      includeAbstract,
    });
  };

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-6">
      <div className="flex items-center gap-2 mb-6">
        <Sparkles className="h-5 w-5 text-[#ffb700]" />
        <h3 className="font-mono font-bold text-gray-200">Generate Literature Review</h3>
      </div>

      <div className="space-y-5">
        {/* Themes Input */}
        <div>
          <label
            htmlFor={themesInputId}
            className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2"
          >
            Themes / Topics *
          </label>
          <div className="flex gap-2 mb-2">
            <input
              id={themesInputId}
              type="text"
              value={themeInput}
              onChange={(e) => setThemeInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter a theme and press Enter..."
              className="flex-1 px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f]"
            />
            <button
              type="button"
              onClick={handleAddTheme}
              disabled={!themeInput.trim()}
              aria-label="Add theme"
              className="px-3 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          {themes.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {themes.map((theme, idx) => (
                <span
                  key={idx}
                  className="flex items-center gap-1 px-2 py-1 bg-[#00ff9f]/10 text-[#00ff9f] text-xs font-mono rounded"
                >
                  {theme}
                  <button
                    onClick={() => handleRemoveTheme(theme)}
                    aria-label={`Remove theme ${theme}`}
                    className="hover:text-red-400 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          {themes.length === 0 && (
            <p className="text-xs text-gray-500 font-mono">
              Add at least one theme for the review
            </p>
          )}
        </div>

        {/* Style Selector */}
        <div role="radiogroup" aria-labelledby={writingStyleLabelId}>
          <label
            id={writingStyleLabelId}
            className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2"
          >
            Writing Style
          </label>
          <div className="flex gap-2">
            {(['academic', 'technical', 'summary'] as const).map((s, index) => (
              <button
                key={s}
                ref={(el) => {
                  styleButtonsRef.current[index] = el;
                }}
                role="radio"
                aria-checked={style === s}
                tabIndex={style === s ? 0 : -1}
                onClick={() => setStyle(s)}
                onKeyDown={(e) => handleStyleKeyDown(e, index)}
                className={`flex-1 px-3 py-2 rounded text-sm font-mono transition-colors ${
                  style === s
                    ? 'bg-[#00ff9f]/20 text-[#00ff9f] border border-[#00ff9f]/50'
                    : 'bg-[#1a1a1a] text-gray-400 border border-[#333] hover:border-[#555]'
                }`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Max Sections Slider */}
        <div>
          <label
            htmlFor={maxSectionsId}
            className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2"
          >
            Max Sections: <span className="text-[#00ff9f]">{maxSections}</span>
          </label>
          <input
            id={maxSectionsId}
            type="range"
            min={2}
            max={10}
            value={maxSections}
            onChange={(e) => setMaxSections(parseInt(e.target.value, 10))}
            className="w-full h-1 bg-[#333] rounded-lg appearance-none cursor-pointer accent-[#00ff9f]"
          />
          <div className="flex justify-between text-xs text-gray-500 font-mono mt-1">
            <span>2</span>
            <span>6</span>
            <span>10</span>
          </div>
        </div>

        {/* Include Abstract Toggle */}
        <div className="flex items-center justify-between">
          <label
            id={includeAbstractId}
            className="text-xs text-gray-500 font-mono uppercase tracking-wide"
          >
            Include Abstract
          </label>
          <button
            role="switch"
            aria-checked={includeAbstract}
            aria-labelledby={includeAbstractId}
            onClick={() => setIncludeAbstract(!includeAbstract)}
            className={`relative w-12 h-6 rounded-full transition-colors ${
              includeAbstract
                ? 'bg-[#00ff9f]/30 border-[#00ff9f]'
                : 'bg-[#333] border-[#555]'
            } border`}
          >
            <span
              className={`absolute top-0.5 w-5 h-5 rounded-full transition-transform ${
                includeAbstract
                  ? 'translate-x-6 bg-[#00ff9f]'
                  : 'translate-x-0.5 bg-gray-500'
              }`}
            />
          </button>
        </div>

        {/* Document Count Info */}
        {documentCount > 0 && (
          <div className="p-3 bg-[#1a1a1a] rounded text-xs font-mono text-gray-400">
            The review will analyze {documentCount} document{documentCount !== 1 ? 's' : ''} from this project.
          </div>
        )}

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={themes.length === 0 || loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#ffb700]/10 text-[#ffb700] border border-[#ffb700]/30 rounded font-mono text-sm hover:bg-[#ffb700]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate Literature Review
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default DraftGenerator;
