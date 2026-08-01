import { describe, expect, it } from 'vitest';

import {
  AUTH_SERVICE_UNAVAILABLE,
  isOpaqueAuthMessage,
  supabaseAuthErrorMessage,
} from '@/utils/supabaseAuthError';

describe('isOpaqueAuthMessage', () => {
  it.each([
    ['{}', 'the stringified Response auth-js produces for gateway errors'],
    ['[]', 'an array body'],
    ['{"code":503}', 'a JSON object body'],
    ['   ', 'whitespace only'],
    ['', 'empty'],
    ['null', 'a null literal'],
    ['undefined', 'an undefined literal'],
  ])('treats %j as opaque (%s)', (message) => {
    expect(isOpaqueAuthMessage(message)).toBe(true);
  });

  it.each([undefined, null, 42, {}])(
    'treats the non-string %j as opaque',
    (message) => {
      expect(isOpaqueAuthMessage(message)).toBe(true);
    }
  );

  it.each(['Invalid login credentials', 'User already registered'])(
    'keeps the real GoTrue message %j',
    (message) => {
      expect(isOpaqueAuthMessage(message)).toBe(false);
    }
  );
});

describe('supabaseAuthErrorMessage', () => {
  const fallback = 'Could not create your account. Please try again.';

  it('passes a real GoTrue message through', () => {
    const error = {
      name: 'AuthApiError',
      status: 400,
      message: 'User already registered',
    };

    expect(supabaseAuthErrorMessage(error, fallback)).toBe(
      'User already registered'
    );
  });

  it('trims a real message', () => {
    expect(
      supabaseAuthErrorMessage(
        { message: '  Invalid login credentials  ' },
        fallback
      )
    ).toBe('Invalid login credentials');
  });

  // The bug: a 502/503/504 from GoTrue makes auth-js stringify the raw
  // Response, so `message` is the literal "{}" — which used to be rendered
  // straight into the sign-up error banner.
  it('replaces the "{}" message from a gateway failure', () => {
    const error = {
      name: 'AuthRetryableFetchError',
      status: 503,
      message: JSON.stringify(new Response(null, { status: 503 })),
    };

    expect(error.message).toBe('{}');
    expect(supabaseAuthErrorMessage(error, fallback)).toBe(
      AUTH_SERVICE_UNAVAILABLE
    );
  });

  it('reports a 5xx AuthApiError as unavailable', () => {
    expect(
      supabaseAuthErrorMessage(
        { name: 'AuthApiError', status: 500, message: '{}' },
        fallback
      )
    ).toBe(AUTH_SERVICE_UNAVAILABLE);
  });

  it('uses the caller fallback for an opaque non-5xx failure', () => {
    expect(
      supabaseAuthErrorMessage(
        { name: 'AuthApiError', status: 400, message: '{}' },
        fallback
      )
    ).toBe(fallback);
  });

  it('uses the caller fallback when there is no error object at all', () => {
    expect(supabaseAuthErrorMessage(null, fallback)).toBe(fallback);
    expect(supabaseAuthErrorMessage(undefined, fallback)).toBe(fallback);
  });
});
