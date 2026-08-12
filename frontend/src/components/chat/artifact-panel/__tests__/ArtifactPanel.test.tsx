/**
 * ArtifactPanel: renders the focused artifact beside the chat — header
 * actions (close, pin, rail toggle, full-page link) and per-kind bodies.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from '@testing-library/react';
import { render, screen, waitFor } from '@/test/test-utils';

import { ArtifactPanel } from '../ArtifactPanel';
import { useArtifactPanelStore, type Artifact } from '@/store/artifactPanelStore';
import { documentService } from '@/services/documentService';

vi.mock('@/services/documentService', () => ({
  documentService: {
    getDocument: vi.fn(),
  },
}));

// The inline viewer fetches blob URLs through the api client; its behavior is
// covered by its own extraction source. Stub it to isolate panel wiring.
vi.mock('@/components/documents/DocumentInlineViewer', () => ({
  DocumentInlineViewer: ({ filename }: { filename: string }) => (
    <div data-testid="inline-viewer">{filename}</div>
  ),
}));

const mockGetDocument = vi.mocked(documentService.getDocument);

const docArtifact: Artifact = {
  kind: 'document',
  id: 'doc-1',
  title: 'RLHF Survey',
};

describe('ArtifactPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    act(() => {
      useArtifactPanelStore.setState({
        artifact: docArtifact,
        isOpen: true,
        pinned: false,
      });
    });
    mockGetDocument.mockResolvedValue({
      success: true,
      data: {
        id: 'doc-1',
        user_id: 'u1',
        organization_id: 'org1',
        title: 'RLHF Survey',
        filename: 'rlhf-survey.pdf',
        file_type: 'pdf',
        processing_status: 'indexed',
        metadata: {},
      },
    } as Awaited<ReturnType<typeof documentService.getDocument>>);
  });

  it('renders a document artifact through the inline viewer', async () => {
    render(<ArtifactPanel artifact={docArtifact} />);

    expect(
      screen.getByRole('region', { name: 'Artifact viewer' })
    ).toBeInTheDocument();
    expect(screen.getByText('RLHF Survey')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId('inline-viewer')).toHaveTextContent(
        'rlhf-survey.pdf'
      )
    );
    expect(mockGetDocument).toHaveBeenCalledWith('doc-1');
  });

  it('shows an error state when the document fetch fails', async () => {
    mockGetDocument.mockRejectedValue(new Error('403'));
    render(<ArtifactPanel artifact={docArtifact} />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(
      screen.getByText("Couldn't load this document")
    ).toBeInTheDocument();
  });

  it('links to the full document page', () => {
    render(<ArtifactPanel artifact={docArtifact} />);
    expect(screen.getByRole('link', { name: 'Open full page' })).toHaveAttribute(
      'href',
      '/documents/doc-1'
    );
  });

  it('close button hides the panel but keeps the artifact', async () => {
    const { user } = render(<ArtifactPanel artifact={docArtifact} />);
    await user.click(
      screen.getByRole('button', { name: 'Close artifact panel' })
    );
    const s = useArtifactPanelStore.getState();
    expect(s.isOpen).toBe(false);
    expect(s.artifact).toEqual(docArtifact);
  });

  it('pin button toggles the pinned flag with aria-pressed', async () => {
    const { user } = render(<ArtifactPanel artifact={docArtifact} />);
    const pin = screen.getByRole('button', { name: 'Pin this artifact' });
    expect(pin).toHaveAttribute('aria-pressed', 'false');
    await user.click(pin);
    expect(useArtifactPanelStore.getState().pinned).toBe(true);
  });

  it('rail toggle renders only when a handler is provided and fires it', async () => {
    const onToggleRail = vi.fn();
    const { user, rerender } = render(
      <ArtifactPanel artifact={docArtifact} onToggleRail={onToggleRail} />
    );
    await user.click(
      screen.getByRole('button', { name: 'Show context rail' })
    );
    expect(onToggleRail).toHaveBeenCalledTimes(1);

    rerender(<ArtifactPanel artifact={docArtifact} />);
    expect(
      screen.queryByRole('button', { name: /context rail/i })
    ).not.toBeInTheDocument();
  });

  it('renders citations and re-focuses the panel on a cited document open', async () => {
    const citations = [
      {
        title: 'Paper A',
        documentId: 'doc-9',
        score: 0.9,
        content: 'passage',
      },
    ] as never[];
    const artifact: Artifact = {
      kind: 'citations',
      citations,
      activeCitationId: 'doc-9',
      traceId: 'trace-1',
    };
    act(() => {
      useArtifactPanelStore.setState({ artifact, isOpen: true });
    });
    const { user } = render(<ArtifactPanel artifact={artifact} />);

    expect(screen.getByText('Paper A')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /open document/i }));

    expect(useArtifactPanelStore.getState().artifact).toEqual({
      kind: 'document',
      id: 'doc-9',
      title: 'Paper A',
    });
  });

  it('cite dispatches the append-mode populate-chat-input bridge event', async () => {
    const citations = [
      { title: 'Paper A', documentId: 'doc-9', score: 0.9, content: 'p' },
    ] as never[];
    const artifact: Artifact = { kind: 'citations', citations };
    const listener = vi.fn();
    window.addEventListener('populate-chat-input', listener);
    try {
      const { user } = render(<ArtifactPanel artifact={artifact} />);
      await user.click(screen.getByRole('button', { name: 'Cite' }));
      expect(listener).toHaveBeenCalledTimes(1);
      expect((listener.mock.calls[0][0] as CustomEvent).detail).toEqual({
        text: '"Paper A"',
        mode: 'append',
      });
    } finally {
      window.removeEventListener('populate-chat-input', listener);
    }
  });

  it('renders an external artifact as an outbound link card', () => {
    const external: Artifact = {
      kind: 'external',
      id: '2310.08419',
      title: 'PAIR: Jailbreaking in Twenty Queries',
    };
    render(<ArtifactPanel artifact={external} />);

    // Title renders in both the header and the link card.
    expect(
      screen.getAllByText('PAIR: Jailbreaking in Twenty Queries').length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('link', { name: /open source/i })).toHaveAttribute(
      'href',
      'https://arxiv.org/abs/2310.08419'
    );
    expect(mockGetDocument).not.toHaveBeenCalled();
  });
});
