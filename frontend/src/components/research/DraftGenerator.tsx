'use client';

/**
 * DraftGenerator Component
 * Form for configuring and generating literature review drafts
 */

import React, { useState, useId, useRef } from 'react';
import { Sparkles, Plus, X, Loader2 } from 'lucide-react';
import { Switch } from '@/components/ui/switch';

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

const styleOptions = ['academic', 'technical', 'summary'] as const;

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

  const themesInputId = useId();
  const maxSectionsId = useId();
  const includeAbstractId = useId();
  const styleButtonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleStyleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = -1;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIndex = (index + 1) % styleOptions.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIndex = (index - 1 + styleOptions.length) % styleOptions.length;
    }

    if (nextIndex !== -1) {
      e.preventDefault();
      const newStyle = styleOptions[nextIndex];
      setStyle(newStyle);
      styleButtonRefs.current[nextIndex]?.focus();
    }
  };

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
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-2 mb-6">
        <Sparkles className="h-5 w-5 text-primary" />
        <h3 className="text-base font-semibold text-foreground">
          Generate literature review
        </h3>
      </div>

      <div className="space-y-5">
        {/* Themes Input */}
        <div>
          <label
            htmlFor={themesInputId}
            className="block text-sm font-medium text-foreground mb-2"
          >
            Themes
          </label>
          <div className="flex gap-2 mb-2">
            <input
              id={themesInputId}
              type="text"
              value={themeInput}
              onChange={(e) => setThemeInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter a theme and press Enter…"
              className="flex-1 px-3 py-2 bg-muted border border-border rounded text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
            <button
              type="button"
              onClick={handleAddTheme}
              disabled={!themeInput.trim()}
              aria-label="Add theme"
              className="px-3 py-2 bg-primary/10 text-primary border border-primary/30 rounded text-sm hover:bg-primary/20 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          {themes.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {themes.map((theme, idx) => (
                <span
                  key={idx}
                  className="flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary text-xs rounded"
                >
                  {theme}
                  <button
                    onClick={() => handleRemoveTheme(theme)}
                    aria-label={`Remove theme ${theme}`}
                    className="p-0.5 hover:text-destructive transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          {themes.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Add at least one theme for the review
            </p>
          )}
        </div>

        {/* Style Selector */}
        <fieldset className="border-0 p-0 m-0">
          <legend className="block text-sm font-medium text-foreground mb-2">
            Writing style
          </legend>
          <div className="flex gap-2" role="radiogroup" aria-label="Writing style">
            {styleOptions.map((s, idx) => (
              <button
                key={s}
                ref={(el) => {
                  styleButtonRefs.current[idx] = el;
                }}
                role="radio"
                aria-checked={style === s}
                tabIndex={style === s ? 0 : -1}
                onClick={() => setStyle(s)}
                onKeyDown={(e) => handleStyleKeyDown(e, idx)}
                className={`flex-1 px-3 py-2 rounded text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                  style === s
                    ? 'bg-primary/20 text-primary border border-primary/50'
                    : 'bg-muted text-muted-foreground border border-border hover:border-muted-foreground/50'
                }`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </fieldset>

        {/* Max Sections Slider */}
        <div>
          <label
            htmlFor={maxSectionsId}
            className="block text-sm font-medium text-foreground mb-2"
          >
            Max sections: <span className="text-primary">{maxSections}</span>
          </label>
          <input
            id={maxSectionsId}
            type="range"
            min={2}
            max={10}
            value={maxSections}
            onChange={(e) => setMaxSections(parseInt(e.target.value, 10))}
            className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>2</span>
            <span>6</span>
            <span>10</span>
          </div>
        </div>

        {/* Include Abstract Toggle */}
        <div className="flex items-center justify-between">
          <label
            id={includeAbstractId}
            htmlFor={`${includeAbstractId}-switch`}
            className="text-sm font-medium text-foreground"
          >
            Include abstract
          </label>
          <Switch
            id={`${includeAbstractId}-switch`}
            checked={includeAbstract}
            onCheckedChange={setIncludeAbstract}
            aria-labelledby={includeAbstractId}
          />
        </div>

        {/* Document Count Info */}
        {documentCount > 0 && (
          <div className="p-3 bg-muted rounded text-xs text-muted-foreground">
            The review will analyze {documentCount} document
            {documentCount !== 1 ? 's' : ''} from this project.
          </div>
        )}

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={themes.length === 0 || loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary/10 text-primary border border-primary/30 rounded text-sm font-medium hover:bg-primary/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate literature review
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default DraftGenerator;
