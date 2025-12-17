'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { useSidebar } from '@/contexts/sidebar-context';
import type { LucideIcon } from 'lucide-react';

interface EnhancedSidebarMenuItemProps {
  title: string;
  href: string;
  icon: LucideIcon;
  badge?: string | number;
  isSubItem?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}

const itemVariants = {
  inactive: {
    scale: 1,
    x: 0,
  },
  active: {
    scale: 1.02,
    x: 4,
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 0.2, 1],
    },
  },
  hover: {
    scale: 1.02,
    x: 4,
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 0.2, 1],
    },
  },
  tap: {
    scale: 0.98,
    transition: {
      duration: 0.1,
    },
  },
};

const textVariants = {
  expanded: {
    opacity: 1,
    x: 0,
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 0.2, 1],
    },
  },
  mini: {
    opacity: 0,
    x: -10,
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 0.2, 1],
    },
  },
};

export const EnhancedSidebarMenuItem = React.forwardRef<
  HTMLAnchorElement,
  EnhancedSidebarMenuItemProps
>(
  (
    {
      title,
      href,
      icon: Icon,
      badge,
      isSubItem = false,
      disabled = false,
      onClick,
    },
    ref
  ) => {
    const pathname = usePathname();
    const { state, shouldShowTooltips } = useSidebar();

    const isActive = pathname === href || pathname?.startsWith(href + '/');
    const isMini = state === 'mini';

    const content = (
      <motion.a
        ref={ref}
        href={href}
        onClick={onClick}
        className={cn(
          'relative flex items-center gap-3 px-3 py-2 rounded-md',
          'text-sm font-medium transition-colors',
          'group cursor-pointer',
          isActive
            ? 'bg-primary text-primary-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-accent',
          disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
          isSubItem && 'ml-4 text-xs',
          isMini && 'justify-center px-2'
        )}
        variants={itemVariants}
        initial="inactive"
        whileHover="hover"
        whileTap="tap"
        animate={isActive ? 'active' : 'inactive'}
      >
        {/* Icon with subtle animation */}
        <motion.div
          className={cn(
            'flex-shrink-0',
            isMini ? 'w-5 h-5' : 'w-4 h-4'
          )}
          animate={{
            rotate: isActive ? [0, -5, 5, 0] : 0,
          }}
          transition={{
            duration: 0.5,
            ease: [0.4, 0, 0.2, 1],
            repeat: isActive ? Infinity : 0,
            repeatDelay: 3,
          }}
        >
          <Icon className="w-full h-full" />
        </motion.div>

        {/* Text with slide animation */}
        <AnimatePresence mode="wait">
          {!isMini && (
            <motion.span
              variants={textVariants}
              initial="mini"
              animate="expanded"
              exit="mini"
              className="flex-1 truncate"
            >
              {title}
            </motion.span>
          )}
        </AnimatePresence>

        {/* Badge */}
        {badge && !isMini && (
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{
              duration: 0.2,
              delay: 0.1,
            }}
          >
            <Badge
              variant={isActive ? 'secondary' : 'default'}
              className="text-xs px-2 py-0.5"
            >
              {badge}
            </Badge>
          </motion.div>
        )}

        {/* Active indicator */}
        {isActive && (
          <motion.div
            className="absolute left-0 top-0 bottom-0 w-1 bg-primary rounded-r-full"
            layoutId="activeIndicator"
            initial={{ opacity: 0, scaleY: 0 }}
            animate={{ opacity: 1, scaleY: 1 }}
            exit={{ opacity: 0, scaleY: 0 }}
            transition={{
              duration: 0.2,
              ease: [0.4, 0, 0.2, 1],
            }}
          />
        )}

        {/* Hover effect */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent rounded-md"
          initial={{ opacity: 0, x: -100 }}
          whileHover={{ opacity: 1, x: 100 }}
          transition={{
            duration: 0.6,
            ease: [0.4, 0, 0.2, 1],
          }}
        />
      </motion.a>
    );

    // Show tooltip in mini mode
    if (shouldShowTooltips) {
      return (
        <Tooltip delayDuration={300}>
          <TooltipTrigger asChild>{content}</TooltipTrigger>
          <TooltipContent side="right" align="center" className="font-medium">
            {title}
            {badge && (
              <Badge variant="secondary" className="ml-2">
                {badge}
              </Badge>
            )}
          </TooltipContent>
        </Tooltip>
      );
    }

    return content;
  }
);

EnhancedSidebarMenuItem.displayName = 'EnhancedSidebarMenuItem';

// Group label for mini mode
export const EnhancedSidebarGroupLabel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { state } = useSidebar();
  const isMini = state === 'mini';

  return (
    <motion.div
      ref={ref}
      className={cn(
        'px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider',
        isMini && 'sr-only',
        className
      )}
      initial={{ opacity: 0, y: -10 }}
      animate={{
        opacity: isMini ? 0 : 1,
        y: isMini ? -10 : 0,
      }}
      transition={{
        duration: 0.2,
        ease: [0.4, 0, 0.2, 1],
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
});

EnhancedSidebarGroupLabel.displayName = 'EnhancedSidebarGroupLabel';

// Separator with animation
export const EnhancedSidebarSeparator = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { state } = useSidebar();
  const isMini = state === 'mini';

  return (
    <motion.div
      ref={ref}
      className={cn(
        'h-px bg-border mx-3',
        isMini && 'mx-2 w-8',
        className
      )}
      initial={{ opacity: 0, scaleX: 0 }}
      animate={{
        opacity: isMini ? 0 : 1,
        scaleX: isMini ? 0 : 1,
      }}
      transition={{
        duration: 0.2,
        ease: [0.4, 0, 0.2, 1],
      }}
      {...props}
    />
  );
});

EnhancedSidebarSeparator.displayName = 'EnhancedSidebarSeparator';