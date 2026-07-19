/**
 * Extract a human-readable message from an error thrown by the API client.
 *
 * Axios rejects with `err.message === "Request failed with status code 4xx"`
 * for non-2xx responses — that's useless in a toast. The useful detail lives
 * on `err.response.data` as either `detail` (FastAPI convention) or
 * `message` (legacy). This helper walks that chain and falls back sensibly.
 *
 * Safe to call with any unknown value; returns `fallback` if nothing
 * readable is found.
 */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null) {
    const maybeAxios = err as {
      response?: { data?: unknown };
      message?: unknown;
    };
    const data = maybeAxios.response?.data;
    if (typeof data === 'string' && data.trim()) {
      return data;
    }
    if (typeof data === 'object' && data !== null) {
      const body = data as { detail?: unknown; message?: unknown };
      if (typeof body.detail === 'string' && body.detail.trim()) {
        return body.detail;
      }
      if (typeof body.message === 'string' && body.message.trim()) {
        return body.message;
      }
    }
    if (typeof maybeAxios.message === 'string' && maybeAxios.message.trim()) {
      return maybeAxios.message;
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}
