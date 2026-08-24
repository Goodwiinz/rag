import { notFound } from 'next/navigation';

import { CitationRenderer } from '@/components/chat/CitationRenderer';

const RESPONSE = `## Evidence synthesis

The retrieved studies agree that retrieval quality determines the ceiling for grounded generation [Doc 1]. Reranking improves the ordering of plausible passages [Doc 2], while answer-level verification catches unsupported claims before delivery [Doc 3].

### Recommended response contract

- Lead with the direct answer and preserve paragraph boundaries [Doc 1].
- Keep citations inside the statement, list item, or table cell they support [Doc 2].
- Use a local scroll container for wide data rather than widening the reading column.

| Layer | Responsibility | Evidence |
| --- | --- | --- |
| Retrieval | Return relevant passages | Recall and ranking diagnostics [Doc 1] |
| Synthesis | Produce a concise grounded answer | Inline source attribution [Doc 2] |
| Verification | Reject unsupported claims | Claim-level checks [Doc 3] |

> A polished response keeps its semantic structure when citations appear.

Use \`search_documents\` for project evidence, and reserve fenced code for commands:

\`\`\`bash
corepack pnpm@10.18.2 test
\`\`\`

**Bottom line:** one Markdown parse should own headings, prose, citations, tables, and code.`;

const CITATIONS = [
  {
    documentId: 'visual-source-1',
    title: 'Retrieval quality evaluation',
    score: 0.93,
    source: 'Project corpus',
    content:
      'Evaluation of retrieval recall, ranking quality, and passage relevance.',
  },
  {
    documentId: 'visual-source-2',
    title: 'Reranking and grounded synthesis',
    score: 0.88,
    source: 'Research notes',
    content: 'Analysis of reranking behavior and inline source attribution.',
  },
  {
    documentId: 'visual-source-3',
    title: 'Claim verification protocol',
    score: 0.84,
    source: 'Evaluation suite',
    content:
      'Claim-level checks for unsupported or weakly supported statements.',
  },
];

export default function ResponseRendererVisualFixture(): React.ReactElement {
  if (process.env.NEXT_PUBLIC_VISUAL_TEST_FIXTURES !== '1') notFound();

  return (
    <main className="min-h-screen bg-(--nous-bg-1) px-4 py-8 text-(--nous-fg-1) sm:px-8 sm:py-12">
      <article
        data-testid="response-renderer-fixture"
        className="nous-chat-body mx-auto w-full max-w-(--nous-chat-col)"
      >
        <CitationRenderer content={RESPONSE} citations={CITATIONS} />
      </article>
    </main>
  );
}
