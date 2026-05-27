export interface ExportableMessage {
  role: 'user' | 'assistant' | string;
  content: string;
  timestamp: number;
}

export function exportAsMarkdown(
  title: string,
  messages: ReadonlyArray<ExportableMessage>
): string {
  const header = `# ${title}\n\n`;
  const body = messages
    .map((m) => {
      const who = m.role === 'user' ? '**You**' : '**Assistant**';
      const when = new Date(m.timestamp).toISOString();
      return `${who} · ${when}\n\n${m.content}\n`;
    })
    .join('\n---\n\n');
  return header + body;
}

export function exportAsJson(
  title: string,
  messages: ReadonlyArray<ExportableMessage>
): string {
  return JSON.stringify({ title, messages }, null, 2);
}

export function downloadFile(
  name: string,
  mime: string,
  content: string
): void {
  if (typeof window === 'undefined') return;
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
