/**
 * EntityForm Component
 * Form for creating and editing entities
 */

import React, { useState, useEffect } from 'react';
import { Save, X, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Entity, EntityType } from '@/types/entity';

interface EntityFormProps {
  entity?: Entity | null;
  onSubmit: (data: Partial<Entity>) => void;
  onCancel: () => void;
}

const entityTypes: EntityType[] = [
  'PERSON',
  'ORGANIZATION',
  'LOCATION',
  'CONCEPT',
  'EVENT',
  'PRODUCT',
  'DATE',
  'TECHNOLOGY',
  'DOCUMENT'
];

interface MetadataField {
  key: string;
  value: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
}

export const EntityForm: React.FC<EntityFormProps> = ({
  entity,
  onSubmit,
  onCancel
}) => {
  const [formData, setFormData] = useState({
    name: '',
    type: 'PERSON' as EntityType,
    confidence: 0.8,
    metadata: {
      description: '',
      aliases: [],
      category: '',
      properties: {} as Record<string, any>
    }
  });

  const [metadataFields, setMetadataFields] = useState<MetadataField[]>([]);

  useEffect(() => {
    if (entity) {
      setFormData({
        name: entity.name || '',
        type: entity.type || 'PERSON',
        confidence: entity.confidence || 0.8,
        metadata: {
          description: entity.metadata?.description || '',
          aliases: entity.metadata?.aliases || [],
          category: entity.metadata?.category || '',
          properties: entity.metadata?.properties || {}
        }
      });

      // Convert metadata properties to fields
      const fields: MetadataField[] = [];
      Object.entries(entity.metadata?.properties || {}).forEach(([key, value]) => {
        let type: MetadataField['type'] = 'string';
        if (Array.isArray(value)) type = 'array';
        else if (typeof value === 'number') type = 'number';
        else if (typeof value === 'boolean') type = 'boolean';
        else if (typeof value === 'object') type = 'object';

        fields.push({
          key,
          value: Array.isArray(value) ? value.join(', ') : String(value),
          type
        });
      });
      setMetadataFields(fields);
    }
  }, [entity]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const properties: Record<string, any> = {};
    metadataFields.forEach(field => {
      if (field.value) {
        switch (field.type) {
          case 'number':
            properties[field.key] = parseFloat(field.value);
            break;
          case 'boolean':
            properties[field.key] = field.value === 'true';
            break;
          case 'array':
            properties[field.key] = field.value.split(',').map(v => v.trim());
            break;
          case 'object':
            try {
              properties[field.key] = JSON.parse(field.value);
            } catch {
              properties[field.key] = field.value;
            }
            break;
          default:
            properties[field.key] = field.value;
        }
      }
    });

    const data = {
      ...formData,
      metadata: {
        ...formData.metadata,
        properties
      }
    };

    onSubmit(data);
  };

  const addMetadataField = () => {
    setMetadataFields(prev => [...prev, { key: '', value: '', type: 'string' }]);
  };

  const updateMetadataField = (index: number, field: Partial<MetadataField>) => {
    setMetadataFields(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], ...field };
      return updated;
    });
  };

  const removeMetadataField = (index: number) => {
    setMetadataFields(prev => prev.filter((_, i) => i !== index));
  };

  const addAlias = (alias: string) => {
    if (alias.trim()) {
      setFormData(prev => ({
        ...prev,
        metadata: {
          ...prev.metadata,
          aliases: [...(prev.metadata.aliases || []), alias.trim()]
        }
      }));
    }
  };

  const removeAlias = (index: number) => {
    setFormData(prev => ({
      ...prev,
      metadata: {
        ...prev.metadata,
        aliases: prev.metadata.aliases?.filter((_, i) => i !== index) || []
      }
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="name">Entity Name *</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Enter entity name"
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="type">Entity Type</Label>
          <Select
            value={formData.type}
            onValueChange={(value: EntityType) => setFormData(prev => ({ ...prev, type: value }))}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {entityTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="confidence">Confidence Score</Label>
        <div className="space-y-2">
          <Slider
            value={[formData.confidence]}
            onValueChange={([value]) => setFormData(prev => ({ ...prev, confidence: value }))}
            max={1}
            min={0}
            step={0.01}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-gray-600">
            <span>0%</span>
            <span className="font-medium">{(formData.confidence * 100).toFixed(1)}%</span>
            <span>100%</span>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.metadata.description}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                metadata: { ...prev.metadata, description: e.target.value }
              }))}
              placeholder="Enter entity description"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Category</Label>
            <Input
              id="category"
              value={formData.metadata.category}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                metadata: { ...prev.metadata, category: e.target.value }
              }))}
              placeholder="Enter category (e.g., Technology, Company, City)"
            />
          </div>

          <div className="space-y-2">
            <Label>Aliases</Label>
            <div className="space-y-2">
              {formData.metadata.aliases?.map((alias, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <span className="flex-1 px-3 py-2 bg-gray-100 rounded">{alias}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeAlias(index)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <div className="flex space-x-2">
                <Input
                  placeholder="Add alias and press Enter"
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      addAlias((e.target as HTMLInputElement).value);
                      (e.target as HTMLInputElement).value = '';
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={(e) => {
                    const input = e.currentTarget.parentElement?.querySelector('input');
                    if (input) {
                      addAlias(input.value);
                      input.value = '';
                    }
                  }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Custom Properties</CardTitle>
            <Button type="button" variant="outline" size="sm" onClick={addMetadataField}>
              <Plus className="h-4 w-4 mr-2" />
              Add Property
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {metadataFields.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">
              No custom properties added. Click "Add Property" to add one.
            </p>
          ) : (
            metadataFields.map((field, index) => (
              <div key={index} className="flex items-center space-x-2">
                <Input
                  placeholder="Property name"
                  value={field.key}
                  onChange={(e) => updateMetadataField(index, { key: e.target.value })}
                  className="w-1/3"
                />
                <Select
                  value={field.type}
                  onValueChange={(value: MetadataField['type']) => updateMetadataField(index, { type: value })}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">String</SelectItem>
                    <SelectItem value="number">Number</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="array">Array</SelectItem>
                    <SelectItem value="object">Object</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder="Value"
                  value={field.value}
                  onChange={(e) => updateMetadataField(index, { value: e.target.value })}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeMetadataField(index)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Separator />

      <div className="flex justify-end space-x-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Save className="h-4 w-4 mr-2" />
          {entity ? 'Update Entity' : 'Create Entity'}
        </Button>
      </div>
    </form>
  );
};