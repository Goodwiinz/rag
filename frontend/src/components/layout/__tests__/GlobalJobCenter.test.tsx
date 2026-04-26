import { GlobalJobCenter } from '@/components/layout/GlobalJobCenter';
import { entityService } from '@/services/entityService';
import { render, waitFor } from '@testing-library/react';

let mockAuthStoreState = {
  isAuthenticated: true,
  isLoading: false,
};

jest.mock('@/services/entityService', () => ({
  entityService: {
    listProcessingJobs: jest.fn(),
  },
}));

jest.mock('@/store/authStore', () => ({
  useAuthStore: (selector: (state: typeof mockAuthStoreState) => unknown) =>
    selector(mockAuthStoreState),
}));

const mockListProcessingJobs = entityService
  .listProcessingJobs as jest.MockedFunction<typeof entityService.listProcessingJobs>;

describe('GlobalJobCenter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuthStoreState = {
      isAuthenticated: true,
      isLoading: false,
    };
    mockListProcessingJobs.mockResolvedValue({ jobs: [] } as never);
  });

  it('does not poll background jobs for signed-out users', async () => {
    mockAuthStoreState = {
      isAuthenticated: false,
      isLoading: false,
    };

    render(<GlobalJobCenter />);

    await waitFor(() => {
      expect(mockListProcessingJobs).not.toHaveBeenCalled();
    });
  });

  it('loads background jobs for signed-in users', async () => {
    render(<GlobalJobCenter />);

    await waitFor(() => {
      expect(mockListProcessingJobs).toHaveBeenCalledWith({
        limit: 15,
        offset: 0,
      });
    });
  });
});
