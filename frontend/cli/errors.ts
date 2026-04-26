export type ErrorKind =
  | 'network'
  | 'auth'
  | 'not_found_thread'
  | 'transient_5xx'
  | 'idle_timeout'
  | 'cancelled'
  | 'unknown';

export interface ClassifiedError {
  kind: ErrorKind;
  retryable: boolean;
  userMessage: string;
  hint?: string;
  raw?: unknown;
}

function messageOf(input: unknown): string {
  if (input == null) return '';
  if (typeof input === 'string') return input;
  if (input instanceof Error) return input.message ?? '';
  if (typeof input === 'object' && 'message' in input) {
    const m = (input as { message?: unknown }).message;
    return typeof m === 'string' ? m : '';
  }
  return '';
}

function codeOf(input: unknown): string | undefined {
  if (input instanceof Error) {
    const direct = (input as Error & { code?: unknown }).code;
    if (typeof direct === 'string') return direct;
    const cause = (input as Error & { cause?: unknown }).cause;
    if (cause && typeof cause === 'object' && 'code' in cause) {
      const c = (cause as { code?: unknown }).code;
      if (typeof c === 'string') return c;
    }
  }
  return undefined;
}

const NETWORK_CODES = new Set(['ECONNREFUSED', 'ENOTFOUND', 'EAI_AGAIN']);

export function classifyError(input: unknown): ClassifiedError {
  const msg = messageOf(input);
  const code = codeOf(input);

  if (code && NETWORK_CODES.has(code)) {
    return network(msg, input);
  }
  if (/getaddrinfo|fetch failed/i.test(msg)) {
    return network(msg, input);
  }

  if (input instanceof Error && input.name === 'AbortError') {
    return {
      kind: 'cancelled',
      retryable: false,
      userMessage: 'Cancelled.',
      raw: input,
    };
  }

  const idleMatch = msg.match(/^IDLE_TIMEOUT:(\d+)$/);
  if (idleMatch) {
    return {
      kind: 'idle_timeout',
      retryable: true,
      userMessage: `Agent went silent at ${idleMatch[1]}s.`,
      hint: 'Retrying once…',
      raw: input,
    };
  }

  if (/thread not found/i.test(msg)) {
    return {
      kind: 'not_found_thread',
      retryable: true,
      userMessage: 'Cached thread expired.',
      hint: 'Starting a fresh thread…',
      raw: input,
    };
  }

  if (/Stream failed: 5\d\d/.test(msg) || /timeout|timed out/i.test(msg)) {
    return {
      kind: 'transient_5xx',
      retryable: true,
      userMessage: 'Backend hiccup (HTTP 5xx).',
      hint: 'Retrying once…',
      raw: input,
    };
  }

  if (/not logged in|\b401\b|\b403\b|unauthorized/i.test(msg)) {
    return {
      kind: 'auth',
      retryable: false,
      userMessage: 'Session expired or unauthorized.',
      hint: 'Run ./nous login.',
      raw: input,
    };
  }

  return {
    kind: 'unknown',
    retryable: false,
    userMessage: msg || 'Unknown error.',
    raw: input,
  };
}

function network(msg: string, raw: unknown): ClassifiedError {
  const urlMatch = msg.match(/(https?:\/\/[^\s)]+)/);
  const url = urlMatch ? urlMatch[1] : null;
  return {
    kind: 'network',
    retryable: true,
    userMessage: url
      ? `Backend not reachable at ${url}.`
      : 'Backend not reachable.',
    hint: 'Set NOUS_API_URL or run /settings.',
    raw,
  };
}
