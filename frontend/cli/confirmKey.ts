import * as p from '@clack/prompts';

export interface ConfirmKeyOptions {
  message: string;
  default?: boolean;
}

export async function confirmKey(
  opts: ConfirmKeyOptions
): Promise<boolean | symbol> {
  const def = opts.default ?? true;
  if (!process.stdin.isTTY) {
    const r = await p.confirm({ message: opts.message });
    return r;
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
      // Ctrl-C
      if (ch === 0x03) return resolve(p.isCancel as unknown as symbol);
      const c = String.fromCharCode(ch).toLowerCase();
      if (c === 'y') return resolve(true);
      if (c === 'n') return resolve(false);
      // Enter / anything else → default
      return resolve(def);
    };
    stdin.on('data', onData);
  });
}
