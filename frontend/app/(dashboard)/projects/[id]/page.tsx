'use client';

/**
 * Project Detail Page
 * Displays project information with tabs for Documents, Notes, Bibliography, Drafts, and Chat
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
  Pin,
  PinOff,
  Edit2,
  Download,
  Loader2,
  Save,
  X,
  MessageSquare,
  GitCompare,
} from 'lucide-react';
import { DraftGenerator, type GenerationConfig } from '@/components/research/DraftGenerator';
import { DraftViewer } from '@/components/research/DraftViewer';
import { DraftGenerationProgress } from '@/components/research/DraftGenerationProgress';
import { DraftComparison } from '@/components/research/DraftComparison';
import { DraftExportModal } from '@/components/research/DraftExportModal';
import { ProjectChatTab } from '@/components/research/ProjectChatTab';
import {
  projectService,
  type Draft,
  type GenerationStatus,
  type DraftComparison as DraftComparisonType,
} from '@/services/projectService';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/stores/authStore';
import type { ProjectNote, ProjectNoteCreate } from '@/services/projectService';

type TabType = 'documents' | 'notes' | 'bibliography' | 'drafts' | 'chat';

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
  const [bibFormat, setBibFormat] = useState<'bibtex' | 'ieee' | 'apa' | 'mla'>('bibtex');

  // Draft state
  const [currentDraft, setCurrentDraft] = useState<Draft | null>(null);
  const [draftVersions, setDraftVersions] = useState<
    Array<{ version: number; created_at: string; id: string; word_count: number; citation_count: number; themes: string[] }>
  >([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [generationTaskId, setGenerationTaskId] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState<GenerationStatus | null>(null);

  // Comparison state
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonData, setComparisonData] = useState<DraftComparisonType | null>(null);
  const [compareVersions, setCompareVersions] = useState<[number, number] | null>(null);

  // Export modal state
  const [showExportModal, setShowExportModal] = useState(false);

  // Note editing state
  const [editingNote, setEditingNote] = useState<ProjectNote | null>(null);
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && isAuthenticated && projectId) {
      fetchProject(projectId);
      fetchProjectDocuments(projectId);
      fetchProjectNotes(projectId);
    }
  }, [mounted, isAuthenticated, projectId, fetchProject, fetchProjectDocuments, fetchProjectNotes]);

  // Load drafts when the Drafts tab is activated
  const loadDrafts = useCallback(async () => {
    if (!projectId) return;
    setDraftsLoading(true);
    try {
      const [listResult, currentResult] = await Promise.allSettled([
        projectService.listDrafts(projectId),
        projectService.getCurrentDraft(projectId),
      ]);

      if (listResult.status === 'fulfilled') {
        setDraftVersions(
          listResult.value.drafts.map((d) => ({
            version: d.version,
            created_at: d.created_at,
            id: d.id,
            word_count: d.word_count,
            citation_count: d.citation_count,
            themes: d.themes,
          }))
        );
      }

      if (currentResult.status === 'fulfilled') {
        setCurrentDraft(currentResult.value);
      }
    } catch (err) {
      console.error('Failed to load drafts:', err);
    } finally {
      setDraftsLoading(false);
    }
  }, [projectId]);

  const handleTabChange = useCallback(
    (tab: TabType) => {
      setActiveTab(tab);
      if (tab === 'bibliography' && !bibliography) {
        fetchBibliography(projectId, bibFormat);
      }
      if (tab === 'drafts') {
        loadDrafts();
      }
    },
    [projectId, bibliography, bibFormat, fetchBibliography, loadDrafts]
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
    setNoteTitle('');
    setNoteContent('');
    setShowNoteEditor(true);
  };

  const handleEditNote = (note: ProjectNote) => {
    setEditingNote(note);
    setNoteTitle(note.title);
    setNoteContent(note.content);
    setShowNoteEditor(true);
  };

  const handleSaveNote = async () => {
    if (!noteTitle.trim()) return;

    setSavingNote(true);
    try {
      if (editingNote) {
        await updateNote(projectId, editingNote.id, {
          title: noteTitle.trim(),
          content: noteContent,
        });
      } else {
        await createNote(projectId, {
          title: noteTitle.trim(),
          content: noteContent,
        });
      }
      setShowNoteEditor(false);
      setEditingNote(null);
      setNoteTitle('');
      setNoteContent('');
    } catch (err) {
      console.error('Failed to save note:', err);
    } finally {
      setSavingNote(false);
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

  // Draft version switching
  const handleVersionChange = async (version: number) => {
    const versionInfo = draftVersions.find((v) => v.version === version);
    if (!versionInfo) return;
    try {
      const draft = await projectService.getDraft(projectId, versionInfo.id);
      setCurrentDraft(draft);
    } catch (err) {
      console.error('Failed to load version:', err);
    }
  };

  // Draft comparison
  const handleCompare = async (versionA: number, versionB: number) => {
    try {
      const result = await projectService.compareDrafts(projectId, versionA, versionB);
      setComparisonData(result);
      setCompareVersions([versionA, versionB]);
      setShowComparison(true);
    } catch (err) {
      console.error('Failed to compare drafts:', err);
    }
  };

  // Draft export via modal
  const handleExportDraft = async (format: 'markdown' | 'latex', includeBibliography: boolean) => {
    if (!currentDraft) return;
    try {
      const result = await projectService.exportDraft(
        projectId,
        currentDraft.id,
        format,
        includeBibliography
      );

      if (format === 'latex' && result.files) {
        // Download each file for LaTeX
        for (const file of result.files) {
          const blob = new Blob([file.content], { type: file.mime_type });
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = file.filename;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
        }
      } else {
        const content = result.content || '';
        const blob = new Blob([content], { type: result.mime_type || 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = result.filename || `draft.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Export failed:', err);
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
          <button onClick={clearError} className="mt-2 text-xs text-red-400 underline">
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
                <p className="text-gray-400 font-mono">No documents in this project</p>
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
                          {doc.document?.title || doc.document?.filename || 'Untitled'}
                        </p>
                        <p className="text-xs text-gray-500 font-mono">
                          Added {new Date(doc.added_at).toLocaleDateString()}
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
            ) : projectNotes.length === 0 ? (
              <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
                <StickyNote className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 font-mono">No notes yet</p>
                <p className="text-sm text-gray-500 mt-2">
                  Create notes to organize your research
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Pinned notes first */}
                {projectNotes
                  .sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0))
                  .map((note) => (
                    <div
                      key={note.id}
                      className={`p-4 bg-[#0a0a0a] border rounded-lg ${
                        note.is_pinned ? 'border-[#ffb700]/50' : 'border-[#1a1a1a]'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {note.is_pinned && (
                            <Pin className="h-4 w-4 text-[#ffb700]" />
                          )}
                          <h3 className="font-mono font-medium text-gray-200">
                            {note.title}
                          </h3>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleTogglePin(note.id)}
                            className="p-1.5 text-gray-500 hover:text-[#ffb700] transition-colors"
                            title={note.is_pinned ? 'Unpin' : 'Pin'}
                          >
                            {note.is_pinned ? (
                              <PinOff className="h-4 w-4" />
                            ) : (
                              <Pin className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            onClick={() => handleEditNote(note)}
                            className="p-1.5 text-gray-500 hover:text-[#00ff9f] transition-colors"
                            title="Edit"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteNote(note.id)}
                            className="p-1.5 text-gray-500 hover:text-red-400 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                      <p className="text-sm text-gray-400 line-clamp-3 whitespace-pre-wrap">
                        {note.content}
                      </p>
                      <p className="text-xs text-gray-600 font-mono mt-2">
                        Updated {new Date(note.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                  ))}
              </div>
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
                    Generated {new Date(bibliography.generated_at).toLocaleString()}
                  </span>
                </div>
                <pre className="text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-[500px] overflow-y-auto">
                  {bibliography.content}
                </pre>
              </div>
            ) : (
              <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
                <BookOpen className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 font-mono">No bibliography available</p>
                <p className="text-sm text-gray-500 mt-2">
                  Add documents with extracted citations to generate a bibliography
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
                  await projectService.cancelGeneration(projectId, generationTaskId);
                  setGenerationTaskId(null);
                  setGenerationStatus(null);
                }}
                onComplete={async (draftId) => {
                  setGenerationTaskId(null);
                  setGenerationStatus(null);
                  // Reload drafts
                  await loadDrafts();
                }}
              />
            )}

            {/* Show comparison view */}
            {showComparison && comparisonData && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-mono font-medium text-gray-200">Version Comparison</h3>
                  <button
                    onClick={() => setShowComparison(false)}
                    className="px-3 py-1.5 text-xs font-mono text-gray-400 hover:text-gray-200 border border-[#333] rounded hover:border-[#555] transition-colors"
                  >
                    Close
                  </button>
                </div>
                <DraftComparison comparison={comparisonData} />
              </div>
            )}

            {/* Main drafts area */}
            {!generationTaskId && !showComparison && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Draft Generator */}
                <div className="lg:col-span-1 space-y-4">
                  <DraftGenerator
                    loading={draftsLoading}
                    documentCount={projectDocuments.length}
                    onGenerate={async (config) => {
                      setDraftsLoading(true);
                      try {
                        const result = await projectService.generateDraft(projectId, config.themes, {
                          style: config.style,
                          maxSections: config.maxSections,
                          includeAbstract: config.includeAbstract,
                        });
                        setGenerationTaskId(result.task_id);
                        // Poll for status
                        const pollStatus = async () => {
                          try {
                            const status = await projectService.getGenerationStatus(projectId, result.task_id);
                            setGenerationStatus(status);
                            if (!['completed', 'failed', 'cancelled'].includes(status.status)) {
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

                  {/* Version History List */}
                  {draftVersions.length > 0 && (
                    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
                      <h4 className="font-mono font-medium text-gray-200 mb-3 text-sm">
                        Version History
                      </h4>
                      <div className="space-y-2">
                        {draftVersions.map((v) => (
                          <div
                            key={v.version}
                            className={`p-3 rounded border cursor-pointer transition-colors ${
                              currentDraft?.version === v.version
                                ? 'bg-[#00ff9f]/5 border-[#00ff9f]/30'
                                : 'bg-[#1a1a1a] border-[#333] hover:border-[#555]'
                            }`}
                            onClick={() => handleVersionChange(v.version)}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-mono text-gray-200">
                                v{v.version}
                              </span>
                              <span className="text-xs text-gray-500 font-mono">
                                {new Date(v.created_at).toLocaleDateString()}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-gray-500 font-mono">
                              <span>{v.word_count} words</span>
                              <span>{v.citation_count} citations</span>
                            </div>
                            {v.themes && v.themes.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-2">
                                {v.themes.slice(0, 3).map((theme, idx) => (
                                  <span
                                    key={idx}
                                    className="px-1.5 py-0.5 bg-[#00ff9f]/5 text-[#00ff9f] text-[10px] font-mono rounded"
                                  >
                                    {theme}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Compare Button */}
                      {draftVersions.length >= 2 && (
                        <button
                          onClick={() => {
                            const versions = draftVersions.map((v) => v.version).sort((a, b) => b - a);
                            handleCompare(versions[1], versions[0]);
                          }}
                          className="w-full mt-3 flex items-center justify-center gap-2 px-3 py-2 bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30 rounded font-mono text-xs hover:bg-[#00d4ff]/20 transition-colors"
                        >
                          <GitCompare className="h-3 w-3" />
                          Compare Latest Versions
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Draft Viewer */}
                <div className="lg:col-span-2">
                  {currentDraft ? (
                    <DraftViewer
                      draft={currentDraft}
                      versions={draftVersions.map((v) => ({
                        version: v.version,
                        created_at: v.created_at,
                      }))}
                      onVersionChange={handleVersionChange}
                      onExport={() => setShowExportModal(true)}
                    />
                  ) : draftsLoading ? (
                    <div className="flex items-center justify-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
                      <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
                    </div>
                  ) : (
                    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-12 text-center">
                      <Sparkles className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                      <p className="text-gray-400 font-mono">No draft generated yet</p>
                      <p className="text-sm text-gray-500 mt-2">
                        Configure themes and generate a literature review draft
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Export Modal */}
            {currentDraft && (
              <DraftExportModal
                isOpen={showExportModal}
                onClose={() => setShowExportModal(false)}
                onExport={handleExportDraft}
                draftTitle={currentDraft.title}
              />
            )}
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <ProjectChatTab projectId={projectId} />
        )}
      </div>

      {/* Note Editor Modal */}
      {showNoteEditor && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
              <h2 className="text-lg font-mono font-bold text-[#00ff9f]">
                {editingNote ? 'Edit Note' : 'New Note'}
              </h2>
              <button
                onClick={() => {
                  setShowNoteEditor(false);
                  setEditingNote(null);
                }}
                className="p-1 text-gray-500 hover:text-gray-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              <div>
                <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
                  Title *
                </label>
                <input
                  type="text"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  placeholder="Note title..."
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f]"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
                  Content (Markdown supported)
                </label>
                <textarea
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="Write your notes here..."
                  rows={12}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f] resize-none"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 p-4 border-t border-[#1a1a1a]">
              <button
                onClick={() => {
                  setShowNoteEditor(false);
                  setEditingNote(null);
                }}
                className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveNote}
                disabled={!noteTitle.trim() || savingNote}
                className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50"
              >
                {savingNote && <Loader2 className="h-4 w-4 animate-spin" />}
                <Save className="h-4 w-4" />
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
