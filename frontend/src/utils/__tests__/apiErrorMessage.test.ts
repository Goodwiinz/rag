import { describe, expect, it } from 'vitest';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';
import { APIErrorClass } from '@/types/api';

describe('getApiErrorMessage', () => {
  it('reads the message from a thrown APIErrorClass envelope', () => {
    const err = new APIErrorClass({
      message: 'Project already exists',
      status_code: 409,
      type: 'http_error',
    });
    expect(getApiErrorMessage(err, 'fallback')).toBe('Project already exists');
  });

  it('reads the message from a raw backend envelope object', () => {
    const err = {
      error: {
        message: 'Not authorized',
        status_code: 403,
        type: 'auth_error',
      },
    };
    expect(getApiErrorMessage(err, 'fallback')).toBe('Not authorized');
  });

  it('reads legacy response.data bodies (detail precedence)', () => {
    const err = { response: { data: { detail: 'Legacy detail message' } } };
    expect(getApiErrorMessage(err, 'fallback')).toBe('Legacy detail message');
  });

  it('falls back to a plain Error message', () => {
    expect(getApiErrorMessage(new Error('network down'), 'fallback')).toBe(
      'network down'
    );
  });

  it('returns the fallback for unreadable values', () => {
    expect(getApiErrorMessage({}, 'Failed to create project')).toBe(
      'Failed to create project'
    );
    expect(getApiErrorMessage(null, 'Failed to create project')).toBe(
      'Failed to create project'
    );
    expect(getApiErrorMessage(undefined, 'Failed to create project')).toBe(
      'Failed to create project'
    );
  });
});
