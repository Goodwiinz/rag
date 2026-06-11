/**
 * SECURITY (audit #13): decide whether an attacker-controllable X-Forwarded-Host
 * header may be trusted as the public origin.
 *
 * The OAuth callback builds its post-auth redirect from this origin, so an
 * unvalidated forwarded host is an open-redirect / phishing vector. Only hosts
 * the deployment explicitly declares are trusted:
 *   - the host of NEXT_PUBLIC_FRONTEND_URL / NEXT_PUBLIC_APP_URL, and
 *   - any host in the comma-separated TRUSTED_PROXY_HOSTS env var.
 * With none configured, no forwarded host is trusted (callers fall back to the
 * request's own origin) — fail closed.
 */
export function isTrustedForwardedHost(host: string): boolean {
  if (!host) return false;

  const allow = new Set<string>();
  for (const url of [
    process.env.NEXT_PUBLIC_FRONTEND_URL,
    process.env.NEXT_PUBLIC_APP_URL,
  ]) {
    if (!url) continue;
    try {
      allow.add(new URL(url).host);
    } catch {
      // ignore a malformed env URL
    }
  }
  for (const h of (process.env.TRUSTED_PROXY_HOSTS || '').split(',')) {
    const trimmed = h.trim();
    if (trimmed) allow.add(trimmed);
  }
  return allow.has(host);
}
