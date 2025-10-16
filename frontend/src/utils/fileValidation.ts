import { UPLOAD_LIMITS } from '@/types';

export interface FileValidationError {
  code: 'FILE_TOO_LARGE' | 'UNSUPPORTED_TYPE' | 'TOO_MANY_FILES' | 'QUOTA_EXCEEDED' | 'INVALID_NAME';
  message: string;
  details?: any;
}

export interface ValidationResult {
  isValid: boolean;
  errors: FileValidationError[];
  warnings: string[];
}

export interface FileValidationOptions {
  maxFileSize?: number; // in bytes
  maxFiles?: number;
  allowedTypes?: string[];
  currentQuotaUsed?: number; // in bytes
  maxQuota?: number; // in bytes
}

/**
 * Validates file name for security and compatibility
 */
export const validateFileName = (fileName: string): FileValidationError | null => {
  // Check for empty filename
  if (!fileName || fileName.trim().length === 0) {
    return {
      code: 'INVALID_NAME',
      message: 'File name cannot be empty',
    };
  }

  // Check for forbidden characters (Windows/Linux/Mac)
  const forbiddenChars = /[<>:"/\\|?*\x00-\x1f]/;
  if (forbiddenChars.test(fileName)) {
    return {
      code: 'INVALID_NAME',
      message: 'File name contains invalid characters',
      details: { forbiddenChars: '<>:"/\\|?*' },
    };
  }

  // Check for reserved names (Windows)
  const reservedNames = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i;
  const nameWithoutExt = fileName.split('.')[0];
  if (nameWithoutExt && reservedNames.test(nameWithoutExt)) {
    return {
      code: 'INVALID_NAME',
      message: 'File name is reserved by the system',
      details: { reservedName: nameWithoutExt },
    };
  }

  // Check length limits
  if (fileName.length > 255) {
    return {
      code: 'INVALID_NAME',
      message: 'File name is too long (max 255 characters)',
      details: { actualLength: fileName.length, maxLength: 255 },
    };
  }

  return null;
};

/**
 * Validates file size against limits
 */
export const validateFileSize = (
  file: File,
  maxFileSize: number
): FileValidationError | null => {
  if (file.size > maxFileSize) {
    return {
      code: 'FILE_TOO_LARGE',
      message: `File is too large (${formatFileSize(file.size)} > ${formatFileSize(maxFileSize)})`,
      details: {
        actualSize: file.size,
        maxSize: maxFileSize,
        fileName: file.name,
      },
    };
  }

  return null;
};

/**
 * Validates file type against allowed types
 */
export const validateFileType = (
  file: File,
  allowedTypes: string[]
): FileValidationError | null => {
  const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
  const isAllowedType = allowedTypes.includes(file.type) ||
                       allowedTypes.some(type => type.includes(fileExtension));

  if (!isAllowedType) {
    return {
      code: 'UNSUPPORTED_TYPE',
      message: `File type not supported (${file.type || 'unknown'})`,
      details: {
        fileType: file.type,
        fileExtension,
        allowedTypes,
        fileName: file.name,
      },
    };
  }

  return null;
};

/**
 * Validates total number of files
 */
export const validateFileCount = (
  currentCount: number,
  newFilesCount: number,
  maxFiles: number
): FileValidationError | null => {
  const totalFiles = currentCount + newFilesCount;

  if (totalFiles > maxFiles) {
    return {
      code: 'TOO_MANY_FILES',
      message: `Too many files (${totalFiles} > ${maxFiles})`,
      details: {
        currentCount,
        newFilesCount,
        maxFiles,
      },
    };
  }

  return null;
};

/**
 * Validates storage quota
 */
export const validateStorageQuota = (
  currentQuotaUsed: number,
  newFilesSize: number,
  maxQuota: number
): FileValidationError | null => {
  const totalQuotaUsed = currentQuotaUsed + newFilesSize;

  if (totalQuotaUsed > maxQuota) {
    return {
      code: 'QUOTA_EXCEEDED',
      message: `Storage quota exceeded (${formatFileSize(totalQuotaUsed)} > ${formatFileSize(maxQuota)})`,
      details: {
        currentQuotaUsed,
        newFilesSize,
        maxQuota,
        availableSpace: maxQuota - currentQuotaUsed,
      },
    };
  }

  return null;
};

/**
 * Validates a single file
 */
export const validateFile = (
  file: File,
  options: FileValidationOptions
): ValidationResult => {
  const errors: FileValidationError[] = [];
  const warnings: string[] = [];

  const {
    maxFileSize = UPLOAD_LIMITS.MAX_FILE_SIZE_MB * 1024 * 1024,
    allowedTypes,
  } = options;

  // Validate file name
  const nameError = validateFileName(file.name);
  if (nameError) errors.push(nameError);

  // Validate file size
  const sizeError = validateFileSize(file, maxFileSize);
  if (sizeError) errors.push(sizeError);

  // Validate file type
  const typeError = validateFileType(file, allowedTypes || [...UPLOAD_LIMITS.SUPPORTED_FORMATS]);
  if (typeError) errors.push(typeError);

  // Add warnings for potentially problematic files
  if (file.size === 0) {
    warnings.push('File is empty');
  }

  if (file.name.length > 100) {
    warnings.push('File name is very long, may cause issues');
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Validates multiple files as a batch
 */
export const validateFileBatch = (
  files: File[],
  existingFileCount: number = 0,
  currentQuotaUsed: number = 0,
  options: FileValidationOptions = {}
): ValidationResult => {
  const errors: FileValidationError[] = [];
  const warnings: string[] = [];

  const {
    maxFileSize = UPLOAD_LIMITS.MAX_FILE_SIZE_MB * 1024 * 1024,
    maxFiles = UPLOAD_LIMITS.MAX_FILES_PER_UPLOAD,
    allowedTypes,
    maxQuota = 5 * 1024 * 1024 * 1024, // 5GB default
  } = options;

  // Validate file count
  const countError = validateFileCount(existingFileCount, files.length, maxFiles);
  if (countError) errors.push(countError);

  // Calculate total size for quota validation
  const totalNewFileSize = files.reduce((sum, file) => sum + file.size, 0);

  // Validate storage quota
  const quotaError = validateStorageQuota(currentQuotaUsed, totalNewFileSize, maxQuota);
  if (quotaError) errors.push(quotaError);

  // Validate individual files
  files.forEach((file, index) => {
    const fileValidation = validateFile(file, {
      maxFileSize,
      allowedTypes: allowedTypes || [...UPLOAD_LIMITS.SUPPORTED_FORMATS],
    });

    // Add file index to error details for debugging
    fileValidation.errors.forEach(error => {
      if (error.details) {
        error.details.fileIndex = index;
      }
    });

    errors.push(...fileValidation.errors);
    warnings.push(...fileValidation.warnings);
  });

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Formats file size in bytes to human readable format
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

/**
 * Gets file type category for display purposes
 */
export const getFileTypeCategory = (file: File): 'document' | 'image' | 'audio' | 'video' | 'other' => {
  if (file.type === 'application/pdf' || file.type === 'text/plain') {
    return 'document';
  }
  if (file.type.startsWith('image/')) {
    return 'image';
  }
  if (file.type.startsWith('audio/')) {
    return 'audio';
  }
  if (file.type.startsWith('video/')) {
    return 'video';
  }
  return 'other';
};

/**
 * Generates a unique file ID for tracking
 */
export const generateFileId = (file: File): string => {
  const timestamp = Date.now().toString(36);
  const randomString = Math.random().toString(36).substr(2, 9);
  const fileHash = file.name + file.size + file.type;
  const fileHashShort = fileHash.split('').reduce((acc, char) => {
    return ((acc << 5) - acc + char.charCodeAt(0)) & 0xffffffff;
  }, 0).toString(36);

  return `${timestamp}_${randomString}_${fileHashShort}`;
};

/**
 * Sanitizes file name for safe storage and display
 */
export const sanitizeFileName = (fileName: string): string => {
  // Remove or replace invalid characters
  let sanitized = fileName
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_') // Replace invalid chars with underscore
    .replace(/\s+/g, ' ') // Replace multiple spaces with single space
    .trim(); // Remove leading/trailing whitespace

  // Ensure the name is not empty after sanitization
  if (sanitized.length === 0) {
    sanitized = 'unnamed_file';
  }

  // Truncate if too long
  if (sanitized.length > 200) {
    const extension = sanitized.split('.').pop();
    const nameWithoutExt = sanitized.substring(0, sanitized.lastIndexOf('.'));
    const truncatedName = nameWithoutExt.substring(0, 200 - (extension?.length || 0) - 1);
    sanitized = extension ? `${truncatedName}.${extension}` : truncatedName;
  }

  return sanitized;
};

// Export default validation options
export const DEFAULT_VALIDATION_OPTIONS: FileValidationOptions = {
  maxFileSize: UPLOAD_LIMITS.MAX_FILE_SIZE_MB * 1024 * 1024,
  maxFiles: UPLOAD_LIMITS.MAX_FILES_PER_UPLOAD,
  allowedTypes: [...UPLOAD_LIMITS.SUPPORTED_FORMATS],
  maxQuota: 5 * 1024 * 1024 * 1024, // 5GB
};