import React, { useState } from 'react';
import { DocumentLibrary } from '@/components/documents/DocumentLibrary';
import { DocumentPreview } from '@/components/documents/DocumentPreview';
import { DocumentMetadataEditor } from '@/components/documents/DocumentMetadataEditor';
import { Document } from '@/types';
import { api } from '@/services/api-client';

const Documents: React.FC = () => {
  const [previewDocument, setPreviewDocument] = useState<Document | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [editingDocument, setEditingDocument] = useState<Document | null>(null);
  const [isMetadataEditorOpen, setIsMetadataEditorOpen] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDocumentSelect = (document: Document) => {
    // Handle document selection for preview or detailed view
    console.log('Document selected:', document.id);
    // For now, also open preview
    setPreviewDocument(document);
    setIsPreviewOpen(true);
  };

  const handleDocumentPreview = (document: Document) => {
    // Handle document preview
    console.log('Document preview:', document.id);
    setPreviewDocument(document);
    setIsPreviewOpen(true);
  };

  const handlePreviewClose = () => {
    setIsPreviewOpen(false);
    setPreviewDocument(null);
  };

  const handleDocumentDownload = async (doc: Document) => {
    const a = window.document.createElement('a');
    let url: string | null = null;
    try {
      const blob = await api.request<Blob>(`/api/documents/${doc.id}/download`, { method: 'GET' });
      url = window.URL.createObjectURL(blob);
      a.href = url;
      a.download = doc.filename ?? 'download';
      window.document.body.appendChild(a);
      a.click();
    } catch (error) {
      console.error('Failed to download document:', error);
      setDownloadError('Failed to download document. Please try again.');
    } finally {
      if (url) window.URL.revokeObjectURL(url);
      if (a.parentNode) window.document.body.removeChild(a);
    }
  };

  const handleDocumentShare = (document: Document) => {
    // TODO: Implement share functionality
    console.log('Sharing document:', document.id);
    // For now, just copy the URL to clipboard
    const shareUrl = `${window.location.origin}/documents/${document.id}`;
    navigator.clipboard.writeText(shareUrl).then(() => {
      // TODO: Show success toast
      console.log('Document URL copied to clipboard');
    }).catch((error) => {
      console.error('Failed to copy URL:', error);
    });
  };

  const handleEditMetadata = (document: Document) => {
    setEditingDocument(document);
    setIsMetadataEditorOpen(true);
  };

  const handleMetadataEditorClose = () => {
    setIsMetadataEditorOpen(false);
    setEditingDocument(null);
  };

  const handleSaveMetadata = async (documentId: string, metadata: Partial<Document>) => {
    try {
      // TODO: Implement actual metadata save functionality
      console.log('Saving metadata for document:', documentId, metadata);
      await api.patch(`/api/documents/${documentId}/metadata`, metadata);

      // TODO: Show success toast and refresh documents
      console.log('Metadata saved successfully');
    } catch (error) {
      console.error('Failed to save metadata:', error);
      throw error; // Re-throw to let the component handle the error
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {downloadError && (
        <div className="mb-4 rounded-md bg-red-50 p-4">
          <div className="text-sm text-red-800">{downloadError}</div>
        </div>
      )}
      <DocumentLibrary
        onDocumentSelect={handleDocumentSelect}
        onDocumentPreview={handleDocumentPreview}
      />

      <DocumentPreview
        document={previewDocument}
        isOpen={isPreviewOpen}
        onClose={handlePreviewClose}
        onDownload={handleDocumentDownload}
        onShare={handleDocumentShare}
        onEditMetadata={handleEditMetadata}
      />

      <DocumentMetadataEditor
        document={editingDocument}
        isOpen={isMetadataEditorOpen}
        onClose={handleMetadataEditorClose}
        onSave={handleSaveMetadata}
      />
    </div>
  );
};

export default Documents;