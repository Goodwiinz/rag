import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';

import { FormField } from '../form-field';

afterEach(() => {
  cleanup();
});

describe('FormField', () => {
  it('shows the green valid icon when value is numeric 0 after blur', () => {
    const { container } = render(
      <FormField
        label="Count"
        type="number"
        value={0}
        onChange={vi.fn()}
        showValidIcon={true}
      />
    );

    const input = screen.getByLabelText('Count');
    fireEvent.blur(input);

    const validIcon = container.querySelector('svg.text-green-500');
    expect(validIcon).not.toBeNull();
  });

  it('does NOT show the valid icon when value is an empty string', () => {
    const { container } = render(
      <FormField
        label="Name"
        type="text"
        value=""
        onChange={vi.fn()}
        showValidIcon={true}
      />
    );

    const input = screen.getByLabelText('Name');
    fireEvent.blur(input);

    const validIcon = container.querySelector('svg.text-green-500');
    expect(validIcon).toBeNull();
  });

  it('shows the valid icon for a non-empty string value after blur', () => {
    const { container } = render(
      <FormField
        label="Name"
        type="text"
        value="Abdel"
        onChange={vi.fn()}
        showValidIcon={true}
      />
    );

    const input = screen.getByLabelText('Name');
    fireEvent.blur(input);

    const validIcon = container.querySelector('svg.text-green-500');
    expect(validIcon).not.toBeNull();
  });
});
