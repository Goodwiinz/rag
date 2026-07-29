/**
 * Normalize a Supabase auth error into a message that is safe to show a user.
 *
 * `@supabase/auth-js` derives an auth error's `message` with
 * `err.msg || err.message || err.error_description || err.error ||
 * JSON.stringify(err)`. For gateway-level failures (502, 503, 504, 520-524,
 * 530) it hands the raw `fetch` `Response` to that helper — and a `Response`
 * has no enumerable own properties, so `JSON.stringify` yields the literal
 * string `"{}"`. Rendering `supabaseError.message` verbatim then puts `{}` in
 * the error banner instead of anything the user can act on.
 *
 * The same applies to any body that stringifies to an opaque blob, so treat
 * "message starts with `{` or `[`" as "not a message".
 */

/** A message we must not show a user: empty, a JSON blob, or a null literal. */
export function isOpaqueAuthMessage(message: unknown): boolean {
  if (typeof message !== 'string') return true;

  const trimmed = message.trim();
  if (!trimmed) return true;
  if (trimmed === 'null' || trimmed === 'undefined') return true;

  return trimmed.startsWith('{') || trimmed.startsWith('[');
}

export const AUTH_SERVICE_UNAVAILABLE =
  'The authentication service is temporarily unavailable. Please try again in a moment.';

/**
 * True when the failure is an infrastructure blip rather than something the
 * user did wrong — a 5xx from GoTrue, or auth-js's retryable fetch error.
 */
function isServiceUnavailable(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false;

  const candidate = error as { name?: unknown; status?: unknown };
  if (candidate.name === 'AuthRetryableFetchError') return true;

  return typeof candidate.status === 'number' && candidate.status >= 500;
}

/**
 * Resolve the message to surface for a Supabase auth failure.
 *
 * Real GoTrue messages ("Invalid login credentials", "User already
 * registered", …) pass through untouched; opaque ones are replaced by
 * {@link AUTH_SERVICE_UNAVAILABLE} for 5xx/retryable failures and by `fallback`
 * otherwise.
 */
export function supabaseAuthErrorMessage(
  error: unknown,
  fallback: string
): string {
  const message =
    typeof error === 'object' && error !== null
      ? (error as { message?: unknown }).message
      : undefined;

  if (!isOpaqueAuthMessage(message)) {
    return (message as string).trim();
  }

  return isServiceUnavailable(error) ? AUTH_SERVICE_UNAVAILABLE : fallback;
}
