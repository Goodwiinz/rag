import { render } from '@testing-library/react';
import type { ReactElement } from 'react';

export function renderWithChatRuntime(ui: ReactElement) {
  return render(ui);
}
