/**
 * BulkOperations Component
 * Supports bulk entity and relationship creation/deletion
 */

import React, { useState } from 'react';
import { Upload, Download, Trash2, Loader2, CheckCircle, AlertCircle, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Entity } from '@/types/entity';
import { entityService } from '@/services/entityService';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import toast from 'react-hot-toast';

interface BulkCreateResult {
  created_entities: Entity[];
  created_relationships: any[];
  errors: Array<{ entity: any; error: string }>;
  processing_time: number;
}

export const BulkOperations: React.FC = () => {
  const { canBulkEdit, isAdmin } = useEntityPermissions();
  const [jsonInput, setJsonInput] = useState('');
  const [csvInput, setCsvInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BulkCreateResult | null>(null);

  // Show admin-only notice if user lacks permissions
  if (!canBulkEdit) {
    return (
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader>
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Bulk Operations
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="text-center py-12">
            <Lock className="w-12 h-12 mx-auto mb-4 text-[var(--terminal-text-dim)]" />
            <p className="text-sm font-mono text-[var(--terminal-text-dim)]">
              Bulk operations are restricted to administrators only.
            </p>
            <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-2">
              Contact your system administrator for access.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const handleBulkCreateFromJSON = async () => {
    try {
      setLoading(true);
      const data = JSON.parse(jsonInput);
      
      if (!data.entities || !Array.isArray(data.entities)) {
        toast.error('Invalid JSON: must contain an "entities" array');
        return;
      }

      const bulkResult = await entityService.batchCreate({
        entities: data.entities,
        relationships: data.relationships || [],
        upsert: data.upsert || false,
      });

      setResult(bulkResult);
      toast.success(
        `Created ${bulkResult.created_entities.length} entities and ${bulkResult.created_relationships.length} relationships`
      );
    } catch (error: any) {
      console.error('Error in bulk create:', error);
      toast.error(error.message || 'Failed to create entities');
    } finally {
      setLoading(false);
    }
  };

  const handleBulkCreateFromCSV = async () => {
    try {
      setLoading(true);
      
      // Parse CSV
      const lines = csvInput.trim().split('\n');
      if (lines.length < 2) {
        toast.error('CSV must have at least a header and one data row');
        return;
      }

      const headers = lines[0].split(',').map(h => h.trim());
      const entities = [];

      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',').map(v => v.trim());
        const entity: any = {};
        
        headers.forEach((header, index) => {
          entity[header] = values[index];
        });

        // Convert to proper entity format
        entities.push({
          name: entity.name,
          entity_type: entity.entity_type || entity.type,
          confidence_score: parseFloat(entity.confidence_score || '0.8'),
          extraction_method: entity.extraction_method || 'manual',
          metadata: {},
        });
      }

      const bulkResult = await entityService.batchCreate({
        entities,
        upsert: true,
      });

      setResult(bulkResult);
      toast.success(`Created ${bulkResult.created_entities.length} entities from CSV`);
    } catch (error: any) {
      console.error('Error parsing CSV:', error);
      toast.error(error.message || 'Failed to parse CSV');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTemplate = (format: 'json' | 'csv') => {
    if (format === 'json') {
      const template = {
        entities: [
          {
            name: 'Example Entity',
            entity_type: 'CONCEPT',
            confidence_score: 0.9,
            extraction_method: 'manual',
            metadata: { description: 'Example description' },
          },
        ],
        relationships: [
          {
            source_entity_id: 'entity-id-1',
            target_entity_id: 'entity-id-2',
            relationship_type: 'RELATED_TO',
            strength: 0.8,
            confidence_score: 0.9,
          },
        ],
        upsert: false,
      };

      const blob = new Blob([JSON.stringify(template, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bulk-import-template.json';
      a.click();
      URL.revokeObjectURL(url);
    } else {
      const csv = 'name,entity_type,confidence_score,extraction_method\nExample Entity,CONCEPT,0.9,manual';
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bulk-import-template.csv';
      a.click();
      URL.revokeObjectURL(url);
    }

    toast.success(`Downloaded ${format.toUpperCase()} template`);
  };

  return (
    <div className="space-y-4">
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <Upload className="w-4 h-4" />
            Bulk Operations
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <Tabs defaultValue="json" className="w-full">
            <TabsList className="grid w-full grid-cols-2 bg-[var(--terminal-bg)]">
              <TabsTrigger value="json" className="font-mono text-xs">
                JSON Import
              </TabsTrigger>
              <TabsTrigger value="csv" className="font-mono text-xs">
                CSV Import
              </TabsTrigger>
            </TabsList>

            <TabsContent value="json" className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    JSON Data
                  </Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDownloadTemplate('json')}
                    className="font-mono text-[10px]"
                  >
                    <Download className="w-3 h-3 mr-1" />
                    TEMPLATE
                  </Button>
                </div>
                <Textarea
                  placeholder='{"entities": [{"name": "...", "entity_type": "..."}], "relationships": []}'
                  value={jsonInput}
                  onChange={(e) => setJsonInput(e.target.value)}
                  className="font-mono text-xs bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)] min-h-[200px]"
                />
              </div>
              <Button
                onClick={handleBulkCreateFromJSON}
                disabled={loading || !jsonInput.trim()}
                className="w-full font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)]"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    PROCESSING...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    BULK_CREATE_FROM_JSON
                  </>
                )}
              </Button>
            </TabsContent>

            <TabsContent value="csv" className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    CSV Data
                  </Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDownloadTemplate('csv')}
                    className="font-mono text-[10px]"
                  >
                    <Download className="w-3 h-3 mr-1" />
                    TEMPLATE
                  </Button>
                </div>
                <Textarea
                  placeholder="name,entity_type,confidence_score,extraction_method&#10;Entity Name,CONCEPT,0.9,manual"
                  value={csvInput}
                  onChange={(e) => setCsvInput(e.target.value)}
                  className="font-mono text-xs bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)] min-h-[200px]"
                />
              </div>
              <Button
                onClick={handleBulkCreateFromCSV}
                disabled={loading || !csvInput.trim()}
                className="w-full font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)]"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    PROCESSING...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    BULK_CREATE_FROM_CSV
                  </>
                )}
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardHeader className="border-b border-[var(--terminal-border)] py-3">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)]">
              Bulk Operation Results
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[var(--phosphor-green)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    CREATED ENTITIES
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--phosphor-green)] mt-2">
                  {result.created_entities.length}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[var(--cyan)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    CREATED RELATIONSHIPS
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--cyan)] mt-2">
                  {result.created_relationships.length}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-[var(--amber-gold)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    ERRORS
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--amber-gold)] mt-2">
                  {result.errors.length}
                </p>
              </div>
            </div>

            {/* Processing Time */}
            <div className="text-xs font-mono text-[var(--terminal-text-dim)]">
              Processing time: {result.processing_time.toFixed(2)}s
            </div>

            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-mono font-bold text-[var(--terminal-text)] uppercase">
                  Errors
                </div>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((error, index) => (
                    <div
                      key={index}
                      className="text-xs font-mono text-[var(--amber-gold)] p-2 rounded bg-[var(--terminal-bg)] border border-[var(--terminal-border)]"
                    >
                      {error.error}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
