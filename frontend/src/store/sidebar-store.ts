'use client';

import React from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export type SidebarState = 'expanded' | 'collapsed' | 'mini';
export type SidebarPosition = 'left' | 'right';

interface SidebarStore {
  // State
  state: SidebarState;
  position: SidebarPosition;
  isMobile: boolean;
  isTablet: boolean;

  // Mobile-specific state
  mobileOpen: boolean;

  // Animation states
  isAnimating: boolean;

  // Actions
  setState: (state: SidebarState) => void;
  toggleSidebar: () => void;
  expandSidebar: () => void;
  collapseSidebar: () => void;
  setMiniMode: () => void;

  // Mobile actions
  setMobileOpen: (open: boolean) => void;
  toggleMobileSidebar: () => void;

  // Responsive handling
  setIsMobile: (isMobile: boolean) => void;
  setIsTablet: (isTablet: boolean) => void;

  // Position
  setPosition: (position: SidebarPosition) => void;

  // Animation helpers
  setAnimating: (animating: boolean) => void;

  // Computed values
  getWidth: () => string;
  isOpen: () => boolean;
  shouldShowTooltips: () => boolean;
}

const SIDEBAR_WIDTHS = {
  expanded: '280px',
  collapsed: '0px',
  mini: '64px',
} as const;

export const useSidebarStore = create<SidebarStore>()(
  persist(
    (set, get) => ({
      // Initial state
      state: 'expanded',
      position: 'left',
      isMobile: false,
      isTablet: false,
      mobileOpen: false,
      isAnimating: false,

      // State setters
      setState: (newState) => {
        const currentState = get();

        // Don't change state if mobile is open
        if (currentState.isMobile && currentState.mobileOpen && newState !== currentState.state) {
          return;
        }

        set((state) => ({
          state: newState,
          isAnimating: true,
        }));

        // Reset animation flag after transition
        setTimeout(() => {
          set({ isAnimating: false });
        }, 300);
      },

      toggleSidebar: () => {
        const { state, isMobile, mobileOpen } = get();

        if (isMobile) {
          get().setMobileOpen(!mobileOpen);
        } else {
          // Cycle through states: expanded -> mini -> collapsed -> expanded
          switch (state) {
            case 'expanded':
              get().setMiniMode();
              break;
            case 'mini':
              get().collapseSidebar();
              break;
            case 'collapsed':
              get().expandSidebar();
              break;
          }
        }
      },

      expandSidebar: () => {
        get().setState('expanded');
      },

      collapseSidebar: () => {
        get().setState('collapsed');
      },

      setMiniMode: () => {
        get().setState('mini');
      },

      // Mobile actions
      setMobileOpen: (open) => {
        set({ mobileOpen: open });
      },

      toggleMobileSidebar: () => {
        set((state) => ({ mobileOpen: !state.mobileOpen }));
      },

      // Responsive handling
      setIsMobile: (isMobile) => {
        const currentState = get();

        set({ isMobile });

        // Auto-collapse sidebar on mobile
        if (isMobile && currentState.state !== 'collapsed') {
          set({ state: 'collapsed', mobileOpen: false });
        }
      },

      setIsTablet: (isTablet) => {
        const currentState = get();

        set({ isTablet });

        // Auto-switch to mini mode on tablet
        if (isTablet && !currentState.isMobile && currentState.state === 'expanded') {
          get().setMiniMode();
        }
      },

      // Position
      setPosition: (position) => {
        set({ position });
      },

      // Animation helpers
      setAnimating: (animating) => {
        set({ isAnimating: animating });
      },

      // Computed values
      getWidth: () => {
        const { state, isMobile } = get();

        if (isMobile) {
          return SIDEBAR_WIDTHS.expanded;
        }

        return SIDEBAR_WIDTHS[state];
      },

      isOpen: () => {
        const { state, isMobile, mobileOpen } = get();

        if (isMobile) {
          return mobileOpen;
        }

        return state !== 'collapsed';
      },

      shouldShowTooltips: () => {
        const { state, isMobile } = get();
        return state === 'mini' && !isMobile;
      },
    }),
    {
      name: 'sidebar-storage',
      storage: createJSONStorage(() => localStorage),
      // Only persist certain fields
      partialize: (state) => ({
        state: state.state,
        position: state.position,
      }),
      // Handle hydration
      onRehydrateStorage: () => (state) => {
        // Apply responsive adjustments after hydration
        if (state && typeof window !== 'undefined') {
          const isMobile = window.innerWidth < 768;
          const isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;

          if (isMobile) {
            state.isMobile = true;
            state.mobileOpen = false;
          } else if (isTablet) {
            state.isTablet = true;
            // Force mini mode on tablets
            if (state.state === 'expanded') {
              state.state = 'mini';
            }
          }
        }
      },
    }
  )
);

// Keyboard shortcuts
export const useSidebarKeyboardShortcuts = () => {
  const toggleSidebar = useSidebarStore((state) => state.toggleSidebar);
  const expandSidebar = useSidebarStore((state) => state.expandSidebar);
  const collapseSidebar = useSidebarStore((state) => state.collapseSidebar);

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Toggle sidebar with Cmd/Ctrl + B
      if ((event.metaKey || event.ctrlKey) && event.key === 'b') {
        event.preventDefault();
        toggleSidebar();
      }

      // Expand with Cmd/Ctrl + Shift + B
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key === 'B') {
        event.preventDefault();
        expandSidebar();
      }

      // Collapse with Cmd/Ctrl + Alt + B
      if ((event.metaKey || event.ctrlKey) && event.altKey && event.key === 'b') {
        event.preventDefault();
        collapseSidebar();
      }

      // Close sidebar with Escape on mobile
      if (event.key === 'Escape') {
        const state = useSidebarStore.getState();
        if (state.isMobile && state.mobileOpen) {
          state.setMobileOpen(false);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar, expandSidebar, collapseSidebar]);
};