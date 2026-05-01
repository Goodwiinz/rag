/**
 * @vitest-environment node
 */
import { describe, expect, test, vi } from 'vitest';
import type { Mock, MockedFunction } from 'vitest';
vi.mock('@clack/prompts', () => ({
  text: vi.fn(),
  isCancel: vi.fn(() => false),
}));
vi.mock('../services/draft');

import { writeDraft, readDraft, clearDraft } from '../services/draft';

const mockedWriteDraft = writeDraft as MockedFunction<typeof writeDraft>;
const mockedClearDraft = clearDraft as MockedFunction<typeof clearDraft>;
void mockedWriteDraft;
void readDraft;

import { buildCompleter, isPromptCancel, CANCEL } from '../prompt';

describe('isPromptCancel', () => {
  test('detects the CANCEL sentinel', () => {
    expect(isPromptCancel(CANCEL)).toBe(true);
    expect(isPromptCancel('cancel')).toBe(false);
    expect(isPromptCancel(null)).toBe(false);
  });
});

describe('buildCompleter', () => {
  test('completes from the slash command list when the line starts with /', () => {
    const c = buildCompleter({});
    const out = c('/h');
    expect(out).toEqual(expect.arrayContaining(['/help', '/history']));
  });

  test('completes from the slash command list when the line is empty', () => {
    const c = buildCompleter({});
    const out = c('');
    expect(out).toEqual(
      expect.arrayContaining(['/new', '/threads', '/projects', '/quit'])
    );
  });

  test('completes thread ids after /forget', () => {
    const c = buildCompleter({
      knownThreadIds: ['thread_alpha', 'thread_beta'],
    });
    const out = c('/forget ');
    expect(out).toEqual(['thread_alpha', 'thread_beta']);
  });

  test('completes project ids after /context project', () => {
    const c = buildCompleter({
      knownProjectIds: ['proj_one', 'proj_two'],
    });
    const out = c('/context project ');
    expect(out).toEqual(['proj_one', 'proj_two']);
  });

  test('returns no completions for plain prose', () => {
    const c = buildCompleter({ knownThreadIds: ['t'], knownProjectIds: ['p'] });
    expect(c('hello world')).toEqual([]);
  });
});

describe('readPrompt — non-TTY initialValue passthrough', () => {
  test('passes initialValue to clack text fallback', async () => {
    // Already covered by clack mock in this file; verify the option is forwarded.
    const { readPrompt } = await import('../prompt');
    const prompts = await import('@clack/prompts');
    const textMock = prompts.text as Mock;
    textMock.mockResolvedValueOnce('result');
    await readPrompt({ message: '>', initialValue: 'restored' });
    expect(textMock).toHaveBeenCalledWith(
      expect.objectContaining({ initialValue: 'restored' })
    );
  });
});

describe('readPrompt — clears draft on submit (non-TTY)', () => {
  test('clearDraft is called when prompt resolves to a string', async () => {
    const { readPrompt } = await import('../prompt');
    const prompts = await import('@clack/prompts');
    (prompts.text as Mock).mockResolvedValueOnce('hello');
    await readPrompt({ message: '>' });
    expect(mockedClearDraft).toHaveBeenCalled();
  });
});
