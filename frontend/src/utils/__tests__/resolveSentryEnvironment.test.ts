import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { resolveSentryEnvironment } =
  require('../../../config/resolveSentryEnvironment') as {
    resolveSentryEnvironment: (env?: NodeJS.ProcessEnv) => string;
  };

describe('resolveSentryEnvironment', () => {
  it('classifies Vercel preview builds as preview even though NODE_ENV is production', () => {
    expect(
      resolveSentryEnvironment({
        VERCEL_ENV: 'preview',
        NODE_ENV: 'production',
      } as NodeJS.ProcessEnv)
    ).toBe('preview');
  });

  it('lets an explicit application environment override the deployment environment', () => {
    expect(
      resolveSentryEnvironment({
        NEXT_PUBLIC_APP_ENV: 'dev',
        VERCEL_ENV: 'preview',
        NODE_ENV: 'production',
      } as NodeJS.ProcessEnv)
    ).toBe('dev');
  });

  it('falls back to NODE_ENV outside Vercel', () => {
    expect(
      resolveSentryEnvironment({ NODE_ENV: 'test' } as NodeJS.ProcessEnv)
    ).toBe('test');
  });

  it('defaults to development when no environment is available', () => {
    expect(resolveSentryEnvironment({} as NodeJS.ProcessEnv)).toBe(
      'development'
    );
  });
});
