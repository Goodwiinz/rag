export interface ParsedCommand {
  command: string;
  args: string[];
}

export function parseSlashCommand(input: string): ParsedCommand | null {
  const normalized = input.replace(/^[\s❯>$%]+/, '');
  if (!normalized.startsWith('/')) return null;
  const parts = normalized.slice(1).trim().split(/\s+/);
  return { command: parts[0], args: parts.slice(1) };
}

export type SlashCommandHandler = (parsed: ParsedCommand) => boolean;
