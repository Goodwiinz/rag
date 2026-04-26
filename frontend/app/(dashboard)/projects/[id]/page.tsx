'use client';

/**
 * Project Detail Page
 * Displays project information with tabs for Documents, Notes, Bibliography,
 * Drafts, Chat, Matrix, and Pipeline
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  FileText,
  StickyNote,
  BookOpen,
  Sparkles,
  Plus,
  Download,
  Loader2,
  RefreshCw,
  MessageSquare,
  Grid3X3,
  GitBranch,
  Network,
} from 'lucide-react';
import { ProjectHeader } from '@/components/research/ProjectHeader';
import { DocumentList } from '@/components/research/DocumentList';
import { ProjectKnowledgeTree } from '@/components/research/ProjectKnowledgeTree';
import { DraftGenerator } from '@/components/research/DraftGenerator';
import { DraftViewer } from '@/components/research/DraftViewer';
import { DraftGenerationProgress } from '@/components/research/DraftGenerationProgress';
import { DraftComparison } from '@/components/research/DraftComparison';
import { DraftExportModal } from '@/components/research/DraftExportModal';
import { ProjectChatTab } from '@/components/research/ProjectChatTab';
import { ExtractionMatrix } from '@/components/research/ExtractionMatrix';
import { ResearchPipeline } from '@/components/research/ResearchPipeline';
import { NoteEditor } from '@/components/research/NoteEditor';
import { NoteList } from '@/components/research/NoteList';
import {
  projectService,
  type Draft,
  type DraftComparison as DraftComparisonData,
  type GenerationStatus,
} from '@/services/projectService';
import { useProjectStore } from '@/store/projectStore';
import { useAgentChatStore } from '@/store/agentChatStore';
import { useAuthStore } from '@/store/authStore';
import { APIErrorClass } from '@/types/api';
import type { ProjectNote, ProjectNoteCreate } from '@/services/projectService';

type TabType =
  | 'documents'
  | 'notes'
  | 'bibliography'
  | 'drafts'
  | 'chat'
  | 'matrix'
  | 'pipeline'
  | 'knowledge';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { isAuthenticated } = useAuthStore();

  const {
    currentProject,
    projectDocuments,
    projectNotes,
    bibliography,
    loading,
    documentsLoading,
    notesLoading,
    error,
    fetchProject,
    fetchProjectDocuments,
    fetchProjectNotes,
    removeDocument,
    createNote,
    updateNote,
    deleteNote,
    toggleNotePin,
    fetchBibliography,
    downloadBibliography,
    clearError,
  } = useProjectStore();

  const [mounted, setMounted] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('documents');
  const [bibFormat, setBibFormat] = useState<'bibtex' | 'ieee' | 'apa' | 'mla'>(
    'bibtex'
  );

  // Draft state
  const [currentDraft, setCurrentDraft] = useState<Draft | null>(null);
  const [draftVersions, setDraftVersions] = useState<
    Array<{
      id: string;
      version: number;
      created_at: string;
      is_current: boolean;
    }>
  >([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [generationTaskId, setGenerationTaskId] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] =
    useState<GenerationStatus | null>(null);
  const [compareVersionA, setCompareVersionA] = useState<number | null>(null);
  const [compareVersionB, setCompareVersionB] = useState<number | null>(null);
  const [draftComparison, setDraftComparison] =
    useState<DraftComparisonData | null>(null);
  const [comparisonDraftA, setComparisonDraftA] = useState<Draft | null>(null);
  const [comparisonDraftB, setComparisonDraftB] = useState<Draft | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportInitialFormat, setExportInitialFormat] = useState<
    'markdown' | 'latex'
  >('markdown');

  // Note editing state
  const [editingNote, setEditingNote] = useState<ProjectNote | null>(null);
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [selectedNoteTag, setSelectedNoteTag] = useState('');
  const [matrixId, setMatrixId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [projectError, setProjectError] = useState<{
    status: number;
    message: string;
  } | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const projectDataVersion = useAgentChatStore((s) => s.projectDataVersion);

  useEffect(() => {
    if (mounted && isAuthenticated && projectId) {
      fetchProject(projectId)
        .then(() => setProjectError(null))
        .catch((err: unknown) => {
          const status =
            err instanceof APIErrorClass ? err.error.status_code : 500;
          const message =
            err instanceof Error ? err.message : 'Failed to load project';
          setProjectError({ status, message });
        })
        .finally(() => setInitialLoading(false));
      fetchProjectDocuments(projectId);
      fetchProjectNotes(projectId);
    }
  }, [
    mounted,
    isAuthenticated,
    projectId,
    fetchProject,
    fetchProjectDocuments,
    fetchProjectNotes,
  ]);

  // Refetch project data when agent tools mutate it (e.g. add_document_to_project)
  useEffect(() => {
    if (projectDataVersion > 0 && projectId) {
      fetchProject(projectId);
      fetchProjectDocuments(projectId);
      fetchProjectNotes(projectId);
    }
  }, [
    projectDataVersion,
    projectId,
    fetchProject,
    fetchProjectDocuments,
    fetchProjectNotes,
  ]);

  const loadDrafts = useCallback(
    async (preferredVersion?: number) => {
      setDraftsLoading(true);
      try {
        const response = await projectService.listDrafts(projectId, {
          limit: 50,
        });
        const versions = response.drafts.map((draft) => ({
          id: draft.id,
          version: draft.version,
          created_at: draft.created_at,
          is_current: draft.is_current,
        }));

        setDraftVersions(versions);

        if (versions.length === 0) {
          setCurrentDraft(null);
          setCompareVersionA(null);
          setCompareVersionB(null);
          setDraftComparison(null);
          setComparisonDraftA(null);
          setComparisonDraftB(null);
          return;
        }

        const selectedVersion =
          preferredVersion ??
          versions.find((draft) => draft.is_current)?.version ??
          versions[0].version;

        const selectedDraftMeta =
          versions.find((draft) => draft.version === selectedVersion) ??
          versions[0];

        const selectedDraft = await projectService.getDraft(
          projectId,
          selectedDraftMeta.id
        );
        setCurrentDraft(selectedDraft);

        setCompareVersionA((previous) => {
          if (
            previous &&
            versions.some((draft) => draft.version === previous)
          ) {
            return previous;
          }
          return versions[0].version;
        });

        setCompareVersionB((previous) => {
          if (
            previous &&
            versions.some((draft) => draft.version === previous)
          ) {
            return previous;
          }
          return versions.length > 1
            ? versions[1].version
            : versions[0].version;
        });
      } catch (err) {
        console.error('Failed to load drafts:', err);
      } finally {
        setDraftsLoading(false);
      }
    },
    [projectId]
  );

  useEffect(() => {
    if (activeTab === 'drafts' && mounted && isAuthenticated && projectId) {
      void loadDrafts();
    }
  }, [activeTab, mounted, isAuthenticated, projectId, loadDrafts]);

  useEffect(() => {
    if (
      projectDataVersion > 0 &&
      activeTab === 'drafts' &&
      mounted &&
      isAuthenticated &&
      projectId
    ) {
      void loadDrafts();
    }
  }, [
    activeTab,
    isAuthenticated,
    loadDrafts,
    mounted,
    projectDataVersion,
    projectId,
  ]);

  const handleDraftVersionChange = useCallback(
    async (version: number) => {
      setDraftComparison(null);
      setComparisonDraftA(null);
      setComparisonDraftB(null);
      await loadDrafts(version);
    },
    [loadDrafts]
  );

  const handleCompareDrafts = useCallback(async () => {
    if (compareVersionA === null || compareVersionB === null) {
      return;
    }
    if (compareVersionA === compareVersionB) {
      return;
    }

    const draftA = draftVersions.find(
      (draft) => draft.version === compareVersionA
    );
    const draftB = draftVersions.find(
      (draft) => draft.version === compareVersionB
    );

    if (!draftA || !draftB) {
      return;
    }

    setComparisonLoading(true);
    try {
      const [comparison, draftAData, draftBData] = await Promise.all([
        projectService.compareDrafts(
          projectId,
          compareVersionA,
          compareVersionB
        ),
        projectService.getDraft(projectId, draftA.id),
        projectService.getDraft(projectId, draftB.id),
      ]);
      setDraftComparison(comparison);
      setComparisonDraftA(draftAData);
      setComparisonDraftB(draftBData);
    } catch (err) {
      console.error('Failed to compare drafts:', err);
    } finally {
      setComparisonLoading(false);
    }
  }, [compareVersionA, compareVersionB, draftVersions, projectId]);

  const handleTabChange = useCallback(
    (tab: TabType) => {
      setActiveTab(tab);
      if (tab === 'bibliography' && !bibliography) {
        fetchBibliography(projectId, bibFormat);
      }
    },
    [projectId, bibliography, bibFormat, fetchBibliography]
  );

  const handleRemoveDocument = async (documentId: string) => {
    try {
      await removeDocument(projectId, documentId);
    } catch (err) {
      console.error('Failed to remove document:', err);
    }
  };

  const handleCreateNote = () => {
    setEditingNote(null);
    setShowNoteEditor(true);
  };

  const handleEditNote = (note: ProjectNote) => {
    setEditingNote(note);
    setShowNoteEditor(true);
  };

  const handleSaveNote = async (noteData: ProjectNoteCreate) => {
    try {
      if (editingNote) {
        await updateNote(projectId, editingNote.id, {
          title: noteData.title.trim(),
          content: noteData.content,
          tags: noteData.tags,
          linked_document_ids: noteData.linked_document_ids,
        });
      } else {
        await createNote(projectId, noteData);
      }
      setShowNoteEditor(false);
      setEditingNote(null);
    } catch (err) {
      console.error('Failed to save note:', err);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    if (!confirm('Delete this note?')) return;
    try {
      await deleteNote(projectId, noteId);
    } catch (err) {
      console.error('Failed to delete note:', err);
    }
  };

  const handleTogglePin = async (noteId: string) => {
    try {
      await toggleNotePin(projectId, noteId);
    } catch (err) {
      console.error('Failed to toggle pin:', err);
    }
  };

  const handleExportBibliography = async () => {
    try {
      await downloadBibliography(projectId, bibFormat);
    } catch (err) {
      console.error('Failed to download bibliography:', err);
    }
  };

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const refreshTasks: Array<Promise<unknown>> = [
        fetchProject(projectId),
        fetchProjectDocuments(projectId),
        fetchProjectNotes(projectId),
      ];

      if (activeTab === 'bibliography') {
        refreshTasks.push(fetchBibliography(projectId, bibFormat));
      }

      if (activeTab === 'drafts') {
        refreshTasks.push(loadDrafts());
      }

      await Promise.allSettled(refreshTasks);
    } finally {
      setRefreshing(false);
    }
  }, [
    activeTab,
    bibFormat,
    fetchBibliography,
    fetchProject,
    fetchProjectDocuments,
    fetchProjectNotes,
    loadDrafts,
    projectId,
  ]);

  if (!mounted || initialLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (projectError) {
    const isNotFound = projectError.status === 404;
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">
          {isNotFound
            ? 'Project not found'
            : `Failed to load project: ${projectError.message}`}
        </p>
        <button
          onClick={() => router.push('/projects')}
          className="mt-4 text-primary underline text-sm"
        >
          Back to projects
        </button>
      </div>
    );
  }

  if (!currentProject) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Project not found</p>
        <button
          onClick={() => router.push('/projects')}
          className="mt-4 text-primary underline text-sm"
        >
          Back to projects
        </button>
      </div>
    );
  }

  const tabs: Array<{
    id: TabType;
    label: string;
    icon: React.ElementType;
    count?: number;
  }> = [
    {
      id: 'documents',
      label: 'Documents',
      icon: FileText,
      count: projectDocuments.length,
    },
    {
      id: 'notes',
      label: 'Notes',
      icon: StickyNote,
      count: projectNotes.length,
    },
    { id: 'bibliography', label: 'Bibliography', icon: BookOpen },
    {
      id: 'drafts',
      label: 'Drafts',
      icon: Sparkles,
      count: draftVersions.length || undefined,
    },
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'matrix', label: 'Matrix', icon: Grid3X3 },
    { id: 'pipeline', label: 'Pipeline', icon: GitBranch },
    { id: 'knowledge', label: 'Knowledge', icon: Network },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <ProjectHeader project={currentProject} />

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
          <p className="text-destructive text-sm">{error}</p>
          <button
            onClick={clearError}
            className="mt-2 text-xs text-destructive underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-6 flex items-end gap-3 border-b border-border pb-2">
        <div className="flex-1 min-w-0 overflow-x-auto">
          <div className="flex items-center gap-1 whitespace-nowrap">
            {tabs.map((tab, index) => (
              <React.Fragment key={tab.id}>
                {index === 3 && (
                  <div className="w-px h-5 bg-border mx-1 shrink-0" />
                )}
                <button
                  onClick={() => handleTabChange(tab.id)}
                  className={`relative flex items-center gap-2 px-3 py-2.5 text-sm rounded-t-md transition-colors shrink-0 ${
                    activeTab === tab.id
                      ? 'text-foreground bg-muted/60 border-b-2 border-primary'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
                  }`}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span
                      className={`ml-1 text-xs rounded-full px-1.5 py-0.5 ${
                        activeTab === tab.id
                          ? 'bg-primary/15 text-primary'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              </React.Fragment>
            ))}
          </div>
        </div>
        <button
          onClick={() => {
            void handleRefresh();
          }}
          disabled={refreshing}
          className="inline-flex items-center justify-center gap-2 shrink-0 rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw
            className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
          />
          Refresh
        </button>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {/* Documents Tab */}
        {activeTab === 'documents' && (
          <DocumentList
            documents={projectDocuments}
            loading={documentsLoading}
            onRemove={(documentId) => {
              void handleRemoveDocument(documentId);
            }}
          />
        )}

        {/* Notes Tab */}
        {activeTab === 'notes' && (
          <div>
            <div className="flex justify-end mb-4">
              <button
                onClick={handleCreateNote}
                className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-sm hover:bg-primary/20 transition-colors"
              >
                <Plus className="h-4 w-4" />
                New Note
              </button>
            </div>

            {notesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : (
              <NoteList
                notes={projectNotes}
                selectedTag={selectedNoteTag}
                onTagChange={setSelectedNoteTag}
                onEdit={handleEditNote}
                onDelete={(noteId) => {
                  void handleDeleteNote(noteId);
                }}
                onTogglePin={(noteId) => {
                  void handleTogglePin(noteId);
                }}
              />
            )}
          </div>
        )}

        {/* Bibliography Tab */}
        {activeTab === 'bibliography' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Format:</span>
                <select
                  value={bibFormat}
                  onChange={(e) => {
                    const format = e.target.value as typeof bibFormat;
                    setBibFormat(format);
                    fetchBibliography(projectId, format);
                  }}
                  className="px-3 py-1.5 bg-muted border border-border rounded-md text-sm text-foreground focus:outline-none focus:border-primary"
                >
                  <option value="bibtex">BibTeX</option>
                  <option value="ieee">IEEE</option>
                  <option value="apa">APA</option>
                  <option value="mla">MLA</option>
                </select>
              </div>
              <button
                onClick={handleExportBibliography}
                disabled={!bibliography}
                className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-sm hover:bg-primary/20 transition-colors disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Download
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : bibliography ? (
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-muted-foreground">
                    {bibliography.citation_count} citations
                  </span>
                  <span className="text-xs text-muted-foreground/60">
                    Generated{' '}
                    {new Date(bibliography.generated_at).toLocaleString()}
                  </span>
                </div>
                <pre className="text-sm text-foreground font-mono overflow-x-auto whitespace-pre-wrap max-h-[500px] overflow-y-auto">
                  {bibliography.content}
                </pre>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-border">
                <BookOpen className="h-10 w-10 text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium text-muted-foreground">
                  No bibliography available
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Add documents with extracted citations to generate a
                  bibliography
                </p>
              </div>
            )}
          </div>
        )}

        {/* Drafts Tab */}
        {activeTab === 'drafts' && (
          <div className="space-y-4">
            {/* Show generation progress if active */}
            {generationTaskId && generationStatus && (
              <DraftGenerationProgress
                status={generationStatus}
                onCancel={async () => {
                  await projectService.cancelGeneration(
                    projectId,
                    generationTaskId
                  );
                  setGenerationTaskId(null);
                  setGenerationStatus(null);
                }}
                onComplete={async (draftId) => {
                  setGenerationTaskId(null);
                  setGenerationStatus(null);
                  try {
                    const draft = await projectService.getDraft(
                      projectId,
                      draftId
                    );
                    await loadDrafts(draft.version);
                  } catch (err) {
                    console.error('Failed to load draft:', err);
                    await loadDrafts();
                  }
                }}
              />
            )}

            {/* Show current draft or generator */}
            {!generationTaskId && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* Draft Generator */}
                  <div className="lg:col-span-1 space-y-4">
                    <DraftGenerator
                      loading={draftsLoading}
                      documentCount={projectDocuments.length}
                      onGenerate={async (config) => {
                        setDraftsLoading(true);
                        try {
                          const result = await projectService.generateDraft(
                            projectId,
                            config.themes,
                            {
                              style: config.style,
                              maxSections: config.maxSections,
                              includeAbstract: config.includeAbstract,
                            }
                          );
                          setGenerationTaskId(result.task_id);
                          const pollStatus = async () => {
                            try {
                              const status =
                                await projectService.getGenerationStatus(
                                  projectId,
                                  result.task_id
                                );
                              setGenerationStatus(status);
                              if (
                                !['completed', 'failed', 'cancelled'].includes(
                                  status.status
                                )
                              ) {
                                setTimeout(pollStatus, 1000);
                              }
                            } catch (err) {
                              console.error('Poll error:', err);
                            }
                          };
                          pollStatus();
                        } catch (err) {
                          console.error('Generation failed:', err);
                        } finally {
                          setDraftsLoading(false);
                        }
                      }}
                    />

                    {draftVersions.length > 0 && (
                      <div className="bg-card border border-border rounded-lg p-4">
                        <h3 className="text-sm text-foreground mb-3">
                          Draft Versions
                        </h3>
                        <div className="space-y-2 max-h-[220px] overflow-y-auto">
                          {draftVersions.map((draftVersion) => (
                            <button
                              key={draftVersion.id}
                              onClick={() => {
                                void handleDraftVersionChange(
                                  draftVersion.version
                                );
                              }}
                              className={`w-full text-left px-3 py-2 rounded-md border text-xs transition-colors ${
                                currentDraft?.version === draftVersion.version
                                  ? 'bg-primary/10 border-primary/40 text-primary'
                                  : 'bg-muted border-border text-muted-foreground hover:border-muted-foreground/30'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-mono">
                                  Version {draftVersion.version}
                                </span>
                                {draftVersion.is_current && (
                                  <span className="text-[10px] uppercase tracking-wide text-primary">
                                    Current
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                                {new Date(
                                  draftVersion.created_at
                                ).toLocaleString()}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {draftVersions.length > 1 && (
                      <div className="bg-card border border-border rounded-lg p-4 space-y-3">
                        <h3 className="text-sm text-foreground">
                          Compare Versions
                        </h3>
                        <div className="grid grid-cols-2 gap-2">
                          <select
                            value={compareVersionA ?? ''}
                            onChange={(e) => {
                              setCompareVersionA(Number(e.target.value));
                              setDraftComparison(null);
                              setComparisonDraftA(null);
                              setComparisonDraftB(null);
                            }}
                            className="px-3 py-2 bg-muted border border-border rounded-md text-xs font-mono text-foreground focus:outline-none focus:border-primary"
                          >
                            {draftVersions.map((draftVersion) => (
                              <option
                                key={`a-${draftVersion.id}`}
                                value={draftVersion.version}
                              >
                                v{draftVersion.version}
                              </option>
                            ))}
                          </select>
                          <select
                            value={compareVersionB ?? ''}
                            onChange={(e) => {
                              setCompareVersionB(Number(e.target.value));
                              setDraftComparison(null);
                              setComparisonDraftA(null);
                              setComparisonDraftB(null);
                            }}
                            className="px-3 py-2 bg-muted border border-border rounded-md text-xs font-mono text-foreground focus:outline-none focus:border-primary"
                          >
                            {draftVersions.map((draftVersion) => (
                              <option
                                key={`b-${draftVersion.id}`}
                                value={draftVersion.version}
                              >
                                v{draftVersion.version}
                              </option>
                            ))}
                          </select>
                        </div>
                        <button
                          onClick={() => {
                            void handleCompareDrafts();
                          }}
                          disabled={
                            comparisonLoading ||
                            compareVersionA === null ||
                            compareVersionB === null ||
                            compareVersionA === compareVersionB
                          }
                          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-xs hover:bg-primary/20 transition-colors disabled:opacity-50"
                        >
                          {comparisonLoading && (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          )}
                          Compare Drafts
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Draft Viewer */}
                  <div className="lg:col-span-2">
                    {currentDraft ? (
                      <DraftViewer
                        draft={currentDraft}
                        versions={draftVersions.map((draftVersion) => ({
                          version: draftVersion.version,
                          created_at: draftVersion.created_at,
                        }))}
                        onVersionChange={(version) => {
                          void handleDraftVersionChange(version);
                        }}
                        onExport={async (format) => {
                          setExportInitialFormat(format);
                          setShowExportModal(true);
                        }}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-border">
                        <Sparkles className="h-10 w-10 text-muted-foreground/40 mb-3" />
                        <p className="text-sm font-medium text-muted-foreground">
                          No draft generated yet
                        </p>
                        <p className="text-xs text-muted-foreground/60 mt-1">
                          Configure themes and generate a literature review
                          draft
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {draftComparison && (
                  <DraftComparison
                    comparison={draftComparison}
                    draftA={
                      comparisonDraftA
                        ? { content: comparisonDraftA.content }
                        : undefined
                    }
                    draftB={
                      comparisonDraftB
                        ? { content: comparisonDraftB.content }
                        : undefined
                    }
                  />
                )}
              </div>
            )}
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && <ProjectChatTab projectId={projectId} />}

        {/* Matrix Tab */}
        {activeTab === 'matrix' && (
          <ExtractionMatrix
            projectId={projectId}
            matrixId={matrixId ?? undefined}
            documents={projectDocuments.map((doc) => ({
              id: doc.document_id,
              title:
                doc.document?.title || doc.document?.filename || 'Untitled',
            }))}
          />
        )}

        {/* Pipeline Tab */}
        {activeTab === 'pipeline' && <ResearchPipeline projectId={projectId} />}

        {/* Knowledge Tab */}
        {activeTab === 'knowledge' && (
          <ProjectKnowledgeTree projectId={projectId} />
        )}
      </div>

      <NoteEditor
        isOpen={showNoteEditor}
        initialNote={editingNote}
        availableDocuments={projectDocuments}
        onClose={() => {
          setShowNoteEditor(false);
          setEditingNote(null);
        }}
        onSave={handleSaveNote}
      />

      {currentDraft && (
        <DraftExportModal
          isOpen={showExportModal}
          onClose={() => setShowExportModal(false)}
          draftTitle={currentDraft.title}
          initialFormat={exportInitialFormat}
          onExport={async (format, includeBibliography, bibliographyFormat) => {
            await projectService.downloadDraftExport(
              projectId,
              currentDraft.id,
              format,
              includeBibliography,
              bibliographyFormat
            );
          }}
        />
      )}
    </div>
  );
}
