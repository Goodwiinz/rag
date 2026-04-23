import * as os from 'os';
import * as path from 'path';

process.env.NOUS_CONFIG_DIR = path.join(
  os.tmpdir(),
  `.nous-test-${Date.now()}`
);

import {
  loadConfig,
  saveConfig,
  clearConfig,
  NousConfig,
} from '../../auth/store';

afterEach(() => {
  clearConfig();
});

test('returns null when no config exists', () => {
  expect(loadConfig()).toBeNull();
});

test('saves and loads config', () => {
  const config: NousConfig = {
    token: 'tok_abc',
    user_email: 'test@example.com',
    organization_id: 'org_1',
    expires_at: '2099-01-01T00:00:00Z',
    thread_id: null,
  };
  saveConfig(config);
  expect(loadConfig()).toEqual(config);
});

test('clearConfig removes the file', () => {
  saveConfig({
    token: 'x',
    user_email: 'a@b.com',
    organization_id: 'o',
    expires_at: '2099-01-01T00:00:00Z',
    thread_id: null,
  });
  clearConfig();
  expect(loadConfig()).toBeNull();
});
