import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

test('backend dev container does not use uvicorn reload', () => {
  const composeFile = resolve(
    process.cwd(),
    'config/docker-compose/docker-compose.development.yml'
  );
  const content = readFileSync(composeFile, 'utf8');

  assert.equal(
    content.includes(
      'command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload'
    ),
    false,
    'Dockerized backend dev server should not run with --reload'
  );

  assert.equal(
    content.includes('python -m pip install --no-cache-dir langgraph'),
    true,
    'Dockerized backend dev server should install langgraph before startup'
  );
});
