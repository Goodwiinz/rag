import { createClient } from '@/lib/supabase/client';
import { useAuthStore } from '@/stores/authStore';

interface NousCliAuthOrganization {
  id: string;
  name?: string;
}

interface NousCliAuthUser {
  email?: string;
  organization_id?: string;
  organization_name?: string;
}

interface LegacyNousCliAuthSource {
  token: string | null;
  refreshTokenValue: string | null;
  tokenExpiresAt: number | null;
  refreshExpiresAt: number | null;
  rememberMe: boolean;
  organization: NousCliAuthOrganization | null;
  user: NousCliAuthUser | null;
}

interface SessionNousCliAuthSource {
  session: {
    access_token: string | null;
    refresh_token: string | null;
    expires_at?: number | null;
  } | null;
  organization: NousCliAuthOrganization | null;
  user: NousCliAuthUser | null;
  rememberMe?: boolean;
  refreshExpiresAt?: number | null;
}

export type NousCliAuthSource =
  | LegacyNousCliAuthSource
  | SessionNousCliAuthSource;

export interface NousCliAuthPayload {
  version: 1;
  source: 'frontend-login';
  exported_at: string;
  token: string;
  organization_id: string;
  organization_name?: string;
  user_email?: string;
  // NOTE: the refresh_token is intentionally NOT exported. It is long-lived and
  // exchangeable for fresh access tokens indefinitely; writing it to a
  // plaintext file on disk (downloads folder, cloud sync, shared machine) is a
  // standing credential-theft risk. The CLI gets only the short-lived access
  // token; it must re-authenticate through the browser when that expires.
  token_expires_at: number | null;
  remember_me: boolean;
}

function isLegacyNousCliAuthSource(
  source: NousCliAuthSource
): source is LegacyNousCliAuthSource {
  return 'token' in source;
}

function getToken(source: NousCliAuthSource): string | null {
  if (isLegacyNousCliAuthSource(source)) {
    return source.token;
  }

  return source.session?.access_token ?? null;
}

function getTokenExpiresAt(source: NousCliAuthSource): number | null {
  if (isLegacyNousCliAuthSource(source)) {
    return source.tokenExpiresAt;
  }

  if (!source.session?.expires_at) {
    return null;
  }

  return source.session.expires_at * 1000;
}

function getRememberMe(source: NousCliAuthSource): boolean {
  if (isLegacyNousCliAuthSource(source)) {
    return source.rememberMe;
  }

  return source.rememberMe ?? false;
}

export function buildNousCliAuthPayload(
  source: NousCliAuthSource
): NousCliAuthPayload {
  const token = getToken(source);
  const organizationId =
    source.organization?.id ?? source.user?.organization_id;
  const organizationName =
    source.organization?.name ?? source.user?.organization_name;

  if (!token) {
    throw new Error('Cannot export NOUS CLI auth without a token.');
  }

  if (!organizationId) {
    throw new Error('Cannot export NOUS CLI auth without an organization.');
  }

  return {
    version: 1,
    source: 'frontend-login',
    exported_at: new Date().toISOString(),
    token,
    organization_id: organizationId,
    organization_name: organizationName,
    user_email: source.user?.email,
    // refresh_token / refresh_expires_at intentionally omitted — see the
    // NousCliAuthPayload type note. Only the short-lived access token is
    // exported.
    token_expires_at: getTokenExpiresAt(source),
    remember_me: getRememberMe(source),
  };
}

export function downloadNousCliAuthFile(
  payload: NousCliAuthPayload,
  filename: string = 'nous-auth.json'
): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

export async function downloadStoredNousCliAuth(): Promise<void> {
  const state = useAuthStore.getState();
  const supabase = createClient();
  const { data, error } = await supabase.auth.getSession();

  if (error) {
    throw new Error(error.message);
  }

  const payload = buildNousCliAuthPayload({
    session: data.session,
    organization: state.organization,
    user: state.user,
  });

  downloadNousCliAuthFile(payload);
}
