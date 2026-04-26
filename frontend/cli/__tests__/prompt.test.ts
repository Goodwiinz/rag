/**
 * @jest-environment node
 */
jest.mock('@clack/prompts', () => ({
  text: jest.fn(),
  isCancel: jest.fn(() => false),
}));

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
