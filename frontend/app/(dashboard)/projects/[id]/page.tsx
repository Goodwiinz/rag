'use client';

/**
 * Project Detail Page
 * Displays project information with tabs for Documents, Notes, and Bibliography
 */

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  FileText,
  StickyNote,
  BookOpen,
  Sparkles,
  Plus,
  Trash2,
  Download,
  Loader2,
  MessageSquare,
  Grid3X3,
} from 'lucide-react';
import { DraftGenerator } from '@/components/research/DraftGenerator';
import { DraftViewer } from '@/components/research/DraftViewer';
import { DraftGenerationProgress } from '@/components/research/DraftGenerationProgress';
import { DraftComparison } from '@/components/research/DraftComparison';
import { DraftExportModal } from '@/components/research/DraftExportModal';
import { ProjectChatTab } from '@/components/research/ProjectChatTab';
import { ExtractionMatrix } from '@/components/research/ExtractionMatrix';
import { NoteEditor } from '@/components/research/NoteEditor';
import { NoteList } from '@/components/research/NoteList';
import {
  projectService,
  type Draft,
  type DraftComparison as DraftComparisonData,
  type GenerationStatus,
} from '@/services/projectService';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/stores/authStore';
import type { ProjectNote, ProjectNoteCreate } from '@/services/projectService';

type TabType =
  | 'documents'
  | 'notes'
  | 'bibliography'
  | 'drafts'
  | 'chat'
  | 'matrix';

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

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && isAuthenticated && projectId) {
      fetchProject(projectId);
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
    if (!confirm('Remove this document from the project?')) return;
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

  if (!mounted || loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-[#00ff9f]" />
      </div>
    );
  }

  if (!currentProject) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-400 font-mono">Project not found</p>
        <button
          onClick={() => router.push('/projects')}
          className="mt-4 text-[#00ff9f] underline font-mono text-sm"
        >
          Back to projects
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => router.push('/projects')}
          className="flex items-center gap-2 text-gray-400 hover:text-[#00ff9f] font-mono text-sm mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Projects
        </button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-mono font-bold text-[#00ff9f]">
              {currentProject.name}
            </h1>
            {currentProject.description && (
              <p className="text-gray-400 mt-2">{currentProject.description}</p>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500 font-mono">
            <span>{currentProject.document_count || 0} documents</span>
            <span>{currentProject.citation_count || 0} citations</span>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-red-400 font-mono text-sm">{error}</p>
          <button
            onClick={clearError}
            className="mt-2 text-xs text-red-400 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-[#1a1a1a]">
        <button
          onClick={() => handleTabChange('documents')}
          className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
            activeTab === 'documents'
              ? 'text-[#00ff9f] border-[#00ff9f]'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          <FileText className="h-4 w-4" />
          Documents
        </button>
        <button
          onClick={() => handleTabChange('notes')}
          className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
            activeTab === 'notes'
              ? 'text-[#00ff9f] border-[#00ff9f]'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          <StickyNote className="h-4 w-4" />
          Notes
        </button>
        <button
          onClick={() => handleTabChange('bibliography')}
          className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
            activeTab === 'bibliography'
              ? 'text-[#00ff9f] border-[#00ff9f]'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          <BookOpen className="h-4 w-4" />
          Bibliography
        </button>
        <button
          onClick={() => handleTabChange('drafts')}
          className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
            activeTab === 'drafts'
              ? 'text-[#00ff9f] border-[#00ff9f]'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          <Sparkles className="h-4 w-4" />
          Drafts
        </button>
        <button
          onClick={() => handleTabChange('chat')}
          className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
            activeTab === 'chat'
              ? 'text-[#00ff9f] border-[#00ff9f]'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          Chat
        </button>
        <button
          onClick={() => handleTabChange('matrix')}
          className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
            activeTab === 'matrix'
              ? 'text-[#00ff9f] border-[#00ff9f]'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          <Grid3X3 className="h-4 w-4" />
          Matrix
        </button>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {/* Documents Tab */}
        {activeTab === 'documents' && (
          <div>
            {documentsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
              </div>
            ) : projectDocuments.length === 0 ? (
              <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
                <FileText className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 font-mono">
                  No documents in this project
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  Add documents from the Documents page
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {projectDocuments.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-4 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg hover:border-[#333] transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-[#00ff9f]" />
                      <div>
                        <p className="font-mono text-gray-200">
                          {doc.document?.title ||
                            doc.document?.filename ||
                            'Untitled'}
                        </p>
                        <p className="text-xs text-gray-500 font-mono">
                          Added{' '}
                          {new Date(
                            doc.added_at ||
                              doc.document?.created_at ||
                              Date.now()
                          ).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRemoveDocument(doc.document_id)}
                      className="p-2 text-gray-500 hover:text-red-400 transition-colors"
                      title="Remove from project"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Notes Tab */}
        {activeTab === 'notes' && (
          <div>
            <div className="flex justify-end mb-4">
              <button
                onClick={handleCreateNote}
                className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors"
              >
                <Plus className="h-4 w-4" />
                New Note
              </button>
            </div>

            {notesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
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
                <span className="text-sm text-gray-500 font-mono">Format:</span>
                <select
                  value={bibFormat}
                  onChange={(e) => {
                    const format = e.target.value as typeof bibFormat;
                    setBibFormat(format);
                    fetchBibliography(projectId, format);
                  }}
                  className="px-3 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
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
                className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Download
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
              </div>
            ) : bibliography ? (
              <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-gray-500 font-mono">
                    {bibliography.citation_count} citations
                  </span>
                  <span className="text-xs text-gray-600 font-mono">
                    Generated{' '}
                    {new Date(bibliography.generated_at).toLocaleString()}
                  </span>
                </div>
                <pre className="text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-[500px] overflow-y-auto">
                  {bibliography.content}
                </pre>
              </div>
            ) : (
              <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
                <BookOpen className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 font-mono">
                  No bibliography available
                </p>
                <p className="text-sm text-gray-500 mt-2">
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
                          // Poll for status
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
                      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
                        <h3 className="text-sm font-mono text-gray-300 mb-3">
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
                              className={`w-full text-left px-3 py-2 rounded border font-mono text-xs transition-colors ${
                                currentDraft?.version === draftVersion.version
                                  ? 'bg-[#00ff9f]/10 border-[#00ff9f]/40 text-[#00ff9f]'
                                  : 'bg-[#1a1a1a] border-[#333] text-gray-400 hover:border-[#555]'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span>Version {draftVersion.version}</span>
                                {draftVersion.is_current && (
                                  <span className="text-[10px] uppercase tracking-wide text-[#00ff9f]">
                                    Current
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-gray-500 mt-1">
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
                      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4 space-y-3">
                        <h3 className="text-sm font-mono text-gray-300">
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
                            className="px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
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
                            className="px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
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
                          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-xs hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50"
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
                      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-12 text-center">
                        <Sparkles className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                        <p className="text-gray-400 font-mono">
                          No draft generated yet
                        </p>
                        <p className="text-sm text-gray-500 mt-2">
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
