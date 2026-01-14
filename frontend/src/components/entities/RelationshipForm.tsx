/**
 * RelationshipForm Component
 * Terminal Observatory themed relationship form
 */

import React, { useState, useEffect } from 'react';
import { Link, Save, X, Search, Terminal, Shield, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Entity, GraphEdge } from '@/types/entity';
import { entityService } from '@/services/entityService';
import { cn } from '@/lib/utils';

interface RelationshipFormProps {
  sourceEntityId?: string;
  initialData?: Partial<GraphEdge>;
  onSubmit: (data: any) => void;
  onCancel: () => void;
  availableTypes?: string[];
}

const DEFAULT_RELATIONSHIP_TYPES = [
  'WORKS_FOR',
  'LOCATED_IN',
  'KNOWS',
  'RELATED_TO',
  'PART_OF',
  'OWNS',
  'CREATED_BY',
  'USES',
  'MANAGES',
  'COLLABORATES_WITH',
  'MEMBER_OF',
  'FOUND_IN',
  'EXAMPLE_OF',
  'CAUSES',
  'ENABLES',
  'REQUIRES',
  'PRECEDES',
  'FOLLOWS'
];

export const RelationshipForm: React.FC<RelationshipFormProps> = ({
  sourceEntityId,
  initialData,
  onSubmit,
  onCancel,
  availableTypes
}) => {
  // Use available types from props or fall back to defaults
  const relationshipTypes = availableTypes || DEFAULT_RELATIONSHIP_TYPES;
  const [formData, setFormData] = useState({
    source_entity_id: sourceEntityId || '',
    target_entity_id: '',
    relationship_type: '',
    strength: 0.8,
    confidence_score: 0.8,
    context: '',
    evidence: [] as string[],
    metadata: {} as Record<string, any>
  });

  const [targetSearchQuery, setTargetSearchQuery] = useState('');
  const [targetSearchResults, setTargetSearchResults] = useState<Entity[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<Entity | null>(null);
  const [newEvidence, setNewEvidence] = useState('');

  useEffect(() => {
    if (initialData) {
      setFormData({
        source_entity_id: initialData.source || '',
        target_entity_id: initialData.target || '',
        relationship_type: initialData.type || '',
        strength: initialData.weight || 0.8,
        confidence_score: initialData.confidence || 0.8,
        context: initialData.context || '',
        evidence: initialData.evidence || [],
        metadata: initialData.metadata || {}
      });
    }
  }, [initialData]);

  const searchTargetEntities = async (query: string) => {
    if (!query) {
      setTargetSearchResults([]);
      return;
    }

    try {
      const results = await entityService.searchEntities(query);
      setTargetSearchResults(results);
    } catch (error) {
      console.error('Error searching entities:', error);
    }
  };

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      searchTargetEntities(targetSearchQuery);
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [targetSearchQuery]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.target_entity_id || !formData.relationship_type) {
      alert('Please select a target entity and relationship type');
      return;
    }

    const data = {
      ...formData,
      evidence: formData.evidence.filter(e => e.trim())
    };

    onSubmit(data);
  };

  const addEvidence = () => {
    if (newEvidence.trim()) {
      setFormData(prev => ({
        ...prev,
        evidence: [...prev.evidence, newEvidence.trim()]
      }));
      setNewEvidence('');
    }
  };

  const removeEvidence = (index: number) => {
    setFormData(prev => ({
      ...prev,
      evidence: prev.evidence.filter((_, i) => i !== index)
    }));
  };

  const selectTargetEntity = (entity: Entity) => {
    setSelectedTarget(entity);
    setFormData(prev => ({
      ...prev,
      target_entity_id: entity.id
    }));
    setTargetSearchQuery('');
    setTargetSearchResults([]);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 text-[var(--terminal-text)]">
      {/* Source Entity */}
      {formData.source_entity_id && (
        <div className="space-y-2">
          <Label className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">Source_Entity_ID</Label>
          <Input 
            value={formData.source_entity_id} 
            disabled 
            className="bg-[var(--terminal-elevated)] border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text-muted)] cursor-not-allowed opacity-70" 
          />
        </div>
      )}

      {/* Target Entity */}
      <div className="space-y-2">
        <Label htmlFor="target" className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">Target_Entity *</Label>
        <div className="space-y-2">
          {selectedTarget ? (
            <div className="flex items-center justify-between p-3 bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] rounded-md">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-[var(--terminal-bg)] border border-[var(--terminal-border)] flex items-center justify-center">
                  <Terminal className="w-4 h-4 text-[var(--cyan)]" />
                </div>
                <div>
                  <p className="font-mono text-sm font-bold text-[var(--terminal-text)]">{selectedTarget.name}</p>
                  <p className="font-mono text-[10px] text-[var(--terminal-text-muted)] uppercase">{selectedTarget.type}</p>
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedTarget(null);
                  setFormData(prev => ({ ...prev, target_entity_id: '' }));
                }}
                className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-red-400 hover:bg-red-400/10"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="relative">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--terminal-text-dim)]" />
                <Input
                  id="target"
                  placeholder="SEARCH_TARGET_ENTITY..."
                  value={targetSearchQuery}
                  onChange={(e) => setTargetSearchQuery(e.target.value)}
                  className="pl-10 bg-[var(--terminal-bg)] border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)] focus:border-[var(--phosphor-green)]"
                />
              </div>
              {targetSearchResults.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-[var(--terminal-surface)] border border-[var(--terminal-border)] rounded-lg shadow-xl max-h-60 overflow-auto terminal-scrollbar">
                  {targetSearchResults.map((entity) => (
                    <button
                      key={entity.id}
                      type="button"
                      className="w-full text-left px-4 py-2 hover:bg-[var(--terminal-elevated)] flex items-center justify-between border-b border-[var(--terminal-border)] last:border-0 group"
                      onClick={() => selectTargetEntity(entity)}
                    >
                      <div>
                        <p className="font-mono text-sm font-bold text-[var(--terminal-text)] group-hover:text-[var(--phosphor-green)] transition-colors">{entity.name}</p>
                        <p className="font-mono text-[10px] text-[var(--terminal-text-muted)] uppercase">{entity.type}</p>
                      </div>
                      <Link className="h-4 w-4 text-[var(--terminal-text-dim)] group-hover:text-[var(--phosphor-green)] transition-colors" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Relationship Type */}
      <div className="space-y-2">
        <Label htmlFor="type" className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">Link_Type *</Label>
        <Select
          value={formData.relationship_type}
          onValueChange={(value) => setFormData(prev => ({ ...prev, relationship_type: value }))}
        >
          <SelectTrigger className="bg-[var(--terminal-bg)] border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] focus:border-[var(--phosphor-green)]">
            <SelectValue placeholder="SELECT_RELATIONSHIP_TYPE" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--terminal-surface)] border-[var(--terminal-border)] max-h-60">
            {relationshipTypes.map((type) => (
              <SelectItem key={type} value={type} className="font-mono text-xs focus:bg-[var(--terminal-elevated)] focus:text-[var(--phosphor-green)]">
                {type.replace(/_/g, ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Strength and Confidence */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Label className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">Link_Strength</Label>
            <span className="text-xs font-mono font-bold text-[var(--cyan)]">{(formData.strength * 100).toFixed(0)}%</span>
          </div>
          <div className="py-2">
            <Slider
              value={[formData.strength]}
              onValueChange={([value]) => setFormData(prev => ({ ...prev, strength: value }))}
              max={1}
              min={0}
              step={0.01}
              className="w-full"
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Label className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">Confidence</Label>
            <span className="text-xs font-mono font-bold text-[var(--phosphor-green)]">{(formData.confidence_score * 100).toFixed(0)}%</span>
          </div>
          <div className="py-2">
            <Slider
              value={[formData.confidence_score]}
              onValueChange={([value]) => setFormData(prev => ({ ...prev, confidence_score: value }))}
              max={1}
              min={0}
              step={0.01}
              className="w-full"
            />
          </div>
        </div>
      </div>

      {/* Context */}
      <div className="space-y-2">
        <Label htmlFor="context" className="text-xs font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">Context_Buffer</Label>
        <Textarea
          id="context"
          value={formData.context}
          onChange={(e) => setFormData(prev => ({ ...prev, context: e.target.value }))}
          placeholder="DESCRIBE_CONTEXT..."
          rows={3}
          className="bg-[var(--terminal-bg)] border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)] focus:border-[var(--phosphor-green)] resize-none"
        />
      </div>

      {/* Evidence */}
      <Card className="bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <Shield className="w-4 h-4" />
            Supporting_Evidence
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-4">
          <div className="flex space-x-2">
            <Input
              placeholder="ADD_EVIDENCE_SNIPPET + ENTER"
              value={newEvidence}
              onChange={(e) => setNewEvidence(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addEvidence();
                }
              }}
              className="bg-[var(--terminal-bg)] border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)] focus:border-[var(--phosphor-green)]"
            />
            <Button 
              type="button" 
              onClick={addEvidence}
              variant="outline"
              className="border-[var(--terminal-border)] bg-[var(--terminal-elevated)] text-[var(--terminal-text)] hover:text-[var(--phosphor-green)] hover:border-[var(--phosphor-green)]"
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-2">
            {formData.evidence.map((evidence, index) => (
              <div key={index} className="flex items-center justify-between p-2 pl-3 bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] rounded-md">
                <p className="text-xs font-mono text-[var(--terminal-text)] flex-1">{evidence}</p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeEvidence(index)}
                  className="h-6 w-6 text-[var(--terminal-text-dim)] hover:text-red-400 hover:bg-red-400/10 p-0"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
            {formData.evidence.length === 0 && (
              <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] text-center py-4 opacity-50">
                NO_EVIDENCE_LOGGED
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-end space-x-3">
        <Button 
          type="button" 
          variant="outline" 
          onClick={onCancel}
          className="font-mono text-xs border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text)]"
        >
          ABORT_OP
        </Button>
        <Button 
          type="submit"
          className="font-mono text-xs bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)]"
        >
          <Save className="h-3.5 w-3.5 mr-2" />
          ESTABLISH_LINK
        </Button>
      </div>
    </form>
  );
};