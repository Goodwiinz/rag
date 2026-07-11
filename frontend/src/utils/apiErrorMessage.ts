import { parseErrorBody } from '@/utils/parseErrorBody';

/**
 * Extract a human-readable message from an error thrown by the API client.
 *
 * The API client rejects with an `APIErrorClass` whose `.error` is the backend
 * envelope `{ message, status_code, type, details? }` and whose `.message`
 * mirrors that envelope message. This helper resolves the best available
 * message from either the thrown error itself or, if the error carries a raw
 * response body, from that body — delegating the precedence rules to the
 * shared `parseErrorBody`.
 *
 * Safe to call with any unknown value; returns `fallback` if nothing readable
 * is found.
 */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null) {
    const candidate = err as {
      error?: unknown;
      response?: { data?: unknown };
      message?: unknown;
    };

    // Thrown APIErrorClass (or any object shaped like the backend envelope):
    // parse `{ error: { message, ... } }` directly.
    if (typeof candidate.error === 'object' && candidate.error !== null) {
      const parsed = parseErrorBody(err);
      if (parsed.message !== 'Request failed') {
        return parsed.message;
      }
    }

    // Legacy / interceptor-wrapped errors that carry the raw response body.
    if (candidate.response?.data !== undefined) {
      const parsed = parseErrorBody(candidate.response.data);
      if (parsed.message !== 'Request failed') {
        return parsed.message;
      }
    }

    if (typeof candidate.message === 'string' && candidate.message.trim()) {
      return candidate.message;
    }
  }

  if (err instanceof Error && err.message) {
    return err.message;
  }

  return fallback;
}
