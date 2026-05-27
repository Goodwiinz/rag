import * as React from 'react';

import { cn } from 'src/lib/utils';

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        // NOUS migration (2026-04-19):
        //   - focus-visible now shifts border-color to Sol and softens the ring
        //     to the handoff's 30% Sol glow (was ring-offset + full --ring).
        //   - Added transition-colors so the focus animation reads.
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-base transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-[var(--nous-sol)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/30 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };
