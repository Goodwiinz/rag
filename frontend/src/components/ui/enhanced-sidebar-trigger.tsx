'use client';

import * as React from 'react';
import { motion } from 'framer-motion';
import { PanelLeft, PanelLeftOpen, PanelRight, PanelRightOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/contexts/sidebar-context';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface EnhancedSidebarTriggerProps
  extends React.ComponentProps<typeof Button> {
  showLabel?: boolean;
  side?: 'left' | 'right';
}

const triggerVariants = {
  expanded: {
    rotate: 0,
    scale: 1,
  },
  collapsed: {
    rotate: 0,
    scale: 1,
  },
  mini: {
    rotate: 0,
    scale: 1,
  },
  hover: {
    scale: 1.05,
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 0.2, 1] as const,
    },
  },
  tap: {
    scale: 0.95,
    transition: {
      duration: 0.1,
    },
  },
};

export const EnhancedSidebarTrigger = React.forwardRef<
  HTMLButtonElement,
  EnhancedSidebarTriggerProps
>(({ className, showLabel = false, side = 'left', ...props }, ref) => {
  const { state, toggleSidebar, isOpen } = useSidebar();

  const getIcon = () => {
    if (side === 'right') {
      switch (state) {
        case 'expanded':
          return PanelRightOpen;
        case 'mini':
          return PanelRight;
        default:
          return PanelLeft;
      }
    }
    switch (state) {
      case 'expanded':
        return PanelLeftOpen;
      case 'mini':
        return PanelLeft;
      default:
        return PanelLeft;
    }
  };

  const Icon = getIcon();

  const buttonContent = (
    <motion.div
      variants={triggerVariants}
      initial={false}
      animate={state}
      whileHover="hover"
      whileTap="tap"
      className="flex items-center gap-2"
    >
      <motion.div
        animate={{
          rotate: state === 'mini' ? 0 : isOpen() ? 180 : 0,
        }}
        transition={{
          duration: 0.3,
          ease: [0.4, 0, 0.2, 1] as const,
        }}
      >
        <Icon className="h-4 w-4" />
      </motion.div>

      {showLabel && (
        <motion.span
          initial={{ opacity: 0, width: 0 }}
          animate={{
            opacity: state === 'expanded' ? 1 : 0,
            width: state === 'expanded' ? 'auto' : 0,
          }}
          transition={{
            duration: 0.2,
            ease: [0.4, 0, 0.2, 1],
          }}
          className="overflow-hidden whitespace-nowrap"
        >
          {state === 'collapsed' ? 'Open' : state === 'mini' ? 'Expand' : 'Collapse'} Sidebar
        </motion.span>
      )}
    </motion.div>
  );

  const trigger = (
    <Button
      ref={ref}
      variant="ghost"
      size="icon"
      className={cn(
        'h-9 w-9 relative',
        'hover:bg-muted transition-colors',
        'data-[state=open]:bg-accent',
        className
      )}
      onClick={toggleSidebar}
      aria-label="Toggle sidebar"
      {...props}
    >
      {buttonContent}

      {/* Keyboard shortcut hint */}
      <kbd className="absolute -bottom-1 -right-1 hidden h-5 min-w-5 items-center justify-center rounded bg-secondary px-1 text-[10px] font-medium text-secondary-foreground opacity-0 transition-opacity group-hover:flex group-hover:opacity-100">
        ⌘B
      </kbd>
    </Button>
  );

  // Show tooltip in collapsed or mini mode
  if (state === 'collapsed' || state === 'mini') {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{trigger}</TooltipTrigger>
        <TooltipContent side="bottom" align="center">
          <p>Toggle Sidebar (⌘B)</p>
        </TooltipContent>
      </Tooltip>
    );
  }

  return trigger;
});

EnhancedSidebarTrigger.displayName = 'EnhancedSidebarTrigger';

// Mobile trigger with hamburger animation
export const MobileSidebarTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof Button>
>(({ className, ...props }, ref) => {
  const { mobileOpen, toggleSidebar } = useSidebar();

  const topLineVariants = {
    open: {
      rotate: 45,
      y: 6,
      transition: {
        duration: 0.2,
        ease: [0.4, 0, 0.2, 1] as const,
      },
    },
    closed: {
      rotate: 0,
      y: 0,
      transition: {
        duration: 0.2,
        ease: [0.4, 0, 0.2, 1] as const,
      },
    },
  };

  const middleLineVariants = {
    open: {
      opacity: 0,
      transition: {
        duration: 0.1,
      },
    },
    closed: {
      opacity: 1,
      transition: {
        duration: 0.1,
        delay: 0.1,
      },
    },
  };

  const bottomLineVariants = {
    open: {
      rotate: -45,
      y: -6,
      transition: {
        duration: 0.2,
        ease: [0.4, 0, 0.2, 1] as const,
      },
    },
    closed: {
      rotate: 0,
      y: 0,
      transition: {
        duration: 0.2,
        ease: [0.4, 0, 0.2, 1] as const,
      },
    },
  };

  return (
    <Button
      ref={ref}
      variant="ghost"
      size="icon"
      className={cn('md:hidden h-9 w-9', className)}
      onClick={toggleSidebar}
      aria-label="Toggle mobile sidebar"
      {...props}
    >
      <motion.svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        className="overflow-visible"
      >
        <motion.line
          x1="0"
          y1="4"
          x2="20"
          y2="4"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          variants={topLineVariants}
          animate={mobileOpen ? 'open' : 'closed'}
        />
        <motion.line
          x1="0"
          y1="10"
          x2="20"
          y2="10"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          variants={middleLineVariants}
          animate={mobileOpen ? 'open' : 'closed'}
        />
        <motion.line
          x1="0"
          y1="16"
          x2="20"
          y2="16"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          variants={bottomLineVariants}
          animate={mobileOpen ? 'open' : 'closed'}
        />
      </motion.svg>
    </Button>
  );
});

MobileSidebarTrigger.displayName = 'MobileSidebarTrigger';