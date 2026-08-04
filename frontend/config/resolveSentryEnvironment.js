const firstNonEmpty = (...values) =>
  values.find((value) => typeof value === 'string' && value.trim())?.trim();

const resolveSentryEnvironment = (env = process.env) =>
  firstNonEmpty(
    env.NEXT_PUBLIC_APP_ENV,
    env.VERCEL_TARGET_ENV,
    env.VERCEL_ENV,
    env.NODE_ENV
  ) || 'development';

module.exports = { resolveSentryEnvironment };
