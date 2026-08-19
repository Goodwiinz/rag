/**
 * R4-H5 regression: the default allowedTypes are bare extensions
 * (UPLOAD_LIMITS.SUPPORTED_FORMATS = ['pdf', 'txt', ...]) but
 * validateFileType only matched MIME types or dotted-extension substrings,
 * so every file was rejected UNSUPPORTED_TYPE at queue time.
 */
import { describe, expect, it } from 'vitest';

import { UPLOAD_LIMITS } from '@/types/constants';
import { validateFileType } from '@/utils/fileValidation';

const makeFile = (name: string, type: string): File =>
  new File(['x'], name, { type });

describe('validateFileType', () => {
  it('accepts files against the default bare-extension formats', () => {
    const allowed = [...UPLOAD_LIMITS.SUPPORTED_FORMATS];
    expect(
      validateFileType(makeFile('paper.pdf', 'application/pdf'), allowed)
    ).toBeNull();
    expect(
      validateFileType(makeFile('notes.txt', 'text/plain'), allowed)
    ).toBeNull();
    expect(
      validateFileType(makeFile('scan.png', 'image/png'), allowed)
    ).toBeNull();
  });

  it('still accepts MIME-type and dotted-extension entries', () => {
    expect(
      validateFileType(makeFile('paper.pdf', 'application/pdf'), [
        'application/pdf',
      ])
    ).toBeNull();
    expect(
      validateFileType(makeFile('paper.pdf', 'application/pdf'), ['.pdf'])
    ).toBeNull();
  });

  it('rejects files outside the allowed list', () => {
    const error = validateFileType(makeFile('malware.exe', ''), [
      ...UPLOAD_LIMITS.SUPPORTED_FORMATS,
    ]);
    expect(error?.code).toBe('UNSUPPORTED_TYPE');
  });
});
