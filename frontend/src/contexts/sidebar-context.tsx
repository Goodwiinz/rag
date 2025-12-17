'use client';

import React, { createContext, useContext, useEffect, type ReactNode } from 'react';
import { useSidebarStore } from '@/store/sidebar-store';
import { useIsMobile } from '@/hooks/use-mobile';

type SidebarContextType = {
  // State from store
  state: 'expanded' | 'collapsed' | 'mini';
  isMobile: boolean;
  mobileOpen: boolean;
  isAnimating: boolean;

  // Actions
  toggleSidebar: () => void;
  setMobileOpen: (open: boolean) => void;
  expandSidebar: () => void;
  collapseSidebar: () => void;
  setMiniMode: () => void;

  // Computed
  isOpen: boolean;
  shouldShowTooltips: boolean;
  getWidth: () => string;
} & {
  // Additional context-specific values
  isTransitioning: boolean;
  variant: 'sidebar' | 'floating' | 'inset';
};

const SidebarContext = createContext<SidebarContextType | null>(null);

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error('useSidebar must be used within an EnhancedSidebarProvider');
  }
  return context;
}

interface EnhancedSidebarProviderProps {
  children: ReactNode;
  defaultOpen?: boolean;
  variant?: 'sidebar' | 'floating' | 'inset';
}

export function EnhancedSidebarProvider({
  children,
  defaultOpen = true,
  variant = 'sidebar',
}: EnhancedSidebarProviderProps) {
  const isMobile = useIsMobile();

  // Store integration
  const {
    state,
    mobileOpen,
    isAnimating,
    toggleSidebar: storeToggle,
    setMobileOpen,
    expandSidebar,
    collapseSidebar,
    setMiniMode,
    isOpen,
    shouldShowTooltips,
    getWidth,
    setIsMobile,
    setIsTablet,
  } = useSidebarStore();

  // Handle responsive state updates
  useEffect(() => {
    setIsMobile(isMobile);

    // Detect tablet size for mini mode
    const isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;
    setIsTablet(isTablet);

    // Handle body scroll lock on mobile
    if (isMobile && mobileOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobile, mobileOpen, setIsMobile, setIsTablet]);

  // Enhanced toggle with animation delay
  const toggleSidebar = () => {
    setMobileOpen(false);
    setTimeout(() => {
      storeToggle();
    }, isMobile ? 300 : 0);
  };

  const value: SidebarContextType = {
    state,
    isMobile,
    mobileOpen,
    isAnimating,
    toggleSidebar,
    setMobileOpen,
    expandSidebar,
    collapseSidebar,
    setMiniMode,
    isOpen,
    shouldShowTooltips,
    getWidth,
    isTransitioning: isAnimating,
    variant,
  };

  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  );
}