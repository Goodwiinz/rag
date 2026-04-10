const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1', '0.0.0.0']);

type GlobalWithTestOrigin = typeof globalThis & {
  __TEST_BROWSER_ORIGIN__?: string;
};

const trimTrailingSlash = (value: string): string => value.replace(/\/$/, '');

const isLocalHostname = (hostname: string): boolean =>
  LOCAL_HOSTNAMES.has(hostname);

const parseUrl = (value: string): URL | null => {
  try {
    return new URL(value);
  } catch {
    return null;
  }
};

const getBrowserLocation = (): URL | null => {
  const testOrigin = (globalThis as GlobalWithTestOrigin).__TEST_BROWSER_ORIGIN__;
  if (testOrigin) {
    return parseUrl(testOrigin);
  }

  if (typeof window === 'undefined') {
    return null;
  }

  return parseUrl(window.location.origin);
};

const shouldIgnoreConfiguredOrigin = (value: string): boolean => {
  const configured = parseUrl(value);
  const browserLocation = getBrowserLocation();

  if (!configured || !browserLocation) {
    return false;
  }

  return (
    isLocalHostname(configured.hostname) &&
    !isLocalHostname(browserLocation.hostname)
  );
};

const mapFrontendHostToApiHost = (hostname: string): string => {
  if (hostname.startsWith('dev-app.')) {
    return hostname.replace(/^dev-app\./, 'dev-api.');
  }

  if (hostname.startsWith('staging-app.')) {
    return hostname.replace(/^staging-app\./, 'staging-api.');
  }

  if (hostname.startsWith('app.')) {
    return hostname.replace(/^app\./, 'api.');
  }

  return hostname;
};

const getConfiguredOrigin = (...values: Array<string | undefined>): string => {
  for (const value of values) {
    const trimmed = value?.trim();
    if (!trimmed || shouldIgnoreConfiguredOrigin(trimmed)) {
      continue;
    }

    return trimTrailingSlash(trimmed);
  }

  return '';
};

export const getPublicApiOrigin = (): string => {
  const configured = getConfiguredOrigin(process.env.NEXT_PUBLIC_API_URL);
  if (configured) {
    return configured;
  }

  const browserLocation = getBrowserLocation();
  if (!browserLocation) {
    return '';
  }

  if (isLocalHostname(browserLocation.hostname)) {
    return 'http://localhost:8000';
  }

  const apiHost = mapFrontendHostToApiHost(browserLocation.hostname);
  if (apiHost !== browserLocation.hostname) {
    return `${browserLocation.protocol}//${apiHost}`;
  }

  return browserLocation.origin;
};

export const getPublicApiBaseUrl = (defaultPath: string = '/api/v1'): string => {
  const configuredBaseUrl = getConfiguredOrigin(
    process.env.NEXT_PUBLIC_API_BASE_URL
  );
  if (configuredBaseUrl) {
    if (configuredBaseUrl.startsWith('/')) {
      return trimTrailingSlash(configuredBaseUrl);
    }

    if (/\/api\/v[0-9]+\/?$/.test(configuredBaseUrl)) {
      return trimTrailingSlash(configuredBaseUrl);
    }

    return `${configuredBaseUrl}${defaultPath}`;
  }

  const origin = getPublicApiOrigin();
  return origin ? `${origin}${defaultPath}` : defaultPath;
};

export const getPublicWebSocketOrigin = (): string => {
  const configured = getConfiguredOrigin(
    process.env.NEXT_PUBLIC_WS_URL,
    process.env.NEXT_PUBLIC_WEBSOCKET_URL
  );
  if (configured) {
    return configured;
  }

  const apiOrigin = getPublicApiOrigin();
  if (apiOrigin) {
    return apiOrigin.replace(/^http/, 'ws');
  }

  return 'ws://localhost:8000';
};
