import React, { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Menu, Layers } from 'lucide-react';
import { mainNavigation, bottomNavigation, navigation, NavigationItem } from './navigation';

const SIDEBAR_STORAGE_KEY = 'sidebar-collapsed';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  className?: string;
}

const NavItem = ({ 
  item, 
  isActive, 
  isCollapsed,
  onClick 
}: { 
  item: NavigationItem; 
  isActive: boolean; 
  isCollapsed: boolean;
  onClick?: () => void;
}) => {
  const Icon = item.icon;
  
  const linkContent = (
    <Link
      to={item.href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
        "hover:bg-accent/80",
        isActive 
          ? "bg-accent text-accent-foreground" 
          : "text-muted-foreground hover:text-foreground",
        isCollapsed && "justify-center px-2"
      )}
    >
      <Icon className={cn(
        "h-5 w-5 flex-shrink-0 transition-colors",
        isActive ? "text-foreground" : "text-muted-foreground"
      )} />
      {!isCollapsed && (
        <span className="truncate">{item.name}</span>
      )}
      {!isCollapsed && item.badge && (
        <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-medium text-primary-foreground">
          {item.badge}
        </span>
      )}
    </Link>
  );

  if (isCollapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          {linkContent}
        </TooltipTrigger>
        <TooltipContent side="right" className="flex items-center gap-2">
          {item.name}
          {item.badge && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-medium text-primary-foreground">
              {item.badge}
            </span>
          )}
        </TooltipContent>
      </Tooltip>
    );
  }

  return linkContent;
};

export const Sidebar = ({ isOpen, setIsOpen, className }: SidebarProps) => {
  const location = useLocation();
  const isCollapsed = !isOpen;

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (stored !== null) {
      setIsOpen(stored !== 'true');
    }
  }, [setIsOpen]);

  const handleToggle = () => {
    const newCollapsed = !isCollapsed;
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(newCollapsed));
    setIsOpen(!newCollapsed);
  };

  const isActive = (href: string) => {
    if (href === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(href);
  };

  return (
    <TooltipProvider>
      <aside
        className={cn(
          "hidden md:flex flex-col border-r bg-background h-screen sticky top-0 transition-all duration-300 ease-in-out",
          isCollapsed ? "w-[68px]" : "w-60",
          className
        )}
      >
        {/* Logo / Sidebar Toggle */}
        <button
          type="button"
          onClick={handleToggle}
          className={cn(
            "h-14 w-full flex items-center border-b px-3 cursor-pointer hover:bg-accent/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
            isCollapsed ? "justify-center" : "gap-2"
          )}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!isCollapsed}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
            <Layers className="h-5 w-5 text-primary-foreground" />
          </div>
          {!isCollapsed && (
            <span className="font-semibold text-foreground truncate">
              RAG System
            </span>
          )}
        </button>

        {/* Main Navigation */}
        <ScrollArea className="flex-1 py-3">
          <nav aria-label="Main navigation" className="grid gap-1 px-2">
            {mainNavigation.map((item) => (
              <NavItem
                key={item.name}
                item={item}
                isActive={isActive(item.href)}
                isCollapsed={isCollapsed}
              />
            ))}
          </nav>
        </ScrollArea>

        {/* Bottom Navigation */}
        <div className="border-t py-3">
          <nav aria-label="Utility navigation" className="grid gap-1 px-2">
            {bottomNavigation.map((item) => (
              <NavItem
                key={item.name}
                item={item}
                isActive={isActive(item.href)}
                isCollapsed={isCollapsed}
              />
            ))}
          </nav>
        </div>
      </aside>
    </TooltipProvider>
  );
};

export const MobileNav = () => {
  const location = useLocation();
  const [open, setOpen] = React.useState(false);

  const isActive = (href: string) => {
    if (href === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(href);
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Open navigation" className="md:hidden">
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle Menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-0">
        <SheetHeader className="h-14 border-b px-4">
          <div className="flex items-center gap-2 h-full">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
              <Layers className="h-5 w-5 text-primary-foreground" />
            </div>
            <SheetTitle className="font-semibold">RAG System</SheetTitle>
          </div>
        </SheetHeader>
        <ScrollArea className="flex-1 py-3">
          <nav aria-label="Main navigation" className="grid gap-1 px-2">
            {mainNavigation.map((item) => (
              <NavItem
                key={item.name}
                item={item}
                isActive={isActive(item.href)}
                isCollapsed={false}
                onClick={() => setOpen(false)}
              />
            ))}
          </nav>
        </ScrollArea>
        <div className="border-t py-3">
          <nav aria-label="Utility navigation" className="grid gap-1 px-2">
            {bottomNavigation.map((item) => (
              <NavItem
                key={item.name}
                item={item}
                isActive={isActive(item.href)}
                isCollapsed={false}
                onClick={() => setOpen(false)}
              />
            ))}
          </nav>
        </div>
      </SheetContent>
    </Sheet>
  );
};
