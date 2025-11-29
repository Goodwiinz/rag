/**
 * Example: Type-Safe API Usage Patterns
 *
 * This file demonstrates correct usage patterns for the new type-safe API clients
 */

import React, { useState, useCallback } from 'react';
import { typeSafeApiClient } from '@/services/typeSafeApiClient';
import { enhancedDocumentServiceV2 } from '@/services/enhancedDocumentService.v2';
import {
  validateFile,
  extractErrorMessage,
  isDocument,
  buildSearchParams
} from '@/lib/typeGuards';
import type * as schemas from '@/types/schemas';

// ============================================================================
// Example 1: File Upload with Validation
// ============================================================================

export function FileUploadExample() {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const handleFileUpload = useCallback(async (file: File) => {
    setError(null);

    // Step 1: Validate file BEFORE uploading
    const validation = validateFile(file);

    if (!validation.isValid) {
      setError(validation.errors.join(', '));
      return;
    }

    // Show warnings if any
    if (validation.warnings.length > 0) {
      console.warn('Upload warnings:', validation.warnings);
    }

    // Step 2: Upload with type-safe client
    setUploading(true);
    try {
      const response = await enhancedDocumentServiceV2.uploadDocument(
        file,
        {
          title: file.name,
          enable_quality_check: true,
          processing_priority: 'normal',
        },
        (progress) => setProgress(progress)
      );

      // response is type: DocumentUploadResponse
      console.log('Upload ID:', response.upload_id); // ✅ Type-safe access
      console.log('Job ID:', response.job_id);

      // Step 3: Poll for processing status
      pollJobStatus(response.job_id!);
    } catch (err) {
      setError(extractErrorMessage(err)); // ✅ Type-safe error extraction
    } finally {
      setUploading(false);
    }
  }, []);

  const pollJobStatus = async (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await typeSafeApiClient.getJobStatus(jobId);

        setProgress(status.progress);

        if (status.status === 'completed') {
          clearInterval(interval);
          console.log('Processing complete!');
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setError(status.error_message || 'Processing failed');
        }
      } catch (err) {
        clearInterval(interval);
        setError(extractErrorMessage(err));
      }
    }, 2000);
  };

  return (
    <div>
      <input
        type="file"
        onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
        disabled={uploading}
      />
      {uploading && <div>Progress: {progress}%</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
    </div>
  );
}

// ============================================================================
// Example 2: Document List with Type-Safe Parameters
// ============================================================================

export function DocumentListExample() {
  const [documents, setDocuments] = useState<schemas.Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = useCallback(async (
    page: number = 1,
    status?: schemas.Document['processing_status'],
    search?: string
  ) => {
    setLoading(true);
    setError(null);

    try {
      // Type-safe parameters with automatic undefined filtering
      const response = await typeSafeApiClient.getDocuments({
        page,
        page_size: 20,
        status,      // ✅ undefined is safely omitted
        search,      // ✅ undefined is safely omitted
      });

      // response.documents is type: Document[]
      setDocuments(response.documents);

      // Access pagination safely
      console.log('Total:', response.pagination.total);
      console.log('Has next:', response.pagination.has_next);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div>
      <button onClick={() => fetchDocuments()}>Load Documents</button>
      <button onClick={() => fetchDocuments(1, 'indexed')}>Load Indexed</button>
      <button onClick={() => fetchDocuments(1, undefined, 'test')}>Search "test"</button>

      {loading && <div>Loading...</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}

      <ul>
        {documents.map(doc => (
          <li key={doc.id}>
            {doc.title} - {doc.processing_status}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================================
// Example 3: Search with Type Guards
// ============================================================================

export function SearchExample() {
  const [results, setResults] = useState<schemas.SearchResultItem[]>([]);
  const [query, setQuery] = useState('');

  const handleSearch = useCallback(async () => {
    try {
      const response = await typeSafeApiClient.search({
        query,
        limit: 10,
      });

      // response is type: SearchResult (validated at runtime)
      setResults(response.results);

      console.log('Search time:', response.search_time_ms, 'ms');
      console.log('Total results:', response.total_results);
    } catch (err) {
      console.error(extractErrorMessage(err));
    }
  }, [query]);

  return (
    <div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search..."
      />
      <button onClick={handleSearch}>Search</button>

      <ul>
        {results.map((result, index) => (
          <li key={index}>
            <h3>{result.title}</h3>
            <p>Score: {(result.score * 100).toFixed(1)}%</p>
            <p>{result.content.substring(0, 200)}...</p>
            {result.entities.length > 0 && (
              <div>
                Entities: {result.entities.map(e => e.text).join(', ')}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================================
// Example 4: Type Guard Usage
// ============================================================================

export function TypeGuardExample() {
  const [data, setData] = useState<unknown>(null);

  const handleApiResponse = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/documents/some-id');
      const json = await response.json();

      // Use type guard to safely check type
      if (isDocument(json)) {
        // ✅ TypeScript knows json is Document type
        setData(json);
        console.log(json.title);
        console.log(json.processing_status);
      } else {
        console.error('Response is not a valid document');
      }
    } catch (err) {
      console.error(extractErrorMessage(err));
    }
  }, []);

  return (
    <div>
      <button onClick={handleApiResponse}>Fetch Data</button>
      {data && isDocument(data) && (
        <div>
          <h2>{data.title}</h2>
          <p>Type: {data.file_type}</p>
          <p>Status: {data.processing_status}</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Example 5: Batch File Upload
// ============================================================================

export function BatchUploadExample() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [errors, setErrors] = useState<string[]>([]);

  const handleFilesChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;

    const fileList = Array.from(e.target.files);

    // Validate all files
    const allValid = fileList.every(file => {
      const validation = validateFile(file);
      if (!validation.isValid) {
        setErrors(prev => [...prev, ...validation.errors]);
        return false;
      }
      return true;
    });

    if (allValid) {
      setFiles(fileList);
      setErrors([]);
    }
  }, []);

  const handleBatchUpload = useCallback(async () => {
    setUploading(true);
    setErrors([]);

    try {
      const responses = await enhancedDocumentServiceV2.uploadBatchDocuments(
        files,
        files.map(file => ({
          title: file.name,
          enable_quality_check: true,
        })),
        (uploadId, progress) => {
          setUploadProgress(prev => ({ ...prev, [uploadId]: progress }));
        }
      );

      console.log('Uploaded:', responses.length, 'files');
    } catch (err) {
      setErrors([extractErrorMessage(err)]);
    } finally {
      setUploading(false);
    }
  }, [files]);

  return (
    <div>
      <input
        type="file"
        multiple
        onChange={handleFilesChange}
        disabled={uploading}
      />

      {files.length > 0 && (
        <>
          <p>Selected: {files.length} files</p>
          <button onClick={handleBatchUpload} disabled={uploading}>
            Upload All
          </button>
        </>
      )}

      {Object.entries(uploadProgress).map(([id, progress]) => (
        <div key={id}>Upload {id}: {progress}%</div>
      ))}

      {errors.length > 0 && (
        <div style={{ color: 'red' }}>
          {errors.map((err, i) => <div key={i}>{err}</div>)}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Example 6: Knowledge Graph Integration
// ============================================================================

export function KnowledgeGraphExample() {
  const [graphData, setGraphData] = useState<schemas.GraphData | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<schemas.EntityDetails | null>(null);

  const loadGraph = useCallback(async (documentIds: string[]) => {
    try {
      const data = await typeSafeApiClient.getGraphData({
        document_ids: documentIds,
        filters: {
          entity_types: ['person', 'organization'],
          min_confidence: 0.7,
        },
      });

      // data is type: GraphData (validated)
      setGraphData(data);
      console.log('Nodes:', data.nodes.length);
      console.log('Edges:', data.edges.length);
    } catch (err) {
      console.error(extractErrorMessage(err));
    }
  }, []);

  const loadEntityDetails = useCallback(async (entityId: string) => {
    try {
      const details = await typeSafeApiClient.getEntityDetails(entityId, {
        include_relationships: true,
        include_documents: true,
      });

      // details is type: EntityDetails (validated)
      setSelectedEntity(details);
      console.log('Entity:', details.entity.text);
      console.log('Relationships:', details.relationships.length);
    } catch (err) {
      console.error(extractErrorMessage(err));
    }
  }, []);

  return (
    <div>
      {graphData && (
        <div>
          <h3>Knowledge Graph</h3>
          <p>Nodes: {graphData.nodes.length}</p>
          <p>Edges: {graphData.edges.length}</p>

          <ul>
            {graphData.nodes.slice(0, 10).map(node => (
              <li key={node.id} onClick={() => loadEntityDetails(node.id)}>
                {node.label} ({node.type})
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedEntity && (
        <div>
          <h3>{selectedEntity.entity.text}</h3>
          <p>Type: {selectedEntity.entity.type}</p>
          <p>Confidence: {(selectedEntity.entity.confidence * 100).toFixed(1)}%</p>
          <p>Relationships: {selectedEntity.relationships.length}</p>
          <p>Documents: {selectedEntity.documents.length}</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Example 7: Custom Validation
// ============================================================================

export function CustomValidationExample() {
  const [customData, setCustomData] = useState<any>(null);

  const fetchCustomData = useCallback(async () => {
    try {
      // For custom endpoints, use the base client with schema
      const data = await typeSafeApiClient.get(
        '/custom/endpoint',
        schemas.z.object({
          id: schemas.z.string().uuid(),
          name: schemas.z.string().min(1),
          count: schemas.z.number().int().nonnegative(),
          tags: schemas.z.array(schemas.z.string()),
        })
      );

      // data is validated and typed
      setCustomData(data);
    } catch (err) {
      console.error(extractErrorMessage(err));
    }
  }, []);

  return (
    <div>
      <button onClick={fetchCustomData}>Fetch Custom Data</button>
      {customData && (
        <pre>{JSON.stringify(customData, null, 2)}</pre>
      )}
    </div>
  );
}

// ============================================================================
// Example 8: Error Handling Patterns
// ============================================================================

export function ErrorHandlingExample() {
  const [error, setError] = useState<string | null>(null);

  const exampleWithErrorHandling = useCallback(async () => {
    try {
      const document = await typeSafeApiClient.getDocument('some-id');
      console.log(document.title);
    } catch (err) {
      // Extract error message safely
      const message = extractErrorMessage(err);
      setError(message);

      // Check if it's an API error for detailed handling
      if (err instanceof Error && 'error' in err) {
        const apiError = err as any;
        if (apiError.error.status_code === 404) {
          console.log('Document not found');
        } else if (apiError.error.status_code === 401) {
          console.log('Unauthorized - redirect to login');
        }
      }
    }
  }, []);

  return (
    <div>
      <button onClick={exampleWithErrorHandling}>Test Error Handling</button>
      {error && <div style={{ color: 'red' }}>{error}</div>}
    </div>
  );
}

// ============================================================================
// Example 9: URL Parameter Building
// ============================================================================

export function SafeUrlParametersExample() {
  const fetchWithSafeParams = useCallback(async (
    page?: number,
    search?: string,
    status?: string
  ) => {
    // ✅ Correct way - undefined values are omitted
    const params = buildSearchParams({
      page: page || 1,
      search,  // undefined is safely omitted
      status,  // undefined is safely omitted
    });

    console.log('URL params:', params.toString());
    // Result: "page=1&status=indexed" (search omitted if undefined)

    // ❌ Wrong way - undefined becomes "undefined" string
    // const wrongParams = new URLSearchParams({
    //   page: String(page || 1),
    //   search: search as any,  // Becomes "undefined"!
    //   status: status as any,
    // });
  }, []);

  return (
    <div>
      <button onClick={() => fetchWithSafeParams(1, undefined, 'indexed')}>
        Fetch with Safe Params
      </button>
    </div>
  );
}

// Export all examples for documentation
export default {
  FileUploadExample,
  DocumentListExample,
  SearchExample,
  TypeGuardExample,
  BatchUploadExample,
  KnowledgeGraphExample,
  CustomValidationExample,
  ErrorHandlingExample,
  SafeUrlParametersExample,
};
