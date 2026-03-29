import { useAuthStore } from '@/stores/authStore';

interface NousCliAuthSource {
  token: string | null;
  refreshTokenValue: string | null;
  tokenExpiresAt: number | null;
  refreshExpiresAt: number | null;
  rememberMe: boolean;
  organization: {
    id: string;
    name?: string;
  } | null;
  user: {
    email?: string;
    organization_id?: string;
    organization_name?: string;
  } | null;
}

export interface NousCliAuthPayload {
  version: 1;
  source: 'frontend-login';
  exported_at: string;
  token: string;
  organization_id: string;
  organization_name?: string;
  user_email?: string;
  refresh_token?: string;
  token_expires_at: number | null;
  refresh_expires_at: number | null;
  remember_me: boolean;
}

export function buildNousCliAuthPayload(
  source: NousCliAuthSource
): NousCliAuthPayload {
  const organizationId = source.organization?.id ?? source.user?.organization_id;
  const organizationName =
    source.organization?.name ?? source.user?.organization_name;

  if (!source.token) {
    throw new Error('Cannot export NOUS CLI auth without a token.');
  }
  if (!organizationId) {
    throw new Error('Cannot export NOUS CLI auth without an organization.');
  }

  return {
    version: 1,
    source: 'frontend-login',
    exported_at: new Date().toISOString(),
    token: source.token,
    organization_id: organizationId,
    organization_name: organizationName,
    user_email: source.user?.email,
    refresh_token: source.refreshTokenValue ?? undefined,
    token_expires_at: source.tokenExpiresAt,
    refresh_expires_at: source.refreshExpiresAt,
    remember_me: source.rememberMe,
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

export function downloadStoredNousCliAuth(): void {
  const state = useAuthStore.getState();
  const payload = buildNousCliAuthPayload(state);
  downloadNousCliAuthFile(payload);
}
