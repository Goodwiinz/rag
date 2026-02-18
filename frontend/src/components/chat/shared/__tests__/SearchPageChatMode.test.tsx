import { render, screen } from '@testing-library/react';
import SearchPage from '../../../../../app/(dashboard)/search/page';

jest.mock('@/lib/analytics', () => ({
  getAnalytics: () => ({
    trackPageView: jest.fn(),
    trackSearch: jest.fn(),
  }),
}));

jest.mock('@/components/search/ResultsPanel', () => ({
  ResultsPanel: () => <div>Results Panel</div>,
}));

jest.mock('@/components/chat/shared/TerminalChatBubble', () => ({
  TerminalChatBubble: () => <div>Bubble</div>,
}));

jest.mock('@/components/chat/CitationPanel', () => ({
  CitationPanel: () => <div>Citation Panel</div>,
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

describe('SearchPage chat mode', () => {
  it('renders terminal chat composer placeholder', async () => {
    render(<SearchPage />);

    expect(
      await screen.findByPlaceholderText(/inject query into neural stream/i)
    ).toBeInTheDocument();
  });
});
