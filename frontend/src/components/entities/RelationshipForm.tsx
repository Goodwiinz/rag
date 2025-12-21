/**
 * RelationshipForm Component
 * Form for creating and editing relationships between entities
 */

import React, { useState, useEffect } from 'react';
import { Link, Save, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Entity, GraphEdge } from '@/types/entity';
import { entityService } from '@/services/entityService';

interface RelationshipFormProps {
  sourceEntityId?: string;
  initialData?: Partial<GraphEdge>;
  onSubmit: (data: any) => void;
  onCancel: () => void;
}

const relationshipTypes = [
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
  onCancel
}) => {
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
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Source Entity */}
      {formData.source_entity_id && (
        <div className="space-y-2">
          <Label>Source Entity</Label>
          <Input value={formData.source_entity_id} disabled className="bg-gray-50" />
        </div>
      )}

      {/* Target Entity */}
      <div className="space-y-2">
        <Label htmlFor="target">Target Entity *</Label>
        <div className="space-y-2">
          {selectedTarget ? (
            <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
              <div>
                <p className="font-medium">{selectedTarget.name}</p>
                <p className="text-sm text-gray-600">{selectedTarget.type}</p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedTarget(null);
                  setFormData(prev => ({ ...prev, target_entity_id: '' }));
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="relative">
              <Input
                id="target"
                placeholder="Search for target entity..."
                value={targetSearchQuery}
                onChange={(e) => setTargetSearchQuery(e.target.value)}
              />
              {targetSearchResults.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                  {targetSearchResults.map((entity) => (
                    <button
                      key={entity.id}
                      type="button"
                      className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center justify-between"
                      onClick={() => selectTargetEntity(entity)}
                    >
                      <div>
                        <p className="font-medium">{entity.name}</p>
                        <p className="text-sm text-gray-600">{entity.type}</p>
                      </div>
                      <Link className="h-4 w-4 text-gray-400" />
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
        <Label htmlFor="type">Relationship Type *</Label>
        <Select
          value={formData.relationship_type}
          onValueChange={(value) => setFormData(prev => ({ ...prev, relationship_type: value }))}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select relationship type" />
          </SelectTrigger>
          <SelectContent>
            {relationshipTypes.map((type) => (
              <SelectItem key={type} value={type}>
                {type.replace(/_/g, ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Strength and Confidence */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Relationship Strength</Label>
          <div className="space-y-2">
            <Slider
              value={[formData.strength]}
              onValueChange={([value]) => setFormData(prev => ({ ...prev, strength: value }))}
              max={1}
              min={0}
              step={0.01}
              className="w-full"
            />
            <div className="flex justify-between text-sm text-gray-600">
              <span>Weak</span>
              <span className="font-medium">{(formData.strength * 100).toFixed(0)}%</span>
              <span>Strong</span>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label>Confidence Score</Label>
          <div className="space-y-2">
            <Slider
              value={[formData.confidence_score]}
              onValueChange={([value]) => setFormData(prev => ({ ...prev, confidence_score: value }))}
              max={1}
              min={0}
              step={0.01}
              className="w-full"
            />
            <div className="flex justify-between text-sm text-gray-600">
              <span>Low</span>
              <span className="font-medium">{(formData.confidence_score * 100).toFixed(0)}%</span>
              <span>High</span>
            </div>
          </div>
        </div>
      </div>

      {/* Context */}
      <div className="space-y-2">
        <Label htmlFor="context">Context</Label>
        <Textarea
          id="context"
          value={formData.context}
          onChange={(e) => setFormData(prev => ({ ...prev, context: e.target.value }))}
          placeholder="Describe the context where this relationship was found..."
          rows={3}
        />
      </div>

      {/* Evidence */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Evidence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex space-x-2">
            <Input
              placeholder="Add evidence snippet..."
              value={newEvidence}
              onChange={(e) => setNewEvidence(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addEvidence();
                }
              }}
            />
            <Button type="button" onClick={addEvidence}>
              Add
            </Button>
          </div>
          {formData.evidence.map((evidence, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded">
              <p className="text-sm flex-1">{evidence}</p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeEvidence(index)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
          {formData.evidence.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">
              No evidence added. Add evidence snippets to support this relationship.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-end space-x-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Save className="h-4 w-4 mr-2" />
          Create Relationship
        </Button>
      </div>
    </form>
  );
};