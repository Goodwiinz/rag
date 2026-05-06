import { expect, test } from 'vitest';
import { parseSlashCommand } from '../../hooks/useSlashCommands';

test('parses /new', () => {
  expect(parseSlashCommand('/new')).toEqual({ command: 'new', args: [] });
});

test('parses /context project <id>', () => {
  expect(parseSlashCommand('/context project proj_123')).toEqual({
    command: 'context',
    args: ['project', 'proj_123'],
  });
});

test('parses /context clear', () => {
  expect(parseSlashCommand('/context clear')).toEqual({
    command: 'context',
    args: ['clear'],
  });
});

test('returns null for non-slash input', () => {
  expect(parseSlashCommand('hello')).toBeNull();
});

test('strips leading prompt characters before parsing', () => {
  expect(parseSlashCommand('❯ /threads')).toEqual({
    command: 'threads',
    args: [],
  });
  expect(parseSlashCommand('> /new')).toEqual({ command: 'new', args: [] });
  expect(parseSlashCommand('$ /quit')).toEqual({ command: 'quit', args: [] });
  expect(parseSlashCommand('% /help')).toEqual({ command: 'help', args: [] });
});

test('strips leading whitespace before slash', () => {
  expect(parseSlashCommand('  /threads')).toEqual({
    command: 'threads',
    args: [],
  });
});

test('parses /quit', () => {
  expect(parseSlashCommand('/quit')).toEqual({ command: 'quit', args: [] });
});
