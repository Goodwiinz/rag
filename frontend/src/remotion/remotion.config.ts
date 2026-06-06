/**
 * Remotion config — enables Tailwind in the Remotion bundler.
 *
 * Move this to the project root (next to package.json) if you run the Remotion
 * CLI from there; the CLI auto-loads `remotion.config.ts` from the cwd.
 * Requires: `@remotion/tailwind` and a `tailwind.config.js` whose `content`
 * globs include `src/remotion/**`.
 */

import { Config } from '@remotion/cli/config';
import { enableTailwind } from '@remotion/tailwind';

Config.overrideWebpackConfig((currentConfig) => {
  return enableTailwind(currentConfig);
});

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
