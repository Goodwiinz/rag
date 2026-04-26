import * as p from '@clack/prompts';

export const CONFIRM_CANCEL = Symbol.for('nous.confirmKey.cancel');

export function isConfirmCancel(value: unknown): boolean {
  return value === CONFIRM_CANCEL;
}

export interface ConfirmKeyOptions {
  message: string;
  default?: boolean;
}

export async function confirmKey(
  opts: ConfirmKeyOptions
): Promise<boolean | typeof CONFIRM_CANCEL> {
  const def = opts.default ?? true;
  if (!process.stdin.isTTY) {
    const r = await p.confirm({ message: opts.message });
    if (p.isCancel(r)) return CONFIRM_CANCEL;
    return r as boolean;
  }
  const suffix = def ? '[Y/n]' : '[y/N]';
  process.stdout.write(`${opts.message} ${suffix} `);
  return new Promise((resolve) => {
    const stdin = process.stdin;
    const wasRaw = stdin.isRaw;
    stdin.setRawMode?.(true);
    stdin.resume();
    const onData = (chunk: Buffer) => {
      const ch = chunk[0];
      stdin.off('data', onData);
      stdin.setRawMode?.(wasRaw ?? false);
      stdin.pause();
      process.stdout.write('\n');
      // Ctrl-C → real cancel sentinel (not a function reference, which the
      // caller would treat as truthy and silently approve)
      if (ch === 0x03) return resolve(CONFIRM_CANCEL);
      const c = String.fromCharCode(ch).toLowerCase();
      if (c === 'y') return resolve(true);
      if (c === 'n') return resolve(false);
      // Enter / anything else → default
      return resolve(def);
    };
    stdin.on('data', onData);
  });
}
