/**
 * Join an incoming `populate-chat-input` payload onto the composer's draft.
 *
 * Two senders share this channel and want different things. The artifact
 * panel's Cite appends a short reference that should sit inline, separated by
 * a space. A quoted passage is a markdown block: its `>` only opens a
 * blockquote at the start of a line, so joining it with a space turns it into
 * a literal angle bracket and the quote renders as ordinary prose.
 *
 * The payload says which it is by whether it opens with a newline, so neither
 * sender needs to know about the other. With an empty composer the leading
 * newline comes off, so a fresh draft does not start on line two.
 */
export function appendToDraft(current: string, text: string): string {
  if (!current) return `${text.replace(/^\n+/, '')} `;
  return text.startsWith('\n') ? `${current}${text}` : `${current} ${text}`;
}
