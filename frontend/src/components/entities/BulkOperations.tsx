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
import { parseBulkEntitiesFromCsv } from '@/utils/csvEntityImport';
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
      <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
        <CardHeader>
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--nous-fg-3)] flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Bulk Operations
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="text-center py-12">
            <Lock className="w-12 h-12 mx-auto mb-4 text-[var(--nous-fg-3)]" />
            <p className="text-sm font-mono text-[var(--nous-fg-3)]">
              Bulk operations are restricted to administrators only.
            </p>
            <p className="text-xs font-mono text-[var(--nous-fg-3)] mt-2">
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

      const entities = parseBulkEntitiesFromCsv(csvInput);

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
        _comment: 'Available relationship_types: WORKS_FOR, KNOWS, RELATED_TO, LOCATED_IN, PART_OF, MENTIONED_IN, APPEARS_WITH, CREATED_BY, OWNS, MANAGES, COLLABORATES_WITH, REPORTS_TO, MEMBER_OF, ATTENDED, SPOKE_AT, PUBLISHED_BY, CITED, REFERENCES, CUSTOM',
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
      <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
        <CardHeader className="border-b border-[var(--nous-border-1)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--nous-fg-3)] flex items-center gap-2">
            <Upload className="w-4 h-4" />
            Bulk Operations
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <Tabs defaultValue="json" className="w-full">
            <TabsList className="grid w-full grid-cols-2 bg-[var(--nous-bg-1)]">
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
                  <Label className="text-xs font-mono text-[var(--nous-fg-3)]">
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
                  className="font-mono text-xs bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] text-[var(--nous-fg-1)] min-h-[200px]"
                />
              </div>
              <Button
                onClick={handleBulkCreateFromJSON}
                disabled={loading || !jsonInput.trim()}
                className="w-full font-mono text-xs font-bold bg-[var(--nous-sol)] text-[var(--nous-bg-1)]"
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
                  <Label className="text-xs font-mono text-[var(--nous-fg-3)]">
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
                  className="font-mono text-xs bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] text-[var(--nous-fg-1)] min-h-[200px]"
                />
              </div>
              <Button
                onClick={handleBulkCreateFromCSV}
                disabled={loading || !csvInput.trim()}
                className="w-full font-mono text-xs font-bold bg-[var(--nous-sol)] text-[var(--nous-bg-1)]"
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
        <Card className="border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
          <CardHeader className="border-b border-[var(--nous-border-1)] py-3">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--nous-fg-3)]">
              Bulk Operation Results
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[var(--nous-sol)]" />
                  <span className="text-xs font-mono text-[var(--nous-fg-3)]">
                    CREATED ENTITIES
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--nous-sol)] mt-2">
                  {result.created_entities.length}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[var(--nous-helios)]" />
                  <span className="text-xs font-mono text-[var(--nous-fg-3)]">
                    CREATED RELATIONSHIPS
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--nous-helios)] mt-2">
                  {result.created_relationships.length}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-[var(--nous-helios)]" />
                  <span className="text-xs font-mono text-[var(--nous-fg-3)]">
                    ERRORS
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--nous-helios)] mt-2">
                  {result.errors.length}
                </p>
              </div>
            </div>

            {/* Processing Time */}
            <div className="text-xs font-mono text-[var(--nous-fg-3)]">
              Processing time: {result.processing_time.toFixed(2)}s
            </div>

            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-mono font-bold text-[var(--nous-fg-1)] uppercase">
                  Errors
                </div>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((error, index) => (
                    <div
                      key={index}
                      className="text-xs font-mono text-[var(--nous-helios)] p-2 rounded bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)]"
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
