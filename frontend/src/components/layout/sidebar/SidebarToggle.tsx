'use client';

import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { Menu, PanelLeft, PanelRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';

export function SidebarToggle() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Load state from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('sidebar-collapsed');
    if (saved) {
      setIsCollapsed(JSON.parse(saved));
    }
    // Check if mobile
    setIsMobile(window.innerWidth < 768);
  }, []);

  // Save state when it changes
  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', JSON.stringify(isCollapsed));
  }, [isCollapsed]);

  // Handle keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        setIsCollapsed(!isCollapsed);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCollapsed]);

  // Handle responsive behavior
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setIsCollapsed(false); // Always show sidebar on mobile as overlay
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={
            isMobile
              ? 'Menu'
              : isCollapsed
                ? 'Open Sidebar (⌘B)'
                : 'Close Sidebar (⌘B)'
          }
          className={cn(
            'h-8 w-8 transition-all duration-200',
            'hover:bg-accent hover:text-accent-foreground'
          )}
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isMobile ? (
            <Menu className="h-4 w-4" />
          ) : isCollapsed ? (
            <PanelRight className="h-4 w-4" />
          ) : (
            <PanelLeft className="h-4 w-4" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">
        <p className="text-xs">
          {isMobile ? 'Menu' : isCollapsed ? 'Open Sidebar' : 'Close Sidebar'}
          <span className="text-muted-foreground ml-1">(⌘B)</span>
        </p>
      </TooltipContent>
    </Tooltip>
  );
}
