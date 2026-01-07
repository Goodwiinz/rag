'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/contexts/sidebar-context';
import { useIsMobile } from '@/hooks/use-mobile';

interface EnhancedSidebarProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: 'left' | 'right';
  variant?: 'sidebar' | 'floating' | 'inset';
  collapsible?: 'offcanvas' | 'icon' | 'none';
}

const sidebarVariants = {
  expanded: {
    width: 280,
    transition: {
      duration: 0.3,
      ease: [0.4, 0, 0.2, 1] as const,
    },
  },
  mini: {
    width: 64,
    transition: {
      duration: 0.3,
      ease: [0.4, 0, 0.2, 1] as const,
    },
  },
  collapsed: {
    width: 0,
    transition: {
      duration: 0.3,
      ease: [0.4, 0, 0.2, 1] as const,
    },
  },
};

const mobileVariants = {
  open: {
    x: 0,
    opacity: 1,
    transition: {
      duration: 0.3,
      ease: [0.4, 0, 0.2, 1] as const,
    },
  },
  closed: {
    x: -280,
    opacity: 0,
    transition: {
      duration: 0.3,
      ease: [0.4, 0, 0.2, 1] as const,
    },
  },
};

export const EnhancedSidebar = React.forwardRef<HTMLDivElement, EnhancedSidebarProps>(
  (
    {
      side = 'left',
      variant = 'sidebar',
      collapsible = 'offcanvas',
      className,
      children,
      ...props
    },
    ref
  ) => {
    const {
      state,
      isMobile,
      mobileOpen,
      isOpen,
      isTransitioning,
      toggleSidebar,
    } = useSidebar();
    const isMobileDevice = useIsMobile();

    // Handle backdrop click for mobile
    const handleBackdropClick = (e: React.MouseEvent) => {
      if (e.target === e.currentTarget && isMobile) {
        toggleSidebar();
      }
    };

    // Mobile sidebar with overlay
    if (isMobileDevice) {
      return (
        <AnimatePresence>
          {mobileOpen && (
            <>
              {/* Backdrop */}
              <motion.div
                className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm md:hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                onClick={handleBackdropClick}
              />

              {/* Mobile Sidebar */}
              <motion.div
                ref={ref}
                className={cn(
                  'fixed top-0 z-50 h-screen bg-background md:hidden',
                  'w-64 max-w-[80vw]',
                  'shadow-2xl border-r border-border',
                  'overflow-hidden',
                  side === 'right' ? 'right-0' : 'left-0',
                  className
                )}
                variants={mobileVariants}
                initial="closed"
                animate="open"
                exit="closed"
                {...props}
              >
                <div className="h-full overflow-y-auto">
                  {children}
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      );
    }

    // Desktop sidebar
    if (!isMobileDevice) {
      return (
        <motion.div
          ref={ref}
          className={cn(
            'relative h-screen bg-background border-r border-border overflow-hidden',
            'flex flex-col',
            variant === 'floating' && 'm-2 rounded-lg shadow-lg border',
            variant === 'inset' && 'm-4 rounded-lg shadow-lg border',
            'group/sidebar',
            isTransitioning && 'pointer-events-none',
            className
          )}
          variants={sidebarVariants}
          animate={state}
          initial={false}
          {...props}
        >
          {children}

          {/* Hover zone for collapsed sidebar */}
          {state === 'collapsed' && collapsible === 'offcanvas' && (
            <motion.div
              className="absolute top-0 right-0 h-full w-4 z-10"
              onHoverStart={() => {
                if (state === 'collapsed') {
                  // Optional: Expand on hover
                  // expandSidebar();
                }
              }}
            />
          )}

          {/* Resize handle */}
          <motion.div
            className={cn(
              'absolute top-0 right-0 h-full w-1 cursor-ew-resize',
              'hover:bg-primary/20 transition-colors opacity-0 hover:opacity-100',
              'group-hover/sidebar:opacity-100'
            )}
            drag="x"
            dragConstraints={{ left: 64, right: 320 }}
            dragElastic={0.1}
            onDragEnd={(event, info) => {
              const width = info.offset.x + 280;
              if (width < 100) {
                // Collapse
                toggleSidebar();
              } else if (width < 200) {
                // Mini mode
                // setMiniMode();
              }
              // Reset position
              event.currentTarget.style.transform = '';
            }}
          />
        </motion.div>
      );
    }

    return null;
  }
);

EnhancedSidebar.displayName = 'EnhancedSidebar';

// Enhanced content wrapper with animation support
export const EnhancedSidebarContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { state, shouldShowTooltips } = useSidebar();

  return (
    <motion.div
      ref={ref}
      className={cn(
        'flex-1 overflow-hidden flex flex-col',
        'transition-opacity duration-300',
        state === 'collapsed' && 'opacity-0',
        className
      )}
      initial={false}
      animate={{
        opacity: state === 'collapsed' ? 0 : 1,
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
});

EnhancedSidebarContent.displayName = 'EnhancedSidebarContent';

// Enhanced header with logo animation
export const EnhancedSidebarHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { state } = useSidebar();

  return (
    <motion.div
      ref={ref}
      className={cn(
        'p-4 border-b border-border',
        'flex items-center gap-3',
        className
      )}
      layout
      {...props}
    >
      {children}
    </motion.div>
  );
});

EnhancedSidebarHeader.displayName = 'EnhancedSidebarHeader';

// Enhanced footer with user menu
export const EnhancedSidebarFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { state } = useSidebar();

  return (
    <motion.div
      ref={ref}
      className={cn(
        'p-4 border-t border-border mt-auto',
        state === 'mini' ? 'justify-center' : '',
        className
      )}
      layout
      {...props}
    >
      {children}
    </motion.div>
  );
});

EnhancedSidebarFooter.displayName = 'EnhancedSidebarFooter';

// Enhanced menu with item animations
export const EnhancedSidebarMenu = React.forwardRef<
  HTMLUListElement,
  React.HTMLAttributes<HTMLUListElement>
>(({ className, children, ...props }, ref) => {
  return (
    <ul
      ref={ref}
      className={cn(
        'flex flex-col gap-1 p-2',
        className
      )}
      {...props}
    >
      {React.Children.map(children, (child, index) => (
        <motion.li
          key={index}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{
            duration: 0.2,
            delay: index * 0.05,
            ease: [0.4, 0, 0.2, 1],
          }}
        >
          {child}
        </motion.li>
      ))}
    </ul>
  );
});

EnhancedSidebarMenu.displayName = 'EnhancedSidebarMenu';