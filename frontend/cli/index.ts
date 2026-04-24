#!/usr/bin/env tsx
import { isTokenExpired, login } from './auth/deviceFlow';
import { loadConfig } from './auth/store';
import { runOneShot, runRepl } from './repl';

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'login') {
    await login();
    process.exit(0);
  }

  const config = loadConfig();
  if (!config) {
    console.error('Not logged in. Run: ./nous login');
    process.exit(1);
  }
  if (isTokenExpired(config.expires_at)) {
    console.error('Session expired. Run: ./nous login');
    process.exit(1);
  }

  if (args.length > 0) {
    await runOneShot(args.join(' '));
  } else {
    await runRepl();
  }
}

main().catch((err) => {
  console.error((err as Error).message);
  process.exit(1);
});
