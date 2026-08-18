import type { Root, Element, Text, RootContent } from 'hast';

/** How much of the tail reads as "just arrived". Roughly the last few words. */
const DEFAULT_TAIL_CHARS = 24;

type Parent = Root | Element;

/** KaTeX output — generated markup, not streamed prose. Tinting inside it
 * would colour a single glyph of a rendered expression. */
function isKatexElement(node: Element): boolean {
  const cls = node.properties?.className;
  // hast normalises space-separated properties, so className is an array.
  const classes = Array.isArray(cls) ? cls : [];
  return classes.includes('katex') || classes.includes('katex-display');
}

/** Depth-first walk to the last text node that carries visible characters. */
function findLastTextNode(
  node: Parent
): { parent: Parent; index: number; text: Text } | null {
  for (let i = node.children.length - 1; i >= 0; i -= 1) {
    const child = node.children[i] as RootContent;
    if (child.type === 'text' && child.value.trim() !== '') {
      return { parent: node, index: i, text: child };
    }
    if (child.type === 'element') {
      // Code keeps its own colouring; tinting inside it would fight the
      // syntax highlighter and read as a highlight rather than as freshness.
      if (child.tagName === 'code' || child.tagName === 'pre') continue;
      // Skip the whole expression: a message that ends with math gets its
      // tint on the prose before it instead.
      if (isKatexElement(child)) continue;
      const found = findLastTextNode(child);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Wraps the trailing characters of a streamed answer in
 * `<span data-fresh="true">`, so the newest text can be tinted and settle
 * into ink as more arrives.
 *
 * This runs on the parsed tree rather than on the source string, which is the
 * whole point: splitting the markdown into words before parsing (the shape the
 * upstream element uses) would mean giving up live bold, lists and headings
 * for the duration of the stream. Tagging after the parse keeps the markdown
 * and still marks the tail.
 *
 * Each token re-renders the tree, so the span is re-created and the newest
 * text is always the tinted one — no per-node bookkeeping across renders.
 */
export function rehypeFreshTail(options?: { chars?: number }) {
  const chars = options?.chars ?? DEFAULT_TAIL_CHARS;

  return (tree: Root): void => {
    if (chars <= 0) return;
    const found = findLastTextNode(tree);
    if (!found) return;

    const { parent, index, text } = found;
    const value = text.value;
    let splitAt = Math.max(0, value.length - chars);
    // A raw UTF-16 index can land between the halves of a surrogate pair
    // (an emoji, say), leaving lone surrogates in sibling DOM nodes that
    // render as replacement characters. Step back one unit so the whole
    // pair stays in the tail. ponytail: code-point guard only — a ZWJ
    // sequence can still split into valid separate emoji for the one render
    // where the boundary crosses it; reach for Intl.Segmenter if that shows.
    const codeUnit = value.charCodeAt(splitAt);
    if (splitAt > 0 && codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      splitAt -= 1;
    }
    const head = value.slice(0, splitAt);
    const tail = value.slice(splitAt);
    if (tail === '') return;

    const freshSpan: Element = {
      type: 'element',
      tagName: 'span',
      properties: { dataFresh: 'true' },
      children: [{ type: 'text', value: tail }],
    };

    const replacement: RootContent[] = head
      ? [{ type: 'text', value: head } as Text, freshSpan]
      : [freshSpan];
    parent.children.splice(index, 1, ...replacement);
  };
}

export default rehypeFreshTail;
