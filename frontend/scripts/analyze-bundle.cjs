// Codecov bundle analysis (standalone, Turbopack-compatible).
//
// Next 16 builds with Turbopack by default, so the webpack-based
// @codecov/nextjs-webpack-plugin never runs. Instead we post-process the emitted
// client assets in `.next/static` with the bundler-agnostic analyzer.
//
// Runs as the tail of `pnpm build` (see package.json). BEST-EFFORT: it never
// fails the build — no token => skip, any upload error => warn + exit 0.
//
// The CODECOV_TOKEN is read from the environment and MUST NOT be committed.
// Set it in the Vercel project env (Production + Preview).

const path = require('path');
const { createAndUploadReport } = require('@codecov/bundle-analyzer');

const token = process.env.CODECOV_TOKEN;
if (!token) {
  console.log('[codecov-bundle] CODECOV_TOKEN unset — skipping bundle analysis');
  process.exit(0);
}

// Client-shipped assets only. `.next/static` is stable across `output: 'standalone'`.
const buildDirs = [path.join(__dirname, '..', '.next', 'static')];

// Vercel isn't an auto-detected CI provider for the plugin core, so feed the git
// context from its injected env vars. Only include defined values — passing
// `undefined` would clobber any value the core could otherwise infer.
const { VERCEL_GIT_REPO_OWNER, VERCEL_GIT_REPO_SLUG } = process.env;
const uploadOverrides = Object.fromEntries(
  Object.entries({
    sha: process.env.VERCEL_GIT_COMMIT_SHA,
    branch: process.env.VERCEL_GIT_COMMIT_REF,
    pr: process.env.VERCEL_GIT_PULL_REQUEST_ID,
    slug:
      VERCEL_GIT_REPO_OWNER && VERCEL_GIT_REPO_SLUG
        ? `${VERCEL_GIT_REPO_OWNER}/${VERCEL_GIT_REPO_SLUG}`
        : undefined,
  }).filter(([, v]) => v),
);

const coreOpts = {
  uploadToken: token,
  bundleName: 'nous-frontend',
  enableBundleAnalysis: true,
  dryRun: false,
  retryCount: 3,
  apiUrl: 'https://api.codecov.io',
  gitService: 'github',
  ...(Object.keys(uploadOverrides).length ? { uploadOverrides } : {}),
};

const bundleAnalyzerOpts = {
  // Don't report source maps as shipped weight.
  ignorePatterns: ['*.map'],
  // Collapse Next's content-hashed chunk names so reports diff cleanly across builds.
  normalizeAssetsPattern: '[name]-[hash].js',
};

createAndUploadReport(buildDirs, coreOpts, bundleAnalyzerOpts)
  .then((report) => console.log('[codecov-bundle] uploaded:', report))
  .catch((err) => {
    console.warn(
      '[codecov-bundle] upload failed (non-blocking):',
      err && err.message ? err.message : err,
    );
    // Never break the deploy on a coverage/bundle upload hiccup.
  });
