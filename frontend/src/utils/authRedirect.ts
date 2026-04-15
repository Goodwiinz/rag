const DEFAULT_AUTH_REDIRECT = '/dashboard';

export function getSafeAuthRedirect(
  candidate: string | null | undefined,
  origin: string,
  fallback: string = DEFAULT_AUTH_REDIRECT
): string {
  if (!candidate) {
    return fallback;
  }

  try {
    const url = new URL(candidate, origin);

    if (url.origin !== origin) {
      return fallback;
    }

    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}
