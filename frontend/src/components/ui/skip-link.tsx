import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import React from 'react';

export const SkipLink = () => {
  return (
    <Button
      asChild
      className={cn(
        'fixed left-4 top-4 z-[100] -translate-y-[150%] transition-transform focus:translate-y-0',
        'bg-primary text-primary-foreground shadow-lg'
      )}
    >
      <a href="#main-content">Skip to content</a>
    </Button>
  );
};
