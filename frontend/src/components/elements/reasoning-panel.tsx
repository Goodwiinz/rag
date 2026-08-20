'use client';

import type { ComponentProps } from 'react';
import { ChevronDownIcon } from 'lucide-react';

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import { mono, ShimmerLabel, SwapLabel } from './surfaces';

export interface ReasoningStep {
  title: string;
  body: string;
}

export interface ReasoningPanelProps extends Omit<
  ComponentProps<typeof Collapsible>,
  'children'
> {
  steps: readonly ReasoningStep[];
  visibleSteps: number;
  streaming: boolean;
  restingLabel: string;
  elapsed?: string;
}

export function ReasoningPanel({
  steps,
  visibleSteps,
  streaming,
  restingLabel,
  elapsed,
  className,
  ...props
}: ReasoningPanelProps): React.JSX.Element {
  return (
    <Collapsible
      data-slot="reasoning-panel"
      className={cn('w-full max-w-sm', className)}
      {...props}
    >
      <CollapsibleTrigger className="group/trigger flex items-center gap-1.5 py-1 text-[13.5px] text-(--nous-fg-2) outline-none transition-[color,scale] hover:text-(--nous-fg-1) active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-(--nous-sol)">
        <SwapLabel active={streaming ? 0 : 1} className="text-start">
          <>
            <ShimmerLabel
              active={streaming}
              className="relative inline-block leading-none"
            >
              Thinking
            </ShimmerLabel>
            {elapsed !== undefined && (
              <span className={cn(mono, 'tabular-nums text-(--nous-fg-3)')}>
                {elapsed}
              </span>
            )}
          </>
          <>{restingLabel}</>
        </SwapLabel>
        <ChevronDownIcon className="size-3.5 shrink-0 opacity-60 transition-transform duration-200 ease-[cubic-bezier(0.32,0.72,0,1)] group-data-[state=open]/trigger:rotate-180 motion-reduce:transition-none" />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-top-1 data-[state=closed]:animate-out data-[state=closed]:fade-out">
        <ol className="flex flex-col gap-4 pb-1 pt-3">
          {steps.slice(0, visibleSteps).map((step, index, shown) => {
            const active = streaming && index === shown.length - 1;
            return (
              <li
                key={`${index}-${step.title}`}
                className="fade-in slide-in-from-bottom-1 animate-in flex gap-3 fill-mode-both duration-300"
              >
                <span
                  aria-hidden
                  className={cn(
                    'mt-[7px] size-[5px] shrink-0 rounded-full transition-colors duration-300',
                    active
                      ? 'animate-pulse bg-(--nous-sol)'
                      : 'bg-(--nous-border-2)'
                  )}
                />
                <span className="flex min-w-0 flex-1 flex-col">
                  <p className="text-[13.5px] font-medium text-(--nous-fg-1)">
                    {step.title}
                  </p>
                  <p className="mt-0.5 break-words text-[13px] leading-relaxed text-(--nous-fg-2)">
                    {step.body}
                  </p>
                </span>
              </li>
            );
          })}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  );
}
