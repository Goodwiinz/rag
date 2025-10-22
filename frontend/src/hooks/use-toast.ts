import { toast as hotToast } from 'react-hot-toast';

export function useToast() {
  return {
    toast: (options: { title?: string; description?: string; variant?: string }) => {
      if (options.variant === 'destructive') {
        hotToast.error(options.description || options.title || 'Error');
      } else {
        hotToast.success(options.description || options.title || 'Success');
      }
    },
  };
}
