'use client';

import * as React from 'react';
import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import {
  BookOpen,
  FileText,
  Info,
  LifeBuoy,
  LogIn,
  MessageSquare,
  Search,
  Upload,
  UserPlus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle,
} from '@/components/ui/navigation-menu';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

// Simple logo component for the navbar
const Logo = (props: React.SVGAttributes<SVGElement>) => {
  return (
    <svg width='1em' height='1em' viewBox='0 0 324 323' fill='currentColor' xmlns='http://www.w3.org/2000/svg' {...props}>
      <rect
        x='88.1023'
        y='144.792'
        width='151.802'
        height='36.5788'
        rx='18.2894'
        transform='rotate(-38.5799 88.1023 144.792)'
        fill='currentColor'
      />
      <rect
        x='85.3459'
        y='244.537'
        width='151.802'
        height='36.5788'
        rx='18.2894'
        transform='rotate(-38.5799 85.3459 244.537)'
        fill='currentColor'
      />
    </svg>
  );
};

// Hamburger icon component
const HamburgerIcon = ({ className, ...props }: React.SVGAttributes<SVGElement>) => (
  <svg
    className={cn('pointer-events-none', className)}
    width={24}
    height={24}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <line x1="4" x2="20" y1="12" y2="12" />
    <line x1="4" x2="20" y1="6" y2="6" />
    <line x1="4" x2="20" y1="18" y2="18" />
  </svg>
);

// Types
export interface Navbar02NavItem {
  href?: string;
  label: string;
  submenu?: boolean;
  type?: 'description' | 'simple' | 'icon';
  items?: Array<{
    href: string;
    label: string;
    description?: string;
    icon?: string;
  }>;
}

export interface Navbar02Props extends React.HTMLAttributes<HTMLElement> {
  logo?: React.ReactNode;
  logoHref?: string;
  navigationLinks?: Navbar02NavItem[];
  signInText?: string;
  signInHref?: string;
  ctaText?: string;
  ctaHref?: string;
  onSignInClick?: () => void;
  onCtaClick?: () => void;
}

// Default navigation links (placeholder)
const defaultNavigationLinks: Navbar02NavItem[] = [
  { href: '#', label: 'Home' },
];

export const Navbar02 = React.forwardRef<HTMLElement, Navbar02Props>(
  (
    {
      className,
      logo = <Logo />,
      logoHref = '#',
      navigationLinks = defaultNavigationLinks,
      signInText = 'Sign In',
      signInHref = '#signin',
      ctaText = 'Get Started',
      ctaHref = '#get-started',
      onSignInClick,
      onCtaClick,
      ...props
    },
    ref
  ) => {
    const [isMobile, setIsMobile] = useState(false);
    const containerRef = useRef<HTMLElement>(null);

    useEffect(() => {
      const checkWidth = () => {
        if (containerRef.current) {
          const width = containerRef.current.offsetWidth;
          setIsMobile(width < 768); // 768px is md breakpoint
        }
      };

      checkWidth();

      const resizeObserver = new ResizeObserver(checkWidth);
      if (containerRef.current) {
        resizeObserver.observe(containerRef.current);
      }

      return () => {
        resizeObserver.disconnect();
      };
    }, []);

    // Combine refs
    const combinedRef = React.useCallback((node: HTMLElement | null) => {
      containerRef.current = node;
      if (typeof ref === 'function') {
        ref(node);
      } else if (ref) {
        ref.current = node;
      }
    }, [ref]);

    return (
      <header
        ref={combinedRef}
        className={cn(
          'sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-lg transition-all duration-200',
          'px-4 md:px-6 [&_*]:no-underline',
          className
        )}
        {...props}
      >
        <div className="container mx-auto flex h-14 md:h-16 max-w-screen-2xl items-center justify-between gap-4">
          {/* Left side */}
          <div className="flex items-center gap-2">
            {/* Mobile menu trigger */}
            {isMobile && (
              <Sheet>
                <SheetTrigger asChild>
                  <Button
                    className="h-9 w-9 shrink-0 md:hidden"
                    variant="ghost"
                    size="icon"
                  >
                    <HamburgerIcon />
                    <span className="sr-only">Toggle navigation menu</span>
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-[300px] sm:w-[400px] pr-0">
                  <SheetHeader className="px-1 pb-4 text-left">
                    <SheetTitle className="flex items-center gap-2">
                      <div className="text-xl font-bold">{logo}</div>
                    </SheetTitle>
                  </SheetHeader>
                  <div className="flex flex-col gap-4 py-4 pr-6 h-full overflow-y-auto">
                    <nav className="flex flex-col gap-1">
                      {navigationLinks.map((link, index) => (
                        <div key={index} className="flex flex-col gap-2 py-2">
                          {link.submenu ? (
                            <>
                              <div className="font-medium text-sm text-muted-foreground px-2">
                                {link.label}
                              </div>
                              <div className="flex flex-col gap-1 pl-2 border-l ml-2">
                                {link.items?.map((item, itemIndex) => (
                                  <Link
                                    key={itemIndex}
                                    href={item.href}
                                    className="flex w-full items-center rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground text-foreground/80"
                                  >
                                    {item.icon && (
                                      <span className="mr-2 opacity-70">
                                        {/* Simple icon render for mobile if needed, keeping it text-based mostly for clean layout */}
                                      </span>
                                    )}
                                    {item.label}
                                  </Link>
                                ))}
                              </div>
                            </>
                          ) : (
                            <Link
                              href={link.href ?? '#'}
                              className="flex w-full items-center rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
                            >
                              {link.label}
                            </Link>
                          )}
                        </div>
                      ))}
                    </nav>
                    <div className="mt-auto border-t pt-6 flex flex-col gap-3">
                       <Button
                        variant="outline"
                        className="w-full justify-start"
                        onClick={(e) => {
                          e.preventDefault();
                          if (onSignInClick) onSignInClick();
                        }}
                      >
                        <LogIn className="mr-2 h-4 w-4" />
                        {signInText}
                      </Button>
                      <Button
                        className="w-full justify-start"
                        onClick={(e) => {
                          e.preventDefault();
                          if (onCtaClick) onCtaClick();
                        }}
                      >
                        <UserPlus className="mr-2 h-4 w-4" />
                        {ctaText}
                      </Button>
                    </div>
                  </div>
                </SheetContent>
              </Sheet>
            )}

            {/* Desktop Logo */}
            <Link
              href={logoHref}
              className="flex items-center space-x-2 text-primary hover:text-primary/90 transition-colors cursor-pointer mr-4"
            >
              <div className="text-2xl flex items-center justify-center">
                {logo}
              </div>
            </Link>

            {/* Desktop Navigation */}
            {!isMobile && (
              <NavigationMenu className="hidden md:flex">
                <NavigationMenuList className="gap-1">
                  {navigationLinks.map((link, index) => (
                    <NavigationMenuItem key={index}>
                      {link.submenu ? (
                        <>
                          <NavigationMenuTrigger className="text-sm font-medium bg-transparent hover:bg-accent focus:bg-accent data-[state=open]:bg-accent/50 transition-colors h-9 px-4 py-2">
                            {link.label}
                          </NavigationMenuTrigger>
                          <NavigationMenuContent>
                            {/* Mega Menu Layouts */}
                            {link.type === 'description' && link.label === 'Features' ? (
                              <ul className="grid gap-3 p-4 md:w-[400px] lg:w-[500px] lg:grid-cols-[.75fr_1fr]">
                                <li className="row-span-3">
                                  <NavigationMenuLink asChild>
                                    <Link
                                      href="/search"
                                      className="flex h-full w-full select-none flex-col justify-end rounded-md bg-gradient-to-b from-muted/50 to-muted p-6 no-underline outline-none focus:shadow-md cursor-pointer hover:bg-muted/80 transition-colors group"
                                    >
                                      <BookOpen className="h-6 w-6 mb-2 opacity-70 group-hover:opacity-100 transition-opacity" aria-hidden={true} />
                                      <div className="mb-2 text-lg font-medium">
                                        Enterprise RAG
                                      </div>
                                      <p className="text-sm leading-tight text-muted-foreground">
                                        Advanced retrieval-augmented generation with multimodal support.
                                      </p>
                                    </Link>
                                  </NavigationMenuLink>
                                </li>
                                <div className="flex flex-col gap-2">
                                  {link.items?.map((item, itemIndex) => (
                                    <ListItem
                                      key={itemIndex}
                                      title={item.label}
                                      href={item.href}
                                      type={link.type}
                                      icon={item.icon}
                                    >
                                      {item.description}
                                    </ListItem>
                                  ))}
                                </div>
                              </ul>
                            ) : link.type === 'simple' ? (
                              <ul className="grid w-[400px] gap-3 p-4 md:w-[500px] md:grid-cols-2 lg:w-[600px]">
                                {link.items?.map((item, itemIndex) => (
                                  <ListItem
                                    key={itemIndex}
                                    title={item.label}
                                    href={item.href}
                                    type={link.type}
                                  >
                                    {item.description}
                                  </ListItem>
                                ))}
                              </ul>
                            ) : link.type === 'icon' ? (
                              <ul className="grid w-[400px] gap-3 p-4">
                                {link.items?.map((item, itemIndex) => (
                                  <ListItem
                                    key={itemIndex}
                                    title={item.label}
                                    href={item.href}
                                    icon={item.icon}
                                    type={link.type}
                                  >
                                    {item.description}
                                  </ListItem>
                                ))}
                              </ul>
                            ) : (
                              <ul className="grid gap-3 p-4 w-[400px]">
                                {link.items?.map((item, itemIndex) => (
                                  <ListItem
                                    key={itemIndex}
                                    title={item.label}
                                    href={item.href}
                                    type={link.type}
                                  >
                                    {item.description}
                                  </ListItem>
                                ))}
                              </ul>
                            )}
                          </NavigationMenuContent>
                        </>
                      ) : (
                        <NavigationMenuLink asChild>
                          <Link
                            href={link.href ?? '#'}
                            className={cn(
                              navigationMenuTriggerStyle(),
                              'text-sm font-medium bg-transparent hover:bg-accent focus:bg-accent h-9 px-4 py-2 cursor-pointer'
                            )}
                          >
                            {link.label}
                          </Link>
                        </NavigationMenuLink>
                      )}
                    </NavigationMenuItem>
                  ))}
                </NavigationMenuList>
              </NavigationMenu>
            )}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2 md:gap-4">
            <div className="hidden md:flex items-center gap-2">
                <Button
                variant="ghost"
                size="sm"
                className="text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                onClick={(e) => {
                    e.preventDefault();
                    if (onSignInClick) onSignInClick();
                }}
                >
                {signInText}
                </Button>
                <Button
                size="sm"
                className="text-sm font-medium px-5 h-9 rounded-md shadow-sm transition-all hover:shadow-md active:scale-95"
                onClick={(e) => {
                    e.preventDefault();
                    if (onCtaClick) onCtaClick();
                }}
                >
                {ctaText}
                </Button>
            </div>
          </div>
        </div>
      </header>
    );
  }
);

Navbar02.displayName = 'Navbar02';

// ListItem component for navigation menu items
const ListItem = React.forwardRef<
  React.ElementRef<'a'>,
  Omit<React.ComponentPropsWithoutRef<typeof Link>, 'href'> & {
    title: string;
    href?: string;
    icon?: string;
    type?: 'description' | 'simple' | 'icon';
    children?: React.ReactNode;
  }
>(({ className, title, children, icon, type, href = '#', ...props }, ref) => {
  const renderIconComponent = (iconName?: string) => {
    if (!iconName) return null;
    switch (iconName) {
      case 'BookOpen': return <BookOpen className="h-5 w-5" />;
      case 'LifeBuoy': return <LifeBuoy className="h-5 w-5" />;
      case 'Info': return <Info className="h-5 w-5" />;
      case 'Search': return <Search className="h-5 w-5" />;
      case 'MessageSquare': return <MessageSquare className="h-5 w-5" />;
      case 'FileText': return <FileText className="h-5 w-5" />;
      case 'Upload': return <Upload className="h-5 w-5" />;
      case 'LogIn': return <LogIn className="h-5 w-5" />;
      case 'UserPlus': return <UserPlus className="h-5 w-5" />;
      default: return null;
    }
  };

  return (
    <li>
      <NavigationMenuLink asChild>
        <Link
          ref={ref}
          href={href}
          className={cn(
            'block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground cursor-pointer group',
            className
          )}
          {...props}
        >
          {type === 'icon' && icon ? (
            <div className="flex items-start space-x-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground group-hover:text-primary transition-colors">
                {renderIconComponent(icon)}
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium leading-tight group-hover:text-primary transition-colors">{title}</div>
                {children && (
                  <p className="line-clamp-2 text-xs leading-snug text-muted-foreground/90 group-hover:text-muted-foreground">
                    {children}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className="text-sm font-medium leading-none group-hover:text-primary transition-colors">{title}</div>
              {children && (
                <p className="line-clamp-2 text-xs leading-snug text-muted-foreground/90 group-hover:text-muted-foreground">
                  {children}
                </p>
              )}
            </>
          )}
        </Link>
      </NavigationMenuLink>
    </li>
  );
});
ListItem.displayName = 'ListItem';

export { Logo, HamburgerIcon };
