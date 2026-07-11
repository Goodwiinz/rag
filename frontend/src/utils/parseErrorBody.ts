import type { APIError } from '@/types/api';

/**
 * Parsed shape of a backend error response body.
 *
 * The backend's global exception handlers (`backend/src/main.py`) rewrite every
 * error into the structured envelope `{ error: { message, status_code, type,
 * details? } }` (see `APIError` in `@/types/api`). This helper reads that
 * envelope and degrades gracefully to legacy / FastAPI-native shapes so a
 * single parser can be used everywhere raw error bodies are handled.
 */
export interface ParsedErrorBody {
  /** Human-readable message, resolved via precedence (never empty). */
  message: string;
  /** Envelope error type, when present — lets callers branch on
   * `auth_error` / `rate_limit` / etc. */
  type?: APIError['error']['type'];
  /** HTTP status code from the envelope, when present. */
  statusCode?: number;
  /** Structured details bag from the envelope, when present. */
  details?: Record<string, unknown>;
  /** Envelope `silent` flag — suppress noisy console errors for optional
   * endpoints that may legitimately 404. */
  silent?: boolean;
}

const firstNonEmptyString = (...values: unknown[]): string | undefined => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return undefined;
};

/**
 * Parse a raw backend error body into a normalized {@link ParsedErrorBody}.
 *
 * Message precedence (matches the audit's required order):
 *   1. `body.error.message` — the structured backend envelope (canonical)
 *   2. `body.detail`        — FastAPI-native / raised `HTTPException(detail=…)`
 *   3. `body.message`       — legacy flat shape
 *   4. `fallback`           — usually `response.statusText`
 *   5. `'Request failed'`   — last resort so the result is never empty
 *
 * `body` may be anything (a parsed JSON object, a string, `null`, or the result
 * of a failed `response.json()`); non-object inputs fall through to `fallback`.
 */
export function parseErrorBody(
  body: unknown,
  fallback?: string
): ParsedErrorBody {
  // A plain string body (e.g. `text/plain` error) is itself the message.
  if (typeof body === 'string') {
    return { message: firstNonEmptyString(body, fallback) ?? 'Request failed' };
  }

  if (typeof body === 'object' && body !== null) {
    const record = body as Record<string, unknown>;
    const envelope =
      typeof record.error === 'object' && record.error !== null
        ? (record.error as Record<string, unknown>)
        : undefined;

    const message = firstNonEmptyString(
      envelope?.message,
      record.detail,
      record.message,
      fallback
    );

    const type = (envelope?.type as ParsedErrorBody['type']) ?? undefined;
    const statusCode =
      typeof envelope?.status_code === 'number'
        ? envelope.status_code
        : undefined;
    const details =
      typeof envelope?.details === 'object' && envelope.details !== null
        ? (envelope.details as Record<string, unknown>)
        : undefined;
    const silent =
      typeof envelope?.silent === 'boolean' ? envelope.silent : undefined;

    return {
      message: message ?? 'Request failed',
      ...(type ? { type } : {}),
      ...(statusCode !== undefined ? { statusCode } : {}),
      ...(details ? { details } : {}),
      ...(silent !== undefined ? { silent } : {}),
    };
  }

  return { message: firstNonEmptyString(fallback) ?? 'Request failed' };
}
