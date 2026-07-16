'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Loader2, Search, AlertCircle } from 'lucide-react';
import { citationService } from '@/services/citationService';
import type { CitationResponse } from '@/types/research';
import { cn } from '@/lib/utils';

export interface CitationEditModalProps {
  citation: CitationResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave?: (updatedCitation: Partial<CitationResponse>) => void;
}

/**
 * CitationEditModal Component
 *
 * Modal dialog for editing citation metadata with auto-lookup capability.
 *
 * Features:
 * - Manual editing of all citation fields
 * - Auto-lookup by ArXiv ID or DOI
 * - Loading states during lookup
 * - Validation and error handling
 * - Terminal Observatory theme
 */
export function CitationEditModal({
  citation,
  open,
  onOpenChange,
  onSave,
}: CitationEditModalProps) {
  // Form state
  const [formData, setFormData] = useState<Partial<CitationResponse>>({});
  const [lookupId, setLookupId] = useState('');
  const [lookupType, setLookupType] = useState<'arxiv' | 'doi'>('arxiv');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize form with citation data
  useEffect(() => {
    if (citation) {
      setFormData({
        documentTitle: citation.documentTitle || '',
        authors: citation.authors || [],
        year: citation.year,
        venue: citation.venue || '',
        doi: citation.doi || '',
        arxivId: citation.arxivId || '',
        abstract: citation.abstract || '',
      });
    }
  }, [citation]);

  const handleLookup = async () => {
    if (!lookupId.trim()) {
      setError('Please enter an ArXiv ID or DOI');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params =
        lookupType === 'arxiv'
          ? { arxivId: lookupId.trim() }
          : { doi: lookupId.trim() };

      const result = await citationService.lookupCitation(params);

      // Update form with lookup results
      setFormData({
        documentTitle: result.documentTitle || formData.documentTitle,
        authors: result.authors || formData.authors,
        year: result.year || formData.year,
        venue: result.venue || formData.venue,
        doi: result.doi || formData.doi,
        arxivId: result.arxivId || formData.arxivId,
        abstract: result.abstract || formData.abstract,
      });

      setLookupId('');
    } catch (err) {
      console.error('Lookup failed:', err);
      setError('Failed to fetch citation metadata. Please check the ID and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = () => {
    if (!formData.documentTitle?.trim()) {
      setError('Title is required');
      return;
    }

    onSave?.(formData);
    onOpenChange(false);
  };

  const handleFieldChange = (field: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    setError(null);
  };

  const handleAuthorsChange = (value: string) => {
    // Parse comma-separated authors
    const authors = value
      .split(',')
      .map((a) => a.trim())
      .filter(Boolean);
    handleFieldChange('authors', authors);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-lg text-[var(--nous-fg-1)]">
            Edit Citation
          </DialogTitle>
          <DialogDescription className="font-mono text-sm text-[var(--nous-fg-3)]">
            Manually edit citation metadata or auto-lookup by ArXiv ID/DOI
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Error Display */}
          {error && (
            <div className="p-3 rounded-lg border border-red-500/30 bg-red-500/5 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-xs font-mono text-red-500">{error}</p>
            </div>
          )}

          {/* Auto-Lookup Section */}
          <div className="p-4 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
            <Label className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider mb-3 block">
              Auto-Lookup
            </Label>

            <div className="flex gap-2">
              <div className="flex-1 flex gap-2">
                <select
                  value={lookupType}
                  onChange={(e) => setLookupType(e.target.value as 'arxiv' | 'doi')}
                  className="px-3 py-2 rounded-lg bg-[var(--nous-bg-3)] border border-[var(--nous-border-1)] text-sm font-mono text-[var(--nous-fg-1)] focus:outline-none focus:ring-2 focus:ring-[var(--nous-sol)]/50"
                >
                  <option value="arxiv">ArXiv ID</option>
                  <option value="doi">DOI</option>
                </select>

                <Input
                  placeholder={lookupType === 'arxiv' ? '2101.00001' : '10.1000/xyz123'}
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
                  className="flex-1 bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                  disabled={loading}
                />
              </div>

              <Button
                onClick={handleLookup}
                disabled={loading || !lookupId.trim()}
                className="bg-[var(--nous-sol)] text-[var(--nous-bg-1)] hover:shadow-[0_0_20px_var(--nous-sol-glow)] font-mono text-xs font-bold"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Looking up...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    Lookup
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Manual Edit Form */}
          <div className="space-y-4">
            {/* Title */}
            <div className="space-y-2">
              <Label
                htmlFor="title"
                className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
              >
                Title *
              </Label>
              <Input
                id="title"
                value={formData.documentTitle || ''}
                onChange={(e) => handleFieldChange('documentTitle', e.target.value)}
                className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                placeholder="Paper title"
              />
            </div>

            {/* Authors */}
            <div className="space-y-2">
              <Label
                htmlFor="authors"
                className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
              >
                Authors (comma-separated)
              </Label>
              <Input
                id="authors"
                value={formData.authors?.join(', ') || ''}
                onChange={(e) => handleAuthorsChange(e.target.value)}
                className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                placeholder="John Doe, Jane Smith"
              />
            </div>

            {/* Year and Venue */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label
                  htmlFor="year"
                  className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
                >
                  Year
                </Label>
                <Input
                  id="year"
                  type="number"
                  value={formData.year || ''}
                  onChange={(e) => handleFieldChange('year', parseInt(e.target.value) || null)}
                  className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                  placeholder="2024"
                />
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="venue"
                  className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
                >
                  Venue
                </Label>
                <Input
                  id="venue"
                  value={formData.venue || ''}
                  onChange={(e) => handleFieldChange('venue', e.target.value)}
                  className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                  placeholder="Journal/Conference"
                />
              </div>
            </div>

            {/* ArXiv ID and DOI */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label
                  htmlFor="arxiv"
                  className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
                >
                  ArXiv ID
                </Label>
                <Input
                  id="arxiv"
                  value={formData.arxivId || ''}
                  onChange={(e) => handleFieldChange('arxivId', e.target.value)}
                  className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                  placeholder="2101.00001"
                />
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="doi"
                  className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
                >
                  DOI
                </Label>
                <Input
                  id="doi"
                  value={formData.doi || ''}
                  onChange={(e) => handleFieldChange('doi', e.target.value)}
                  className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm"
                  placeholder="10.1000/xyz123"
                />
              </div>
            </div>

            {/* Abstract */}
            <div className="space-y-2">
              <Label
                htmlFor="abstract"
                className="text-xs font-mono font-medium text-[var(--nous-fg-1)] uppercase tracking-wider"
              >
                Abstract
              </Label>
              <Textarea
                id="abstract"
                value={formData.abstract || ''}
                onChange={(e) => handleFieldChange('abstract', e.target.value)}
                className="bg-[var(--nous-bg-3)] border-[var(--nous-border-1)] font-mono text-sm min-h-[120px]"
                placeholder="Paper abstract..."
              />
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="font-mono text-xs border-[var(--nous-border-1)] text-[var(--nous-fg-3)]"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!formData.documentTitle?.trim()}
            className="bg-[var(--nous-sol)] text-[var(--nous-bg-1)] hover:shadow-[0_0_20px_var(--nous-sol-glow)] font-mono text-xs font-bold"
          >
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
