import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'fs';
import * as os from 'os';
import * as path from 'path';

export interface CachedMessage {
  role: 'user' | 'assistant';
  content: string;
  model?: string;
  client_message_id?: string;
  ended_at: string;
}

export interface TurnInput {
  user: { content: string; client_message_id: string };
  assistant: { content: string; model?: string };
  ended_at: string;
}

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function threadFile(id: string): string {
  return path.join(configDir(), 'threads', `${id}.jsonl`);
}

export function appendTurn(threadId: string, turn: TurnInput): void {
  const file = threadFile(threadId);
  const dir = path.dirname(file);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const userLine: CachedMessage = {
    role: 'user',
    content: turn.user.content,
    client_message_id: turn.user.client_message_id,
    ended_at: turn.ended_at,
  };
  const asstLine: CachedMessage = {
    role: 'assistant',
    content: turn.assistant.content,
    model: turn.assistant.model,
    ended_at: turn.ended_at,
  };
  appendFileSync(
    file,
    JSON.stringify(userLine) + '\n' + JSON.stringify(asstLine) + '\n',
    'utf-8'
  );
}

export function loadMessages(threadId: string): CachedMessage[] {
  const file = threadFile(threadId);
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as CachedMessage);
}
