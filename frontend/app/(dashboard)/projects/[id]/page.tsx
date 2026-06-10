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
  Upload,
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
import { DocumentUploadWizard } from '@/components/upload';
import {
  projectService,
  type Draft,
  type DraftComparison as DraftComparisonData,
  type GenerationStatus,
} from '@/services/projectService';
import { useProjectStore } from '@/store/projectStore';
import { useAgentChatStore } from '@/store/agentChatStore';
import { useAuthStore } from '@/stores/authStore';
import { APIErrorClass } from '@/types/api';
import type { ProjectNote, ProjectNoteCreate } from '@/services/projectService';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

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
  const pollTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const [showUploadWizard, setShowUploadWizard] = useState(false);
  const [pendingNoteDelete, setPendingNoteDelete] = useState<{
    id: string;
    title: string;
  } | null>(null);
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

  // Clean up draft generation polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

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
      if (tab === 'bibliography') {
        fetchBibliography(projectId, bibFormat);
      }
    },
    [projectId, bibFormat, fetchBibliography]
  );

  // WAI-ARIA tablist keyboard navigation: ArrowLeft/Right moves between tabs,
  // Home/End jumps to first/last. Activates the focused tab.
  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
      const tabIds = tabs.map((t) => t.id);
      let nextIndex: number | null = null;
      if (event.key === 'ArrowRight') {
        nextIndex = (index + 1) % tabIds.length;
      } else if (event.key === 'ArrowLeft') {
        nextIndex = (index - 1 + tabIds.length) % tabIds.length;
      } else if (event.key === 'Home') {
        nextIndex = 0;
      } else if (event.key === 'End') {
        nextIndex = tabIds.length - 1;
      }
      if (nextIndex !== null) {
        event.preventDefault();
        const nextId = tabIds[nextIndex];
        handleTabChange(nextId);
        // Move focus to the newly selected tab
        const nextButton = document.getElementById(`project-tab-${nextId}`);
        nextButton?.focus();
      }
    },
    // tabs array is rebuilt on every render; rely on closure capture
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [handleTabChange]
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

  const handleDeleteNote = (noteId: string) => {
    const note = projectNotes.find((n) => n.id === noteId);
    if (!note) return;
    setPendingNoteDelete({ id: noteId, title: note.title || 'Untitled note' });
  };

  const confirmDeleteNote = async () => {
    if (!pendingNoteDelete) return;
    try {
      await deleteNote(projectId, pendingNoteDelete.id);
    } catch (err) {
      console.error('Failed to delete note:', err);
    } finally {
      setPendingNoteDelete(null);
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

  const handleUploadComplete = useCallback(
    async (documentIds: string[]) => {
      setShowUploadWizard(false);
      try {
        await Promise.all(
          documentIds.map((docId) =>
            projectService.addDocumentToProject(projectId, docId)
          )
        );
        await fetchProjectDocuments(projectId);
      } catch {
        // linking may partially fail, still refresh to show what succeeded
        await fetchProjectDocuments(projectId);
      }
    },
    [projectId, fetchProjectDocuments]
  );

  if (!mounted || initialLoading) {
    return (
      <div
        role="status"
        aria-busy="true"
        aria-label="Loading project"
        className="p-3 sm:p-6 pb-20 md:pb-6 max-w-7xl mx-auto"
      >
        <div className="mb-4 sm:mb-8 space-y-3 sm:space-y-4">
          <div className="h-4 w-20 rounded-md bg-muted animate-pulse" />
          <div className="rounded-xl border border-border bg-card p-4 sm:p-6 space-y-3">
            <div className="h-6 w-1/2 rounded-md bg-muted animate-pulse" />
            <div className="h-4 w-3/4 rounded-md bg-muted animate-pulse" />
            <div className="h-3 w-40 rounded-md bg-muted animate-pulse" />
          </div>
        </div>
        <div className="flex gap-2 border-b border-border pb-2 mb-6">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-8 w-20 rounded-md bg-muted animate-pulse"
            />
          ))}
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-lg border border-border bg-card animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (projectError) {
    const isNotFound = projectError.status === 404;
    return (
      <div
        role="alert"
        className="mx-auto mt-10 max-w-md rounded-xl border border-border bg-card p-6 text-center"
      >
        <p className="text-base font-medium text-foreground">
          {isNotFound ? 'Project not found' : 'Could not load this project'}
        </p>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {isNotFound
            ? 'It may have been deleted or you may not have access.'
            : projectError.message}
        </p>
        <div className="mt-5 flex items-center justify-center gap-3">
          {!isNotFound && (
            <button
              onClick={() => {
                setInitialLoading(true);
                setProjectError(null);
                fetchProject(projectId)
                  .then(() => setProjectError(null))
                  .catch((err: unknown) => {
                    const status =
                      err instanceof APIErrorClass
                        ? err.error.status_code
                        : 500;
                    const message =
                      err instanceof Error
                        ? err.message
                        : 'Failed to load project';
                    setProjectError({ status, message });
                  })
                  .finally(() => setInitialLoading(false));
              }}
              className="inline-flex items-center rounded-md bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              Try again
            </button>
          )}
          <button
            onClick={() => router.push('/projects')}
            className="inline-flex items-center rounded-md border border-border bg-card px-3.5 py-2 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Back to projects
          </button>
        </div>
      </div>
    );
  }

  if (!currentProject) {
    return (
      <div className="mx-auto mt-10 max-w-md rounded-xl border border-border bg-card p-6 text-center">
        <p className="text-base font-medium text-foreground">
          Project not found
        </p>
        <p className="mt-1.5 text-sm text-muted-foreground">
          It may have been deleted or you may not have access.
        </p>
        <button
          onClick={() => router.push('/projects')}
          className="mt-5 inline-flex items-center rounded-md border border-border bg-card px-3.5 py-2 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Back to projects
        </button>
      </div>
    );
  }

  const tabs: Array<{
    id: TabType;
    label: string;
    shortLabel: string;
    icon: React.ElementType;
    count?: number;
  }> = [
    {
      id: 'documents',
      label: 'Documents',
      shortLabel: 'Docs',
      icon: FileText,
      count: projectDocuments.length,
    },
    {
      id: 'notes',
      label: 'Notes',
      shortLabel: 'Notes',
      icon: StickyNote,
      count: projectNotes.length,
    },
    { id: 'bibliography', label: 'Bibliography', shortLabel: 'Bibs', icon: BookOpen },
    {
      id: 'drafts',
      label: 'Drafts',
      shortLabel: 'Drafts',
      icon: Sparkles,
      count: draftVersions.length || undefined,
    },
    { id: 'chat', label: 'Chat', shortLabel: 'Chat', icon: MessageSquare },
    { id: 'matrix', label: 'Matrix', shortLabel: 'Matrix', icon: Grid3X3 },
    { id: 'pipeline', label: 'Pipeline', shortLabel: 'Steps', icon: GitBranch },
    { id: 'knowledge', label: 'Knowledge', shortLabel: 'Graph', icon: Network },
  ];

  return (
    <div className="p-3 sm:p-6 pb-20 md:pb-6 max-w-7xl mx-auto">
      {/* Header */}
      <ProjectHeader project={currentProject} />

      {/* Error Display */}
      {error && (
        <div
          role="alert"
          className="mb-6 p-4 bg-destructive/10 border border-destructive/30 rounded-lg"
        >
          <p className="text-destructive text-sm">{error}</p>
          <button
            onClick={clearError}
            className="mt-2 text-xs text-destructive underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-3 sm:mb-6 border-b border-border pb-2">
        <div className="flex items-center gap-2 mb-2 sm:mb-0 sm:float-right">
          <button
            onClick={() => setShowUploadWizard(true)}
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-2.5 py-1.5 sm:px-3 sm:py-2 text-xs sm:text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Upload aria-hidden="true" className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            Upload
          </button>
          <button
            onClick={() => {
              void handleRefresh();
            }}
            disabled={refreshing}
            aria-label={refreshing ? 'Refreshing project' : 'Refresh project'}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 sm:px-3 sm:py-2 text-xs sm:text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <RefreshCw
              aria-hidden="true"
              className={`h-3.5 w-3.5 sm:h-4 sm:w-4 ${refreshing ? 'animate-spin' : ''}`}
            />
            Refresh
          </button>
        </div>
        <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
          <div
            role="tablist"
            aria-label="Project sections"
            className="flex items-center gap-0.5 sm:gap-1 whitespace-nowrap"
          >
            {tabs.map((tab, index) => {
              const isActive = activeTab === tab.id;
              return (
                <React.Fragment key={tab.id}>
                  {index === 3 && (
                    <div
                      role="separator"
                      aria-orientation="vertical"
                      className="w-px h-4 bg-border mx-0.5 sm:mx-1 shrink-0"
                    />
                  )}
                  <button
                    role="tab"
                    id={`project-tab-${tab.id}`}
                    aria-selected={isActive}
                    aria-controls={`project-tabpanel-${tab.id}`}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => handleTabChange(tab.id)}
                    onKeyDown={(e) => handleTabKeyDown(e, index)}
                    className={`relative flex items-center gap-1 sm:gap-2 px-2 py-2 sm:px-3 sm:py-2.5 text-xs sm:text-sm rounded-t-md transition-colors shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                      isActive
                        ? 'text-foreground bg-muted/60 border-b-2 border-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
                    }`}
                  >
                    <tab.icon
                      aria-hidden="true"
                      className="h-3.5 w-3.5 sm:h-4 sm:w-4"
                    />
                    <span className="hidden sm:inline">{tab.label}</span>
                    <span className="sm:hidden">{tab.shortLabel}</span>
                    {tab.count !== undefined && tab.count > 0 && (
                      <span
                        aria-label={`${tab.count} items`}
                        className={`ml-0.5 sm:ml-1 text-[10px] sm:text-xs rounded-full px-1 sm:px-1.5 py-0.5 ${
                          isActive
                            ? 'bg-primary/15 text-primary'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {tab.count}
                      </span>
                    )}
                  </button>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tab Content */}
      <div
        className="min-h-[200px] sm:min-h-[400px]"
        role="tabpanel"
        id={`project-tabpanel-${activeTab}`}
        aria-labelledby={`project-tab-${activeTab}`}
      >
        {/* Heading for each tab panel (visually hidden, exposed to screen readers) */}
        <h2 className="sr-only">
          {tabs.find((t) => t.id === activeTab)?.label}
        </h2>
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
                className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-sm font-medium hover:bg-primary/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Plus aria-hidden="true" className="h-4 w-4" />
                New note
              </button>
            </div>

            {notesLoading ? (
              <div
                role="status"
                aria-busy="true"
                aria-label="Loading notes"
                className="grid grid-cols-1 sm:grid-cols-2 gap-3"
              >
                {Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-border bg-card p-4 space-y-3"
                  >
                    <div className="h-4 w-2/3 rounded-md bg-muted animate-pulse" />
                    <div className="h-3 w-full rounded-md bg-muted animate-pulse" />
                    <div className="h-3 w-4/5 rounded-md bg-muted animate-pulse" />
                  </div>
                ))}
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
                  aria-label="Citation format"
                  onChange={(e) => {
                    const format = e.target.value as typeof bibFormat;
                    setBibFormat(format);
                    fetchBibliography(projectId, format);
                  }}
                  className="px-3 py-1.5 bg-muted border border-border rounded-md text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
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
                className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-sm font-medium hover:bg-primary/20 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Download aria-hidden="true" className="h-4 w-4" />
                Download
              </button>
            </div>

            {loading ? (
              <div
                role="status"
                aria-busy="true"
                aria-label="Loading bibliography"
                className="rounded-lg border border-border bg-card p-4 space-y-2"
              >
                <div className="h-3 w-32 rounded-md bg-muted animate-pulse mb-4" />
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-3 rounded-md bg-muted animate-pulse"
                    style={{ width: `${90 - (i % 3) * 18}%` }}
                  />
                ))}
              </div>
            ) : bibliography ? (
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-muted-foreground">
                    {bibliography.citation_count} citations
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Generated{' '}
                    {new Date(bibliography.generated_at).toLocaleString()}
                  </span>
                </div>
                <pre className="text-sm text-foreground font-[var(--nous-font-mono)] overflow-x-auto whitespace-pre-wrap max-h-[500px] overflow-y-auto rounded-md bg-muted/40 p-3">
                  {bibliography.content}
                </pre>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-border">
                <BookOpen
                  aria-hidden="true"
                  className="h-10 w-10 text-muted-foreground/50 mb-3"
                />
                <p className="text-sm font-medium text-foreground">
                  No bibliography yet
                </p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm text-center">
                  Add documents with extracted citations, then a bibliography
                  will be generated here.
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
                  if (pollTimeoutRef.current)
                    clearTimeout(pollTimeoutRef.current);
                  await projectService.cancelGeneration(
                    projectId,
                    generationTaskId
                  );
                  setGenerationTaskId(null);
                  setGenerationStatus(null);
                }}
                onComplete={async (draftId) => {
                  if (pollTimeoutRef.current)
                    clearTimeout(pollTimeoutRef.current);
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
                                pollTimeoutRef.current = setTimeout(
                                  pollStatus,
                                  1000
                                );
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
                        <h3 className="text-sm font-medium text-foreground mb-3">
                          Draft versions
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
                              className={`w-full text-left px-3 py-2 rounded-md border text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                                currentDraft?.version === draftVersion.version
                                  ? 'bg-primary/10 border-primary/40 text-primary'
                                  : 'bg-muted border-border text-muted-foreground hover:border-muted-foreground/30'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium tabular-nums">
                                  Version {draftVersion.version}
                                </span>
                                {draftVersion.is_current && (
                                  <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                                    Current
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-muted-foreground mt-1 tabular-nums">
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
                        <h3 className="text-sm font-medium text-foreground">
                          Compare versions
                        </h3>
                        <div className="grid grid-cols-2 gap-2">
                          <select
                            value={compareVersionA ?? ''}
                            aria-label="First version to compare"
                            onChange={(e) => {
                              setCompareVersionA(Number(e.target.value));
                              setDraftComparison(null);
                              setComparisonDraftA(null);
                              setComparisonDraftB(null);
                            }}
                            className="px-3 py-2 bg-muted border border-border rounded-md text-xs tabular-nums text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
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
                            aria-label="Second version to compare"
                            onChange={(e) => {
                              setCompareVersionB(Number(e.target.value));
                              setDraftComparison(null);
                              setComparisonDraftA(null);
                              setComparisonDraftB(null);
                            }}
                            className="px-3 py-2 bg-muted border border-border rounded-md text-xs tabular-nums text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
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
                          aria-busy={comparisonLoading}
                          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-xs font-medium hover:bg-primary/20 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        >
                          {comparisonLoading && (
                            <Loader2
                              aria-hidden="true"
                              className="h-3.5 w-3.5 animate-spin"
                            />
                          )}
                          {comparisonLoading ? 'Comparing…' : 'Compare drafts'}
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
                        <Sparkles
                          aria-hidden="true"
                          className="h-10 w-10 text-muted-foreground/50 mb-3"
                        />
                        <p className="text-sm font-medium text-foreground">
                          No draft yet
                        </p>
                        <p className="text-xs text-muted-foreground mt-1 max-w-sm text-center">
                          Choose your themes on the left, then generate a
                          literature review draft.
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

      <DocumentUploadWizard
        isOpen={showUploadWizard}
        onClose={() => setShowUploadWizard(false)}
        onComplete={handleUploadComplete}
      />

      <ConfirmDialog
        open={pendingNoteDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingNoteDelete(null);
        }}
        title={`Delete note "${pendingNoteDelete?.title ?? ''}"?`}
        description="This action cannot be undone. This will permanently delete the note and any links to project documents."
        confirmLabel="Delete note"
        variant="destructive"
        onConfirm={confirmDeleteNote}
      />
    </div>
  );
}
