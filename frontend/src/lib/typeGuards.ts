/**
 * Type Guards and Validation Utilities
 *
 * Runtime type checking, validation helpers, and type guard functions
 * for ensuring type safety throughout the application.
 */

import { ZodSchema, ZodError } from 'zod';

// ============================================================================
// Validation Result Types
// ============================================================================

export interface ValidationResult<T> {
  success: boolean;
  data?: T;
  error?: ZodError;
}

export interface FileValidationResult {
  valid: boolean;
  file: File;
  errors: string[];
  warnings: string[];
  fileInfo: {
    name: string;
    size: number;
    type: string;
    extension: string;
  };
}

// ============================================================================
// Zod Schema Validation
// ============================================================================

/**
 * Validate data against a Zod schema
 * @param schema - Zod schema to validate against
 * @param data - Data to validate
 * @returns ValidationResult with success status and either data or error
 */
export function validate<T>(schema: ZodSchema<T>, data: unknown): ValidationResult<T> {
  try {
    const result = schema.safeParse(data);

    if (result.success) {
      return {
        success: true,
        data: result.data,
      };
    }

    return {
      success: false,
      error: result.error,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof ZodError ? error : undefined,
    };
  }
}

// ============================================================================
// URL and Search Params Utilities
// ============================================================================

/**
 * Build URLSearchParams from an object, filtering out undefined/null values
 * @param params - Object to convert to search params
 * @returns URLSearchParams instance
 */
export function buildSearchParams(params: Record<string, unknown>): URLSearchParams {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null) {
          searchParams.append(key, String(item));
        }
      });
    } else if (typeof value === 'object') {
      searchParams.set(key, JSON.stringify(value));
    } else if (typeof value === 'boolean') {
      searchParams.set(key, value.toString());
    } else {
      searchParams.set(key, String(value));
    }
  });

  return searchParams;
}

// ============================================================================
// Error Handling Utilities
// ============================================================================

/**
 * Extract a readable error message from various error types
 * @param error - Error object of any type
 * @returns Human-readable error message
 */
export function extractErrorMessage(error: unknown): string {
  if (error === null || error === undefined) {
    return 'An unknown error occurred';
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error instanceof ZodError) {
    const issues = error.issues.map((issue) => issue.message).join(', ');
    return `Validation error: ${issues}`;
  }

  if (error instanceof Error) {
    return error.message || error.name || 'An error occurred';
  }

  if (typeof error === 'object') {
    const errorObj = error as Record<string, unknown>;

    // Check common error message properties
    if (typeof errorObj.message === 'string') {
      return errorObj.message;
    }

    if (typeof errorObj.error === 'string') {
      return errorObj.error;
    }

    if (
      typeof errorObj.error === 'object' &&
      errorObj.error !== null &&
      typeof (errorObj.error as Record<string, unknown>).message === 'string'
    ) {
      return (errorObj.error as Record<string, unknown>).message as string;
    }

    if (typeof errorObj.detail === 'string') {
      return errorObj.detail;
    }

    // FastAPI validation errors
    if (Array.isArray(errorObj.detail)) {
      return errorObj.detail
        .map((d: { msg?: string; message?: string }) => d.msg || d.message || String(d))
        .join(', ');
    }
  }

  return 'An unknown error occurred';
}

// ============================================================================
// File Validation
// ============================================================================

/**
 * Supported file types and their configurations
 */
const SUPPORTED_FILE_TYPES: Record<string, { maxSize: number; extensions: string[] }> = {
  // Documents
  'application/pdf': { maxSize: 50 * 1024 * 1024, extensions: ['.pdf'] },
  'text/plain': { maxSize: 10 * 1024 * 1024, extensions: ['.txt'] },
  'text/markdown': { maxSize: 10 * 1024 * 1024, extensions: ['.md', '.markdown'] },
  'application/msword': { maxSize: 50 * 1024 * 1024, extensions: ['.doc'] },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
    maxSize: 50 * 1024 * 1024,
    extensions: ['.docx'],
  },

  // Images
  'image/jpeg': { maxSize: 20 * 1024 * 1024, extensions: ['.jpg', '.jpeg'] },
  'image/png': { maxSize: 20 * 1024 * 1024, extensions: ['.png'] },
  'image/gif': { maxSize: 10 * 1024 * 1024, extensions: ['.gif'] },
  'image/webp': { maxSize: 20 * 1024 * 1024, extensions: ['.webp'] },

  // Audio
  'audio/mpeg': { maxSize: 100 * 1024 * 1024, extensions: ['.mp3'] },
  'audio/wav': { maxSize: 200 * 1024 * 1024, extensions: ['.wav'] },
  'audio/ogg': { maxSize: 100 * 1024 * 1024, extensions: ['.ogg'] },

  // Video
  'video/mp4': { maxSize: 500 * 1024 * 1024, extensions: ['.mp4'] },
  'video/quicktime': { maxSize: 500 * 1024 * 1024, extensions: ['.mov'] },
  'video/x-msvideo': { maxSize: 500 * 1024 * 1024, extensions: ['.avi'] },

  // Data
  'application/json': { maxSize: 10 * 1024 * 1024, extensions: ['.json'] },
  'text/csv': { maxSize: 50 * 1024 * 1024, extensions: ['.csv'] },
};

/**
 * Check if a file type is supported
 * @param mimeType - MIME type to check
 * @returns boolean indicating if the type is supported
 */
export function isSupportedFileType(mimeType: string): boolean {
  return mimeType in SUPPORTED_FILE_TYPES;
}

/**
 * Get file extension from filename
 */
function getFileExtension(filename: string): string {
  const lastDotIndex = filename.lastIndexOf('.');
  if (lastDotIndex === -1) return '';
  return filename.slice(lastDotIndex).toLowerCase();
}

/**
 * Validate a file for upload
 * @param file - File to validate
 * @param options - Optional validation options
 * @returns FileValidationResult
 */
export function validateFile(
  file: File,
  options?: {
    maxSize?: number;
    allowedTypes?: string[];
  }
): FileValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const extension = getFileExtension(file.name);

  const fileInfo = {
    name: file.name,
    size: file.size,
    type: file.type || 'application/octet-stream',
    extension,
  };

  // Check if file type is supported
  const typeConfig = SUPPORTED_FILE_TYPES[file.type];

  if (options?.allowedTypes && options.allowedTypes.length > 0) {
    // Custom allowed types
    if (!options.allowedTypes.includes(file.type)) {
      errors.push(
        `File type '${file.type || 'unknown'}' is not allowed. Allowed types: ${options.allowedTypes.join(', ')}`
      );
    }
  } else if (!typeConfig) {
    errors.push(`File type '${file.type || 'unknown'}' is not supported`);
  }

  // Check file size
  const maxSize = options?.maxSize || typeConfig?.maxSize || 100 * 1024 * 1024;

  if (file.size > maxSize) {
    const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(1);
    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
    errors.push(`File size (${fileSizeMB} MB) exceeds maximum allowed size (${maxSizeMB} MB)`);
  }

  // Check for empty files
  if (file.size === 0) {
    errors.push('File is empty');
  }

  // Check extension matches type
  if (typeConfig && extension && !typeConfig.extensions.includes(extension)) {
    warnings.push(
      `File extension '${extension}' doesn't match expected extensions for ${file.type}`
    );
  }

  // Check for suspicious filenames
  const suspiciousPatterns = [/\.exe$/i, /\.bat$/i, /\.cmd$/i, /\.sh$/i, /\.ps1$/i];
  if (suspiciousPatterns.some((pattern) => pattern.test(file.name))) {
    errors.push('Executable files are not allowed');
  }

  return {
    valid: errors.length === 0,
    file,
    errors,
    warnings,
    fileInfo,
  };
}

/**
 * Validate multiple files for upload
 * @param files - Array of files to validate
 * @param options - Optional validation options
 * @returns Array of FileValidationResult
 */
export function validateFiles(
  files: File[],
  options?: {
    maxSize?: number;
    allowedTypes?: string[];
    maxFiles?: number;
  }
): FileValidationResult[] {
  const results: FileValidationResult[] = [];

  if (options?.maxFiles && files.length > options.maxFiles) {
    // Return a single error result for too many files
    return [
      {
        valid: false,
        file: files[0],
        errors: [`Too many files. Maximum allowed: ${options.maxFiles}`],
        warnings: [],
        fileInfo: {
          name: 'Multiple files',
          size: files.reduce((sum, f) => sum + f.size, 0),
          type: 'multiple',
          extension: '',
        },
      },
    ];
  }

  for (const file of files) {
    results.push(validateFile(file, options));
  }

  return results;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for checking if value is a Document object
 */
export function isDocument(value: unknown): value is {
  id: string;
  title: string;
  file_type: string;
  status: string;
} {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  return (
    typeof obj.id === 'string' &&
    typeof obj.title === 'string' &&
    typeof obj.file_type === 'string' &&
    typeof obj.status === 'string'
  );
}

/**
 * Type guard for API error objects
 */
export function isAPIError(value: unknown): value is {
  message: string;
  status_code: number;
  type: string;
} {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  return (
    typeof obj.message === 'string' &&
    typeof obj.status_code === 'number' &&
    typeof obj.type === 'string'
  );
}

/**
 * Type guard for API error response wrapper
 */
export function isAPIErrorResponse(value: unknown): value is {
  error: {
    message: string;
    status_code: number;
    type: string;
  };
} {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;

  return isAPIError(obj.error);
}

// ============================================================================
// Response Transformers
// ============================================================================

/**
 * Transform backend file upload response to frontend format
 */
export function transformFileUploadResponse(backendResponse: {
  id: string;
  file_info: {
    filename: string;
    content_type: string;
    size: number;
  };
  job_id?: string;
  message?: string;
  estimated_processing_time_seconds?: number;
}): {
  document_id: string;
  upload_id: string;
  title: string;
  filename: string;
  document_type: string;
  file_size_bytes: number;
  file_size_mb: number;
  mime_type: string;
  processing_status: string;
  job_id?: string;
  estimated_processing_time?: number;
  message?: string;
  created_at: string;
} {
  return {
    document_id: backendResponse.id,
    upload_id: backendResponse.id,
    title: backendResponse.file_info.filename,
    filename: backendResponse.file_info.filename,
    document_type: backendResponse.file_info.content_type,
    file_size_bytes: backendResponse.file_info.size,
    file_size_mb: backendResponse.file_info.size / (1024 * 1024),
    mime_type: backendResponse.file_info.content_type,
    processing_status: 'queued',
    job_id: backendResponse.job_id,
    estimated_processing_time: backendResponse.estimated_processing_time_seconds,
    message: backendResponse.message,
    created_at: new Date().toISOString(),
  };
}

// ============================================================================
// Utility Type Checks
// ============================================================================

/**
 * Check if value is a non-null object
 */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Check if value is a non-empty string
 */
export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

/**
 * Check if value is a valid UUID
 */
export function isUUID(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(value);
}

/**
 * Check if value is a valid ISO timestamp
 */
export function isISOTimestamp(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const date = new Date(value);
  return !isNaN(date.getTime()) && value.includes('T');
}
