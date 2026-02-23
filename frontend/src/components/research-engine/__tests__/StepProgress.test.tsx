import { fireEvent, render, screen } from '@testing-library/react';
import { StepProgress, type StepData } from '../StepProgress';

describe('StepProgress', () => {
  it('renders structured output objects without crashing', () => {
    const step: StepData = {
      stepIndex: 0,
      stepName: 'Extract Evidence',
      stepType: 'extract',
      status: 'complete',
      tokenCount: 50,
      qualityMarks: [],
      output: {
        content: 'Structured summary',
        sources: ['paper-a', 'paper-b'],
      },
    };

    render(<StepProgress step={step} />);

    fireEvent.click(screen.getByRole('button', { name: /extract evidence/i }));
    expect(screen.getByText(/structured summary/i)).toBeInTheDocument();
  });
});
