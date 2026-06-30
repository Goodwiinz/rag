'use client';

import React from 'react';

import Plan from '@/components/ui/agent-plan';

export function Demo(): React.JSX.Element {
  return (
    <div className="flex flex-col p-4 w-full h-full">
      <Plan />
    </div>
  );
}
