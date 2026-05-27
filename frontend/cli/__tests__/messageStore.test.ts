import { mkdtempSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { beforeEach, describe, expect, it } from 'vitest';

import { appendTurn, loadMessages } from '../services/messageStore';

let dir: string;
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'nous-cli-'));
  process.env.NOUS_CONFIG_DIR = dir;
});

describe('messageStore', () => {
  it('appends one JSONL line per message and reads back in order', () => {
    appendTurn('t-1', {
      user: { content: 'hi', client_message_id: 'abc' },
      assistant: { content: 'hey', model: 'gpt-5-mini' },
      ended_at: '2026-05-13T00:00:00Z',
    });
    appendTurn('t-1', {
      user: { content: 'and?', client_message_id: 'def' },
      assistant: { content: 'cool', model: 'gpt-5-mini' },
      ended_at: '2026-05-13T00:01:00Z',
    });

    const msgs = loadMessages('t-1');
    expect(msgs.map((m) => m.role)).toEqual([
      'user',
      'assistant',
      'user',
      'assistant',
    ]);
    expect(msgs[2].content).toBe('and?');

    const raw = readFileSync(join(dir, 'threads', 't-1.jsonl'), 'utf-8')
      .trim()
      .split('\n');
    expect(raw).toHaveLength(4);
  });

  it('returns [] when no cache exists', () => {
    expect(loadMessages('missing')).toEqual([]);
  });
});
