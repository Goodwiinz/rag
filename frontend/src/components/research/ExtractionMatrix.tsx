'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Loader2, Pencil, Play, Trash2, X } from 'lucide-react';
import type {
  ExtractionColumn,
  ExtractionMatrix as ExtractionMatrixType,
  ExtractionTaskStatus,
} from '@/types/scispace';
import {
  createMatrix,
  deleteMatrix,
  getExtractionTaskStatus,
  getMatrix,
  listMatrices,
  triggerExtraction,
  updateMatrix,
} from '@/services/scispaceService';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ColumnEditor } from './ColumnEditor';
import { CellCitation } from './CellCitation';

interface ExtractionMatrixProps {
  projectId: string;
  matrixId?: string;
  documents?: Array<{ id: string; title: string }>;
}

export function ExtractionMatrix({
  projectId,
  matrixId,
  documents = [],
}: ExtractionMatrixProps) {
  const [matrix, setMatrix] = useState<ExtractionMatrixType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const [createName, setCreateName] = useState('');
  const [createColumns, setCreateColumns] = useState<ExtractionColumn[]>([
    { name: '', description: '' },
  ]);
  const [creating, setCreating] = useState(false);

  // Edit mode state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editColumns, setEditColumns] = useState<ExtractionColumn[]>([]);
  const [saving, setSaving] = useState(false);

  // Auto-extraction progress state
  const [autoExtractionTaskId, setAutoExtractionTaskId] = useState<
    string | null
  >(null);
  const [autoExtractionStatus, setAutoExtractionStatus] =
    useState<ExtractionTaskStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchMatrix = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMatrix(id);
      setMatrix(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load matrix');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (matrixId) {
      fetchMatrix(matrixId);
    } else {
      // Fetch existing matrices for this project
      setLoading(true);
      listMatrices(projectId)
        .then((data) => {
          if (data.matrices.length > 0) {
            fetchMatrix(data.matrices[0].id);
          }
        })
        .catch(() => {
          // No existing matrices — show create form
        })
        .finally(() => setLoading(false));
    }
  }, [matrixId, projectId, fetchMatrix]);

  // Poll auto-extraction status
  useEffect(() => {
    if (!autoExtractionTaskId) return;

    const poll = async () => {
      try {
        const status = await getExtractionTaskStatus(autoExtractionTaskId);
        setAutoExtractionStatus(status);

        if (status.status === 'completed' || status.status === 'failed') {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setAutoExtractionTaskId(null);

          // Refetch matrix to show new cells
          if (status.status === 'completed' && matrix) {
            await fetchMatrix(matrix.id);
          }
        }
      } catch {
        // Task may not be registered yet, keep polling
      }
    };

    pollRef.current = setInterval(poll, 3000);
    // Run immediately too
    poll();

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [autoExtractionTaskId, matrix, fetchMatrix]);

  const handleCreate = async () => {
    const validColumns = createColumns.filter((c) => c.name.trim());
    if (!createName.trim() || validColumns.length === 0) return;

    setCreating(true);
    setError(null);
    try {
      const result = await createMatrix(projectId, {
        name: createName.trim(),
        columns: validColumns.map((c) => ({
          name: c.name.trim(),
          description: c.description?.trim() || undefined,
        })),
      });
      await fetchMatrix(result.id);

      // Start polling if auto-extraction was triggered
      if (result.extraction_task_id) {
        setAutoExtractionTaskId(result.extraction_task_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create matrix');
    } finally {
      setCreating(false);
    }
  };

  const handleExtract = async () => {
    if (!matrix || documents.length === 0) return;

    setExtracting(true);
    setError(null);
    try {
      await triggerExtraction(matrix.id, {
        document_ids: documents.map((d) => d.id),
      });
      await fetchMatrix(matrix.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleDelete = async () => {
    if (!matrix) return;

    setDeleting(true);
    setError(null);
    try {
      await deleteMatrix(matrix.id);
      setMatrix(null);
      setDeleteOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete matrix');
    } finally {
      setDeleting(false);
    }
  };

  const handleStartEdit = () => {
    if (!matrix) return;
    setEditName(matrix.name);
    setEditColumns(matrix.columns.map((c) => ({ ...c })));
    setEditing(true);
  };

  const handleCancelEdit = () => {
    setEditing(false);
    setEditName('');
    setEditColumns([]);
  };

  const handleSaveEdit = async () => {
    if (!matrix) return;

    const validColumns = editColumns.filter((c) => c.name.trim());
    if (!editName.trim() || validColumns.length === 0) return;

    setSaving(true);
    setError(null);
    try {
      const result = await updateMatrix(matrix.id, {
        name: editName.trim(),
        columns: validColumns.map((c) => ({
          name: c.name.trim(),
          description: c.description?.trim() || undefined,
        })),
        clear_stale_cells: true,
      });

      setEditing(false);
      await fetchMatrix(matrix.id);

      // If columns changed, auto-trigger extraction for all documents
      if (result.columns_changed && documents.length > 0) {
        try {
          await triggerExtraction(matrix.id, {
            document_ids: documents.map((d) => d.id),
          });
          await fetchMatrix(matrix.id);
        } catch {
          // Non-critical — user can manually re-extract
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update matrix');
    } finally {
      setSaving(false);
    }
  };

  const handleExportCsv = () => {
    if (!matrix) return;

    const headers = ['Document', ...matrix.columns.map((c) => c.name)];
    const rows = documents.map((doc) => {
      const docCells = matrix.columns.map((col) => {
        const cell = matrix.cells.find(
          (c) => c.document_id === doc.id && c.column_name === col.name
        );
        return cell?.value ?? '';
      });
      return [doc.title, ...docCells];
    });

    const escape = (val: string) => {
      if (val.includes(',') || val.includes('"') || val.includes('\n')) {
        return `"${val.replace(/"/g, '""')}"`;
      }
      return val;
    };

    const csv = [
      headers.map(escape).join(','),
      ...rows.map((r) => r.map(escape).join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${matrix.name.replace(/\s+/g, '_')}_extraction.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const getCellValue = (documentId: string, columnName: string) => {
    return (
      matrix?.cells.find(
        (c) => c.document_id === documentId && c.column_name === columnName
      ) ?? null
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-[#00d4ff]" />
        <span className="ml-2 text-sm font-mono text-gray-500">
          Loading matrix...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-500/30 bg-red-500/5 p-4">
        <p className="text-sm font-mono text-red-400">{error}</p>
        {matrixId && (
          <Button
            variant="outline"
            size="sm"
            className="mt-3 border-red-500/30 text-red-400 hover:bg-red-500/10 font-mono text-xs"
            onClick={() => fetchMatrix(matrixId)}
          >
            Retry
          </Button>
        )}
      </div>
    );
  }

  if (!matrix && !matrixId) {
    return (
      <div className="space-y-6 rounded-lg border border-border bg-black/30 p-6">
        <div>
          <h3 className="text-sm font-mono font-bold text-[#00d4ff] uppercase tracking-wide mb-4">
            Create Extraction Matrix
          </h3>
          <div className="space-y-4">
            <div>
              <Label className="text-xs text-gray-500 font-mono uppercase tracking-wide">
                Matrix Name
              </Label>
              <Input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="e.g. Literature Review 2024"
                className="mt-1.5 bg-muted border-border text-sm font-mono text-foreground placeholder:text-muted-foreground focus:border-secondary"
              />
            </div>

            <ColumnEditor columns={createColumns} onChange={setCreateColumns} />

            <Button
              className="bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30 hover:bg-[#00d4ff]/20 font-mono text-sm"
              disabled={
                creating ||
                !createName.trim() ||
                createColumns.filter((c) => c.name.trim()).length === 0
              }
              isLoading={creating}
              loadingText="Creating..."
              onClick={handleCreate}
            >
              Create Matrix
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!matrix) return null;

  return (
    <div className="space-y-4">
      {/* Auto-extraction progress indicator */}
      {autoExtractionTaskId && autoExtractionStatus && (
        <div className="flex items-center gap-2 rounded-md border border-[#00d4ff]/30 bg-[#00d4ff]/5 px-4 py-2">
          <Loader2 className="h-4 w-4 animate-spin text-[#00d4ff]" />
          <span className="text-xs font-mono text-[#00d4ff]">
            Extracting {autoExtractionStatus.completed}/
            {autoExtractionStatus.total}...
          </span>
          {autoExtractionStatus.failed > 0 && (
            <span className="text-xs font-mono text-red-400">
              ({autoExtractionStatus.failed} failed)
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between rounded-lg border border-border bg-black/30 px-4 py-3">
        {editing ? (
          <div className="flex-1 mr-4">
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="bg-muted border-border text-sm font-mono text-foreground focus:border-secondary"
            />
          </div>
        ) : (
          <h3 className="text-sm font-mono font-bold text-[#00d4ff]">
            {matrix.name}
          </h3>
        )}
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="border-[#D4A039]/30 text-[#D4A039] hover:bg-[#D4A039]/10 font-mono text-xs"
                disabled={
                  saving ||
                  !editName.trim() ||
                  editColumns.filter((c) => c.name.trim()).length === 0
                }
                isLoading={saving}
                loadingText="Saving..."
                onClick={handleSaveEdit}
              >
                Save
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-border text-muted-foreground hover:bg-white/5 font-mono text-xs"
                onClick={handleCancelEdit}
                disabled={saving}
              >
                <X className="h-3 w-3 mr-1" />
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                className="border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/10 font-mono text-xs"
                onClick={handleStartEdit}
              >
                <Pencil className="h-3 w-3 mr-1" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-[#D4A039]/30 text-[#D4A039] hover:bg-[#D4A039]/10 font-mono text-xs"
                disabled={extracting || documents.length === 0}
                isLoading={extracting}
                loadingText="Extracting..."
                onClick={handleExtract}
              >
                <Play className="h-3 w-3 mr-1" />
                Extract
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-[#ffb700]/30 text-[#ffb700] hover:bg-[#ffb700]/10 font-mono text-xs"
                onClick={handleExportCsv}
                disabled={matrix.cells.length === 0}
              >
                <Download className="h-3 w-3 mr-1" />
                Export CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-red-500/30 text-red-400 hover:bg-red-500/10 font-mono text-xs"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="h-3 w-3 mr-1" />
                Delete
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Column editor in edit mode */}
      {editing && (
        <div className="rounded-lg border border-border bg-black/30 p-4">
          <ColumnEditor columns={editColumns} onChange={setEditColumns} />
        </div>
      )}

      <div className="rounded-lg border border-border bg-black/30 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-xs font-mono text-gray-500 uppercase tracking-wide bg-card min-w-[200px]">
                Document
              </TableHead>
              {matrix.columns.map((col) => (
                <TableHead
                  key={col.name}
                  className="text-xs font-mono text-gray-500 uppercase tracking-wide bg-card min-w-[150px]"
                  title={col.description}
                >
                  {col.name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.length === 0 ? (
              <TableRow className="border-border">
                <TableCell
                  colSpan={matrix.columns.length + 1}
                  className="text-center text-sm font-mono text-muted-foreground py-8"
                >
                  No documents available
                </TableCell>
              </TableRow>
            ) : (
              documents.map((doc) => (
                <TableRow
                  key={doc.id}
                  className="border-border hover:bg-white/[0.02]"
                >
                  <TableCell className="text-sm font-mono text-gray-300 font-medium">
                    {doc.title}
                  </TableCell>
                  {matrix.columns.map((col) => {
                    const cell = getCellValue(doc.id, col.name);
                    return (
                      <TableCell
                        key={col.name}
                        className="text-sm font-mono text-gray-400"
                      >
                        <div className="flex items-start gap-1.5">
                          <span className="flex-1">{cell?.value ?? ''}</span>
                          <CellCitation
                            citation_snippet={cell?.citation_snippet ?? null}
                            confidence={cell?.confidence ?? null}
                          />
                        </div>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="font-mono text-gray-300">
              Delete Matrix
            </DialogTitle>
            <DialogDescription className="font-mono text-gray-500">
              This will permanently delete &quot;{matrix.name}&quot; and all
              extracted data. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              className="font-mono text-xs border-border text-muted-foreground"
              onClick={() => setDeleteOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              className="font-mono text-xs"
              disabled={deleting}
              isLoading={deleting}
              loadingText="Deleting..."
              onClick={handleDelete}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ExtractionMatrix;
