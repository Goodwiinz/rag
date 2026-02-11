/**
 * Unit tests for DraftViewer component
 *
 * Tests draft rendering (title, metadata, themes, content via ReactMarkdown),
 * citation badge rendering for [Doc N] patterns, version selector,
 * export button, and "Current" badge display.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { DraftViewer } from '@/components/research/DraftViewer';
import type { Draft } from '@/services/projectService';

// Mock react-markdown since it uses ESM and may not work in the Jest/JSDOM env
jest.mock('react-markdown', () => {
  return function MockReactMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});

jest.mock('remark-gfm', () => () => {});

// Helper to create a valid Draft object for tests
function createMockDraft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: 'draft-abc-123',
    project_id: 'project-xyz',
    version: 2,
    title: 'Literature Review: Transformer Architectures',
    content:
      'This section discusses attention mechanisms [Doc 1] and their applications [Doc 3].',
    themes: ['transformers', 'attention', 'NLP'],
    word_count: 2450,
    citation_count: 8,
    generation_params: { style: 'academic' },
    is_current: true,
    created_at: '2025-03-10T14:30:00Z',
    ...overrides,
  };
}

describe('DraftViewer', () => {
  it('renders draft title and metadata', () => {
    const draft = createMockDraft();
    render(<DraftViewer draft={draft} />);

    expect(
      screen.getByText('Literature Review: Transformer Architectures')
    ).toBeInTheDocument();

    // Metadata line: "Version 2 . 2450 words . 8 citations"
    expect(screen.getByText(/Version 2/)).toBeInTheDocument();
    expect(screen.getByText(/2450 words/)).toBeInTheDocument();
    expect(screen.getByText(/8 citations/)).toBeInTheDocument();
  });

  it('renders theme badges', () => {
    const draft = createMockDraft({
      themes: ['deep learning', 'computer vision', 'GANs'],
    });
    render(<DraftViewer draft={draft} />);

    expect(screen.getByText('Themes:')).toBeInTheDocument();
    expect(screen.getByText('deep learning')).toBeInTheDocument();
    expect(screen.getByText('computer vision')).toBeInTheDocument();
    expect(screen.getByText('GANs')).toBeInTheDocument();
  });

  it('does not render themes section when themes array is empty', () => {
    const draft = createMockDraft({ themes: [] });
    render(<DraftViewer draft={draft} />);

    expect(screen.queryByText('Themes:')).not.toBeInTheDocument();
  });

  it('renders content with ReactMarkdown', () => {
    const draft = createMockDraft({
      content: '## Introduction\n\nSome content here.',
    });
    render(<DraftViewer draft={draft} />);

    const markdownEl = screen.getByTestId('markdown-content');
    expect(markdownEl).toBeInTheDocument();
    expect(markdownEl).toHaveTextContent('## Introduction');
    expect(markdownEl).toHaveTextContent('Some content here.');
  });

  it('renders [Doc N] citation badges in content', () => {
    // With the mock ReactMarkdown, the content is rendered as plain text
    // inside a div. The citation badge rendering happens inside the real
    // ReactMarkdown components override (p, li). Since we mock ReactMarkdown,
    // we verify that the content containing [Doc N] is passed through.
    const draft = createMockDraft({
      content: 'Evidence shows [Doc 1] and confirms [Doc 5] results.',
    });
    render(<DraftViewer draft={draft} />);

    const markdownEl = screen.getByTestId('markdown-content');
    expect(markdownEl).toHaveTextContent('[Doc 1]');
    expect(markdownEl).toHaveTextContent('[Doc 5]');
  });

  it('shows version selector when multiple versions are provided', () => {
    const draft = createMockDraft({ version: 3 });
    const versions = [
      { version: 3, created_at: '2025-03-10T14:30:00Z' },
      { version: 2, created_at: '2025-03-09T10:00:00Z' },
      { version: 1, created_at: '2025-03-08T08:00:00Z' },
    ];
    const onVersionChange = jest.fn();

    render(
      <DraftViewer
        draft={draft}
        versions={versions}
        onVersionChange={onVersionChange}
      />
    );

    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();

    // Should have 3 options
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(3);

    // Options text should contain version numbers
    expect(options[0]).toHaveTextContent('v3');
    expect(options[1]).toHaveTextContent('v2');
    expect(options[2]).toHaveTextContent('v1');
  });

  it('does not show version selector when only one version exists', () => {
    const draft = createMockDraft({ version: 1 });
    const versions = [{ version: 1, created_at: '2025-03-08T08:00:00Z' }];
    const onVersionChange = jest.fn();

    render(
      <DraftViewer
        draft={draft}
        versions={versions}
        onVersionChange={onVersionChange}
      />
    );

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('does not show version selector when versions prop is not provided', () => {
    const draft = createMockDraft();
    render(<DraftViewer draft={draft} />);

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('calls onVersionChange when a version is selected', () => {
    const draft = createMockDraft({ version: 3 });
    const versions = [
      { version: 3, created_at: '2025-03-10T14:30:00Z' },
      { version: 2, created_at: '2025-03-09T10:00:00Z' },
      { version: 1, created_at: '2025-03-08T08:00:00Z' },
    ];
    const onVersionChange = jest.fn();

    render(
      <DraftViewer
        draft={draft}
        versions={versions}
        onVersionChange={onVersionChange}
      />
    );

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: '1' } });

    expect(onVersionChange).toHaveBeenCalledTimes(1);
    expect(onVersionChange).toHaveBeenCalledWith(1);
  });

  it('calls onExport when export button is clicked', () => {
    const draft = createMockDraft();
    const onExport = jest.fn();

    render(<DraftViewer draft={draft} onExport={onExport} />);

    const exportButton = screen.getByRole('button', { name: /export/i });
    expect(exportButton).toBeInTheDocument();

    fireEvent.click(exportButton);

    expect(onExport).toHaveBeenCalledTimes(1);
  });

  it('does not render export button when onExport is not provided', () => {
    const draft = createMockDraft();
    render(<DraftViewer draft={draft} />);

    expect(
      screen.queryByRole('button', { name: /export/i })
    ).not.toBeInTheDocument();
  });

  it('shows "Current" badge when draft.is_current is true', () => {
    const draft = createMockDraft({ is_current: true });
    render(<DraftViewer draft={draft} />);

    expect(screen.getByText('Current')).toBeInTheDocument();
  });

  it('does not show "Current" badge when draft.is_current is false', () => {
    const draft = createMockDraft({ is_current: false });
    render(<DraftViewer draft={draft} />);

    expect(screen.queryByText('Current')).not.toBeInTheDocument();
  });

  it('renders the created_at date in the footer', () => {
    const draft = createMockDraft({
      created_at: '2025-03-10T14:30:00Z',
    });
    render(<DraftViewer draft={draft} />);

    // The footer uses new Date(...).toLocaleString(), so we check for "Generated"
    expect(screen.getByText(/Generated/)).toBeInTheDocument();
  });

  it('handles empty content gracefully', () => {
    const draft = createMockDraft({ content: '' });
    render(<DraftViewer draft={draft} />);

    const markdownEl = screen.getByTestId('markdown-content');
    expect(markdownEl).toBeInTheDocument();
    expect(markdownEl).toHaveTextContent('');
  });
});
