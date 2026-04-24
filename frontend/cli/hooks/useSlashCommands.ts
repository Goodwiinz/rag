export interface ParsedCommand {
  command: string;
  args: string[];
}

export function parseSlashCommand(input: string): ParsedCommand | null {
  if (!input.startsWith('/')) return null;
  const parts = input.slice(1).trim().split(/\s+/);
  return { command: parts[0], args: parts.slice(1) };
}

export type SlashCommandHandler = (parsed: ParsedCommand) => boolean;
