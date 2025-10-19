import React from 'react';
import { cn } from '@/lib/utils';

interface TwoPanelLayoutProps {
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
  leftPanelWidth?: string;
  rightPanelWidth?: string;
  className?: string;
  leftPanelClassName?: string;
  rightPanelClassName?: string;
}

/**
 * Two Panel Layout Component
 *
 * Provides a responsive two-column layout for the main dashboard interface.
 * On mobile, panels stack vertically.
 */
export const TwoPanelLayout: React.FC<TwoPanelLayoutProps> = ({
  leftPanel,
  rightPanel,
  leftPanelWidth = 'w-1/3',
  rightPanelWidth = 'w-2/3',
  className,
  leftPanelClassName,
  rightPanelClassName,
}) => {
  return (
    <div className={cn('flex flex-col lg:flex-row h-full gap-6 p-6', className)}>
      {/* Left Panel */}
      <div className={cn(
        'flex flex-col space-y-6 min-h-0',
        leftPanelWidth,
        leftPanelClassName
      )}>
        {leftPanel}
      </div>

      {/* Right Panel */}
      <div className={cn(
        'flex flex-col min-h-0',
        rightPanelWidth,
        rightPanelClassName
      )}>
        {rightPanel}
      </div>
    </div>
  );
};