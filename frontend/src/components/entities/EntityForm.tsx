/**
 * EntityForm Component
 * Terminal Observatory themed entity form with duplicate detection
 */

import React, { useState, useEffect } from 'react';
import { Save, X, Plus, Trash2, AlertTriangle, Loader2, Database, Tag, Shield, Terminal, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Entity, EntityType } from '@/types/entity';
import { entityService } from '@/services/entityService';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import { cn } from '@/lib/utils';
import toast from 'react-hot-toast';

interface EntityFormProps {
  entity?: Entity | null;
  onSubmit: (data: Partial<Entity>) => void;
  onCancel: () => void;
  availableTypes?: string[];
}

const DEFAULT_ENTITY_TYPES: EntityType[] = [
  'PERSON',
  'ORGANIZATION',
  'LOCATION',
  'CONCEPT',
  'EVENT',
  'PRODUCT',
  'DATE',
  'TECHNOLOGY',
  'DOCUMENT',
  'TOPIC',
  'RESEARCH',
  'FINANCIAL',
  'EMAIL',
  'PHONE',
  'URL',
  'JOB_TITLE',
  'OTHER'
];

interface MetadataField {
  key: string;
  value: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
}

export const EntityForm: React.FC<EntityFormProps> = ({
  entity,
  onSubmit,
  onCancel,
  availableTypes
}) => {
  const { canCreate, canEdit } = useEntityPermissions();
  const isEditing = !!entity;
  const hasPermission = isEditing ? canEdit : canCreate;

  // Use available types from props or fall back to defaults
  const entityTypes = (availableTypes || DEFAULT_ENTITY_TYPES) as EntityType[];
  const [formData, setFormData] = useState({
    name: '',
    type: 'PERSON' as EntityType,
    confidence: 0.8,
    metadata: {
      description: '',
      aliases: [] as string[],
      category: '',
      properties: {} as Record<string, any>
    }
  });

  const [metadataFields, setMetadataFields] = useState<MetadataField[]>([]);
  const [duplicateWarning, setDuplicateWarning] = useState<{ show: boolean; entities: Entity[]; suggestedName: string } | null>(null);
  const [isCheckingDuplicate, setIsCheckingDuplicate] = useState(false);

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

  // Show locked state when user lacks permission
  if (!hasPermission) {
    return (
      <Card className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]">
        <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
          <div className="w-16 h-16 rounded-full bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] flex items-center justify-center">
            <Lock className="w-8 h-8 text-[var(--nous-fg-3)] opacity-50" />
          </div>
          <div className="text-center space-y-2">
            <h3 className="font-mono text-sm font-bold text-[var(--nous-fg-1)] uppercase tracking-wider">
              {isEditing ? 'EDIT_ACCESS_RESTRICTED' : 'CREATE_ACCESS_RESTRICTED'}
            </h3>
            <p className="font-mono text-xs text-[var(--nous-fg-3)] max-w-sm leading-relaxed">
              {isEditing
                ? 'You do not have permission to edit entities. Contact an administrator to request edit access.'
                : 'You do not have permission to create entities. Contact an administrator to request create access.'}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            className="font-mono text-xs border-[var(--nous-border-1)] hover:bg-[var(--nous-bg-3)] text-[var(--nous-fg-1)] mt-2"
          >
            DISMISS
          </Button>
        </CardContent>
      </Card>
    );
  }

  /**
   * Check for duplicate entities with the same name and type
   */
  const checkForDuplicates = async (name: string, type: EntityType): Promise<Entity[]> => {
    try {
      const existing = await entityService.searchEntities(name, [type], 5);
      return existing.filter(e =>
        e.name.toLowerCase() === name.toLowerCase() && e.type === type
      );
    } catch (error) {
      console.error('Error checking for duplicates:', error);
      return [];
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation: require name and type
    if (!formData.name.trim()) {
      toast.error('Entity name is required');
      return;
    }

    if (!formData.type) {
      toast.error('Entity type is required');
      return;
    }

    // Check for duplicates only when creating new entities (not editing)
    if (!entity) {
      setIsCheckingDuplicate(true);
      const duplicates = await checkForDuplicates(formData.name, formData.type);
      setIsCheckingDuplicate(false);

      if (duplicates.length > 0) {
        // Generate suggested name with suffix
        const suggestedName = `${formData.name} (2)`;
        setDuplicateWarning({ show: true, entities: duplicates, suggestedName });
        return; // Stop submission and show warning dialog
      }
    }

    // Build the final data object
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

  /**
   * Force create with the suggested name suffix
   */
  const handleForceCreate = () => {
    if (duplicateWarning) {
      setFormData(prev => ({ ...prev, name: duplicateWarning.suggestedName }));
      setDuplicateWarning(null);
      toast.success(`Entity name changed to "${duplicateWarning.suggestedName}"`);
    }
  };

  /**
   * Cancel duplicate warning and go back to editing
   */
  const handleCancelDuplicate = () => {
    setDuplicateWarning(null);
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
    <>
    <form onSubmit={handleSubmit} className="space-y-6 text-[var(--nous-fg-1)]">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="name" className="text-xs font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">Entity_Name *</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="ENTER_ENTITY_ID"
            required
            className="bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)] focus:border-[var(--nous-sol)] focus:ring-[var(--nous-sol)]/20"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="type" className="text-xs font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">Classification *</Label>
          <Select
            value={formData.type}
            onValueChange={(value: EntityType) => setFormData(prev => ({ ...prev, type: value }))}
          >
            <SelectTrigger className="bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] focus:border-[var(--nous-sol)]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]">
              {entityTypes.map((type: EntityType) => (
                <SelectItem key={type} value={type} className="font-mono text-xs focus:bg-[var(--nous-bg-3)] focus:text-[var(--nous-sol)]">
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Label htmlFor="confidence" className="text-xs font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">Confidence_Metric</Label>
          <span className="text-xs font-mono font-bold text-[var(--nous-sol)]">{(formData.confidence * 100).toFixed(1)}%</span>
        </div>
        <div className="py-2">
          <Slider
            value={[formData.confidence]}
            onValueChange={([value]) => setFormData(prev => ({ ...prev, confidence: value }))}
            max={1}
            min={0}
            step={0.01}
            className="w-full"
          />
        </div>
      </div>

      <Card className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]">
        <CardHeader className="border-b border-[var(--nous-border-1)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--nous-fg-3)] flex items-center gap-2">
            <Terminal className="w-4 h-4" />
            Core_Attributes
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 p-4">
          <div className="space-y-2">
            <Label htmlFor="description" className="text-xs font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">Description_Buffer</Label>
            <Textarea
              id="description"
              value={formData.metadata.description}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                metadata: { ...prev.metadata, description: e.target.value }
              }))}
              placeholder="ENTER_DESCRIPTION_TEXT"
              rows={3}
              className="bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)] focus:border-[var(--nous-sol)] resize-none"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category" className="text-xs font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">Category_Tag</Label>
            <Input
              id="category"
              value={formData.metadata.category}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                metadata: { ...prev.metadata, category: e.target.value }
              }))}
              placeholder="ENTER_CATEGORY"
              className="bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)] focus:border-[var(--nous-sol)]"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">Known_Aliases</Label>
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2 mb-2">
                {formData.metadata.aliases?.map((alias, index) => (
                  <div key={index} className="flex items-center gap-1 pl-2 pr-1 py-1 bg-[var(--nous-bg-3)] border border-[var(--nous-border-1)] rounded">
                    <span className="text-xs font-mono text-[var(--nous-fg-1)]">{alias}</span>
                    <button
                      type="button"
                      onClick={() => removeAlias(index)}
                      className="text-[var(--nous-fg-3)] hover:text-red-400 p-0.5 rounded transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex space-x-2">
                <Input
                  placeholder="ADD_ALIAS + ENTER"
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addAlias((e.target as HTMLInputElement).value);
                      (e.target as HTMLInputElement).value = '';
                    }
                  }}
                  className="bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)] focus:border-[var(--nous-sol)]"
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
                  className="border-[var(--nous-border-1)] bg-[var(--nous-bg-3)] text-[var(--nous-fg-1)] hover:text-[var(--nous-sol)] hover:border-[var(--nous-sol)]"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]">
        <CardHeader className="border-b border-[var(--nous-border-1)] py-3 flex flex-row items-center justify-between">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--nous-fg-3)] flex items-center gap-2">
            <Database className="w-4 h-4" />
            Extended_Properties
          </CardTitle>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={addMetadataField}
            className="h-6 text-[10px] font-mono hover:text-[var(--nous-sol)] hover:bg-[var(--nous-sol)]/10"
          >
            <Plus className="h-3 w-3 mr-1.5" />
            ADD_FIELD
          </Button>
        </CardHeader>
        <CardContent className="space-y-3 p-4">
          {metadataFields.length === 0 ? (
            <div className="text-center py-4 flex flex-col items-center gap-2 text-[var(--nous-fg-3)] opacity-50">
              <Shield className="w-6 h-6" />
              <p className="text-xs font-mono">NO_CUSTOM_FIELDS</p>
            </div>
          ) : (
            metadataFields.map((field, index) => (
              <div key={index} className="flex items-center space-x-2">
                <Input
                  placeholder="KEY"
                  value={field.key}
                  onChange={(e) => updateMetadataField(index, { key: e.target.value })}
                  className="w-1/3 bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-xs text-[var(--nous-fg-1)] h-8"
                />
                <Select
                  value={field.type}
                  onValueChange={(value: MetadataField['type']) => updateMetadataField(index, { type: value })}
                >
                  <SelectTrigger className="w-28 bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-xs text-[var(--nous-fg-3)] h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]">
                    <SelectItem value="string" className="font-mono text-xs">STRING</SelectItem>
                    <SelectItem value="number" className="font-mono text-xs">NUMBER</SelectItem>
                    <SelectItem value="boolean" className="font-mono text-xs">BOOL</SelectItem>
                    <SelectItem value="array" className="font-mono text-xs">ARRAY</SelectItem>
                    <SelectItem value="object" className="font-mono text-xs">OBJECT</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder="VALUE"
                  value={field.value}
                  onChange={(e) => updateMetadataField(index, { value: e.target.value })}
                  className="flex-1 bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-xs text-[var(--nous-fg-1)] h-8"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeMetadataField(index)}
                  className="h-8 w-8 text-red-500/50 hover:text-red-400 hover:bg-red-400/10"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Separator className="bg-[var(--nous-border-1)]" />

      <div className="flex justify-end space-x-3">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          className="font-mono text-xs border-[var(--nous-border-1)] hover:bg-[var(--nous-bg-3)] text-[var(--nous-fg-1)]"
        >
          ABORT_OP
        </Button>
        <Button
          type="submit"
          disabled={isCheckingDuplicate}
          className="font-mono text-xs bg-[var(--nous-sol)] text-[var(--nous-bg-1)] hover:shadow-[0_0_15px_var(--nous-sol-glow)]"
        >
          {isCheckingDuplicate ? (
            <>
              <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
              CHECKING...
            </>
          ) : (
            <>
              <Save className="h-3.5 w-3.5 mr-2" />
              {entity ? 'UPDATE_NODE' : 'PROVISION_NODE'}
            </>
          )}
        </Button>
      </div>
    </form>

      {/* Duplicate Warning Dialog */}
      {duplicateWarning && (
        <Dialog open={duplicateWarning.show} onOpenChange={() => setDuplicateWarning(null)}>
          <DialogContent className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)] text-[var(--nous-fg-1)]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[var(--nous-helios)] font-mono text-sm uppercase tracking-widest">
                <AlertTriangle className="h-5 w-5" />
                Duplicate_Entity_Warning
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <p className="text-xs font-mono text-[var(--nous-fg-3)]">
                An entity with the name <span className="text-[var(--nous-fg-1)] font-bold">{formData.name}</span> and type <span className="text-[var(--nous-fg-1)] font-bold">{formData.type}</span> already exists:
              </p>
              <div className="space-y-2">
                {duplicateWarning.entities.map((dup) => (
                  <Card key={dup.id} className="p-3 bg-[var(--nous-bg-3)] border-[var(--nous-border-1)]">
                    <div className="text-xs font-mono">
                      <div className="font-bold text-[var(--nous-fg-1)]">{dup.name}</div>
                      <div className="text-[var(--nous-fg-3)]">
                        Type: {dup.type} • Created: {new Date(dup.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
              <p className="text-xs font-mono text-[var(--nous-fg-3)]">
                Would you like to create anyway with the name <span className="text-[var(--nous-sol)] font-bold">{duplicateWarning.suggestedName}</span>?
              </p>
            </div>
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={handleCancelDuplicate}
                className="font-mono text-xs border-[var(--nous-border-1)] hover:bg-[var(--nous-bg-3)] text-[var(--nous-fg-1)]"
              >
                CANCEL
              </Button>
              <Button
                onClick={handleForceCreate}
                className="font-mono text-xs bg-[var(--nous-sol)] text-[var(--nous-bg-1)]"
              >
                CREATE_AS "{duplicateWarning.suggestedName}"
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
};
