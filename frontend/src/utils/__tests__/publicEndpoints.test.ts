import { afterEach, describe, expect, it } from 'vitest';
import {
  getPublicApiBaseUrl,
  getPublicApiOrigin,
  getPublicWebSocketOrigin,
} from '@/utils/publicEndpoints';

describe('public endpoint resolution', () => {
  const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
  const originalApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  const originalWsUrl = process.env.NEXT_PUBLIC_WS_URL;
  const originalWebsocketUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL;
  const originalTestOrigin = (
    globalThis as typeof globalThis & {
      __TEST_BROWSER_ORIGIN__?: string;
    }
  ).__TEST_BROWSER_ORIGIN__;

  const setLocation = (origin: string) => {
    (
      globalThis as typeof globalThis & { __TEST_BROWSER_ORIGIN__?: string }
    ).__TEST_BROWSER_ORIGIN__ = origin;
  };

  const restoreEnv = (key: string, value: string | undefined) => {
    if (value === undefined) {
      delete process.env[key];
      return;
    }

    process.env[key] = value;
  };

  afterEach(() => {
    restoreEnv('NEXT_PUBLIC_API_URL', originalApiUrl);
    restoreEnv('NEXT_PUBLIC_API_BASE_URL', originalApiBaseUrl);
    restoreEnv('NEXT_PUBLIC_WS_URL', originalWsUrl);
    restoreEnv('NEXT_PUBLIC_WEBSOCKET_URL', originalWebsocketUrl);
    (
      globalThis as typeof globalThis & { __TEST_BROWSER_ORIGIN__?: string }
    ).__TEST_BROWSER_ORIGIN__ = originalTestOrigin;
  });

  it('derives the API and WebSocket origins from the dev app hostname', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_WS_URL;
    delete process.env.NEXT_PUBLIC_WEBSOCKET_URL;

    setLocation('https://dev-app.gen-text.app/login');

    expect(getPublicApiOrigin()).toBe('https://dev-api.gen-text.app');
    expect(getPublicApiBaseUrl()).toBe('https://dev-api.gen-text.app/api/v1');
    expect(getPublicWebSocketOrigin()).toBe('wss://dev-api.gen-text.app');
  });

  it.each([
    [
      'https://staging-app.gen-text.app/login',
      'https://staging-api.gen-text.app',
    ],
    ['https://app.gen-text.app/login', 'https://api.gen-text.app'],
  ])(
    'derives the split-deployment API origin for %s',
    (browserOrigin, expectedApiOrigin) => {
      delete process.env.NEXT_PUBLIC_API_URL;
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
      delete process.env.NEXT_PUBLIC_WS_URL;
      delete process.env.NEXT_PUBLIC_WEBSOCKET_URL;

      setLocation(browserOrigin);

      expect(getPublicApiOrigin()).toBe(expectedApiOrigin);
      expect(getPublicApiBaseUrl()).toBe(`${expectedApiOrigin}/api/v1`);
      expect(getPublicWebSocketOrigin()).toBe(
        expectedApiOrigin.replace(/^http/, 'ws')
      );
    }
  );

  it('uses configured API endpoints from Vercel preview deployments', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev-api.gen-text.app';
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_WS_URL;
    delete process.env.NEXT_PUBLIC_WEBSOCKET_URL;

    setLocation('https://nous-platform-git-feature-goodwiinz.vercel.app');

    expect(getPublicApiOrigin()).toBe('https://dev-api.gen-text.app');
    expect(getPublicApiBaseUrl()).toBe('https://dev-api.gen-text.app/api/v1');
    expect(getPublicWebSocketOrigin()).toBe('wss://dev-api.gen-text.app');
  });

  it('ignores baked localhost public env on remote hosts', () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8000/api/v1';
    process.env.NEXT_PUBLIC_WS_URL = 'ws://localhost:8000';

    setLocation('https://dev-app.gen-text.app/login');

    expect(getPublicApiOrigin()).toBe('https://dev-api.gen-text.app');
    expect(getPublicApiBaseUrl()).toBe('https://dev-api.gen-text.app/api/v1');
    expect(getPublicWebSocketOrigin()).toBe('wss://dev-api.gen-text.app');
  });

  it('keeps localhost defaults for local development', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_WS_URL;
    delete process.env.NEXT_PUBLIC_WEBSOCKET_URL;

    setLocation('http://localhost:3000/login');

    expect(getPublicApiOrigin()).toBe('http://localhost:8000');
    expect(getPublicApiBaseUrl()).toBe('http://localhost:8000/api/v1');
    expect(getPublicWebSocketOrigin()).toBe('ws://localhost:8000');
  });

  it('ignores baked remote public env on localhost', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev-api.gen-text.app';
    process.env.NEXT_PUBLIC_API_BASE_URL =
      'https://dev-api.gen-text.app/api/v1';
    process.env.NEXT_PUBLIC_WS_URL = 'wss://dev-api.gen-text.app';

    setLocation('http://localhost:3000/login');

    expect(getPublicApiOrigin()).toBe('http://localhost:8000');
    expect(getPublicApiBaseUrl()).toBe('http://localhost:8000/api/v1');
    expect(getPublicWebSocketOrigin()).toBe('ws://localhost:8000');
  });

  it('normalizes trailing slashes on same-environment configured values without producing double slashes', () => {
    // Browser + configured env BOTH remote, so `shouldIgnoreConfiguredOrigin`
    // does NOT discard the env (the previous version of this test failed to
    // exercise trimTrailingSlash because cross-env values were thrown away
    // before reaching the concat path).
    process.env.NEXT_PUBLIC_API_URL = 'https://dev-api.gen-text.app/';
    process.env.NEXT_PUBLIC_API_BASE_URL =
      'https://dev-api.gen-text.app/api/v1/';

    setLocation('https://dev-app.gen-text.app/login');

    const origin = getPublicApiOrigin();
    const baseUrl = getPublicApiBaseUrl();

    // Trailing slashes are trimmed on both origin and base.
    expect(origin).toBe('https://dev-api.gen-text.app');
    expect(baseUrl).toBe('https://dev-api.gen-text.app/api/v1');

    // Explicit assertion that no component path contains `//` (the protocol's
    // `://` is allowed, but not `/api//v1` or a trailing `//`).
    const pathOnly = baseUrl.replace(/^[a-z]+:\/\//, '');
    expect(pathOnly).not.toMatch(/\/\//);
  });

  it('honors a caller-supplied default path when deriving from the browser origin', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;

    setLocation('http://localhost:3000/login');

    expect(getPublicApiBaseUrl('/api/v2')).toBe('http://localhost:8000/api/v2');
    expect(getPublicApiBaseUrl('/custom')).toBe('http://localhost:8000/custom');
  });

  it('uses explicitly configured public endpoints when they are not localhost', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://staging-api.gen-text.app';
    process.env.NEXT_PUBLIC_WS_URL = 'wss://staging-api.gen-text.app';

    setLocation('https://dev-app.gen-text.app/login');

    expect(getPublicApiOrigin()).toBe('https://staging-api.gen-text.app');
    expect(getPublicApiBaseUrl()).toBe(
      'https://staging-api.gen-text.app/api/v1'
    );
    expect(getPublicWebSocketOrigin()).toBe('wss://staging-api.gen-text.app');
  });
});
