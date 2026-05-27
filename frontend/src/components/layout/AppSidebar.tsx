'use client';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  ChevronsUpDown,
  Files,
  FolderKanban,
  HelpCircle,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Network,
  Search,
  Settings,
  Sparkles,
  Upload,
  Workflow,
} from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';

// Navigation items organized by section
const mainNavItems = [
  { title: 'Overview', url: '/dashboard', icon: LayoutDashboard },
  { title: 'Chat', url: '/chat', icon: MessageSquare },
  { title: 'Search', url: '/search', icon: Search },
];

const knowledgeNavItems = [
  { title: 'Documents', url: '/documents', icon: Files },
  { title: 'Upload', url: '/documents/upload', icon: Upload },
  { title: 'ArXiv Papers', url: '/arxiv', icon: BookOpen },
  { title: 'Entities', url: '/entities', icon: Network },
  { title: 'Research', url: '/research', icon: FolderKanban },
  { title: 'Research Engine', url: '/research-engine', icon: Workflow },
];

const systemNavItems = [
  { title: 'Analytics', url: '/analytics', icon: BarChart3 },
  { title: 'Diagnostics', url: '/diagnostics', icon: Activity },
  { title: 'Settings', url: '/settings', icon: Settings },
];

// System metrics type
interface SystemMetrics {
  uptime: string;
  cpu: string;
  memory: string;
  queries: string;
}

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const { setOpen } = useSidebar();
  const { resolvedTheme } = useTheme();

  // Auto-collapse sidebar when navigating to /chat, but only on route change
  // so the user can still toggle it open manually
  const prevPathnameRef = useRef(pathname);
  useEffect(() => {
    const prev = prevPathnameRef.current;
    prevPathnameRef.current = pathname;

    const isChat = pathname === '/chat' || pathname?.startsWith('/chat/');
    const wasChat = prev === '/chat' || prev?.startsWith('/chat/');

    if (isChat && !wasChat) {
      setOpen(false);
    } else if (!isChat && wasChat) {
      setOpen(true);
    }
  }, [pathname, setOpen]);

  // Static metrics (replace with real API call when backend endpoint is available)
  const metrics: SystemMetrics = {
    uptime: '99.4%',
    cpu: '23%',
    memory: '67%',
    queries: '1,247',
  };

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const getInitials = (email: string | undefined) => {
    if (!email) return 'U';
    const name = email.split('@')[0];
    return name.slice(0, 2).toUpperCase();
  };

  const isActive = (url: string) => {
    if (url === '/') return pathname === '/';
    return pathname?.startsWith(url);
  };

  const displayName = user?.email?.split('@')[0] || 'User';

  // Navigation item component matching the design
  const NavItem = ({
    item,
  }: {
    item: {
      title: string;
      url: string;
      icon: React.ComponentType<{ className?: string }>;
    };
  }) => {
    const active = isActive(item.url);
    const Icon = item.icon;
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          asChild
          isActive={active}
          tooltip={item.title}
          className={cn(
            'group/nav font-mono text-xs transition-all duration-200 h-10 rounded-none border-l-2',
            'group-data-[collapsible=icon]:!h-9 group-data-[collapsible=icon]:!w-9 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:rounded-md group-data-[collapsible=icon]:border-l-0',
            active
              ? 'bg-primary/10 text-sidebar-foreground border-l-primary group-data-[collapsible=icon]:bg-primary/15'
              : 'text-muted-foreground border-l-transparent hover:text-sidebar-foreground hover:bg-sidebar-accent hover:border-l-primary/50 group-data-[collapsible=icon]:hover:bg-sidebar-accent'
          )}
        >
          <Link
            href={item.url}
            data-testid={
              item.url === '/analytics' ? 'analytics-nav-link' : undefined
            }
            className="flex items-center gap-3 w-full px-5 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:justify-center"
          >
            <Icon
              className={cn(
                'w-4 h-4 flex-shrink-0 transition-colors duration-200',
                active
                  ? 'text-primary'
                  : 'text-muted-foreground group-hover/nav:text-primary'
              )}
            />
            <span className="truncate group-data-[collapsible=icon]:hidden font-medium">
              {item.title}
            </span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  };

  // Section label component (// MAIN, // DOCUMENTS, etc.) - hidden when collapsed
  const SectionLabel = ({ children }: { children: string }) => (
    <div className="px-5 py-2 font-mono text-[9px] font-medium tracking-wider text-primary uppercase group-data-[collapsible=icon]:hidden">
      {`// ${children}`}
    </div>
  );

  return (
    <Sidebar
      collapsible="icon"
      className="border-sidebar-border !bg-sidebar z-50"
    >
      {/* Header with Logo */}
      <SidebarHeader className="border-b border-sidebar-border px-5 py-4 group-data-[collapsible=icon]:px-1 group-data-[collapsible=icon]:py-2 bg-sidebar">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 group-data-[collapsible=icon]:justify-center"
        >
          {/* Collapsed: show icon only */}
          <Image
            src={
              resolvedTheme === 'dark'
                ? '/nous-logo-dark.svg'
                : '/nous-logo.svg'
            }
            alt="NOUS"
            width={28}
            height={28}
            className="flex-shrink-0 hidden group-data-[collapsible=icon]:block group-data-[collapsible=icon]:w-7 group-data-[collapsible=icon]:h-7"
          />
          {/* Expanded: show full logo */}
          <Image
            src={
              resolvedTheme === 'dark'
                ? '/nous-logo-dark.svg'
                : '/nous-logo.svg'
            }
            alt="NOUS — Multimodal Intelligence"
            width={160}
            height={38}
            className="h-[38px] w-auto group-data-[collapsible=icon]:hidden"
            priority
          />
        </Link>
      </SidebarHeader>

      <SidebarContent className="flex flex-col justify-between py-6 group-data-[collapsible=icon]:py-2 bg-sidebar">
        <div className="flex-1">
          {/* Main Navigation */}
          <SidebarGroup className="py-0 group-data-[collapsible=icon]:px-1">
            <SectionLabel>MAIN</SectionLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-0.5 group-data-[collapsible=icon]:space-y-1">
                {mainNavItems.map((item) => (
                  <NavItem key={item.title} item={item} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {/* Knowledge Navigation */}
          <SidebarGroup className="py-0 mt-4 group-data-[collapsible=icon]:mt-2 group-data-[collapsible=icon]:px-1">
            <SectionLabel>KNOWLEDGE</SectionLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-0.5 group-data-[collapsible=icon]:space-y-1">
                {knowledgeNavItems.map((item) => (
                  <NavItem key={item.title} item={item} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {/* System Navigation */}
          <SidebarGroup className="py-0 mt-4 group-data-[collapsible=icon]:mt-2 group-data-[collapsible=icon]:px-1">
            <SectionLabel>SYSTEM</SectionLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-0.5 group-data-[collapsible=icon]:space-y-1">
                {systemNavItems.map((item) => (
                  <NavItem key={item.title} item={item} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </div>

        {/* System Status Panel */}
        <div className="mt-8 group-data-[collapsible=icon]:hidden">
          <div className="bg-sidebar border-y border-sidebar-border px-5 py-3">
            <SectionLabel>SYSTEM STATUS</SectionLabel>
            <div className="space-y-2 mt-2">
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-muted-foreground">
                  UPTIME
                </span>
                <span className="font-mono text-[10px] font-medium text-primary">
                  {metrics.uptime}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-muted-foreground">
                  CPU
                </span>
                <span className="font-mono text-[10px] font-medium text-sidebar-foreground">
                  {metrics.cpu}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-muted-foreground">
                  MEMORY
                </span>
                <span className="font-mono text-[10px] font-medium text-[var(--amber-gold)]">
                  {metrics.memory}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-muted-foreground">
                  QUERIES
                </span>
                <span className="font-mono text-[10px] font-medium text-[var(--cyan)]">
                  {metrics.queries}
                </span>
              </div>
            </div>
          </div>

          {/* Premium Upgrade Card */}
          <div className="mx-5 mt-4 p-4 border-2 border-primary/25 rounded-none group-data-[collapsible=icon]:hidden">
            <div className="flex items-center gap-2 mb-2">
              <span className="bg-primary/15 text-primary font-mono text-[9px] font-semibold px-2 py-1 rounded">
                PRO
              </span>
              <span className="font-mono text-[11px] font-semibold text-primary">
                UNLOCK PREMIUM
              </span>
            </div>
            <p className="font-mono text-[10px] text-muted-foreground leading-relaxed mb-3">
              Advanced RAG features, unlimited queries, and priority support.
            </p>
            <button className="w-full bg-primary text-primary-foreground font-mono text-[9px] font-bold py-2.5 hover:bg-primary/90 transition-colors flex items-center justify-center gap-1.5">
              <Sparkles className="w-3 h-3" />
              UPGRADE NOW
            </button>
          </div>
        </div>
      </SidebarContent>

      {/* Footer with User Menu */}
      <SidebarFooter className="border-t border-sidebar-border p-0 group-data-[collapsible=icon]:p-1.5 bg-sidebar">
        <SidebarMenu>
          <SidebarMenuItem>
            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    data-testid="user-menu"
                    className="h-auto px-5 py-3 hover:bg-sidebar data-[state=open]:bg-sidebar rounded-none group-data-[collapsible=icon]:!w-9 group-data-[collapsible=icon]:!h-9 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:rounded-md group-data-[collapsible=icon]:mx-auto"
                  >
                    {/* Avatar */}
                    <div className="flex items-center justify-center w-8 h-8 border border-primary/30 rounded flex-shrink-0 bg-primary/10">
                      <span className="font-mono text-[10px] font-semibold text-primary">
                        {getInitials(user?.email)}
                      </span>
                    </div>
                    {/* User Info */}
                    <div className="flex flex-col gap-0.5 leading-none text-left flex-1 group-data-[collapsible=icon]:hidden">
                      <span className="font-mono text-[11px] font-medium text-sidebar-foreground truncate">
                        {displayName}
                      </span>
                      <span className="font-mono text-[9px] text-muted-foreground truncate">
                        Administrator
                      </span>
                    </div>
                    <ChevronsUpDown className="w-4 h-4 text-muted-foreground flex-shrink-0 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-56 bg-sidebar border-sidebar-border font-mono"
                  side="top"
                  align="start"
                  sideOffset={4}
                >
                  <DropdownMenuLabel className="text-muted-foreground text-xs font-normal">
                    <div className="flex flex-col gap-1">
                      <span className="text-sidebar-foreground font-medium">
                        {displayName}
                      </span>
                      <span className="text-muted-foreground text-[10px]">
                        {user?.email || 'Not signed in'}
                      </span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-sidebar-border" />
                  <DropdownMenuItem
                    asChild
                    className="hover:bg-sidebar-accent focus:bg-sidebar-accent cursor-pointer"
                  >
                    <Link
                      href="/settings"
                      className="flex items-center gap-2 text-muted-foreground hover:text-sidebar-foreground"
                    >
                      <Settings className="w-4 h-4" />
                      Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    asChild
                    className="hover:bg-sidebar-accent focus:bg-sidebar-accent cursor-pointer"
                  >
                    <Link
                      href="/notifications"
                      className="flex items-center gap-2 text-muted-foreground hover:text-sidebar-foreground"
                    >
                      <Bell className="w-4 h-4" />
                      Notifications
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    asChild
                    className="hover:bg-sidebar-accent focus:bg-sidebar-accent cursor-pointer"
                  >
                    <Link
                      href="/help"
                      className="flex items-center gap-2 text-muted-foreground hover:text-sidebar-foreground"
                    >
                      <HelpCircle className="w-4 h-4" />
                      Help Center
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-sidebar-border" />
                  <DropdownMenuItem
                    onClick={handleLogout}
                    data-testid="logout-button"
                    className="text-red-400 hover:text-red-300 hover:bg-red-500/10 focus:bg-red-500/10 cursor-pointer"
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Sign Out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <SidebarMenuButton
                asChild
                size="lg"
                tooltip="Sign In"
                className="bg-sidebar text-sidebar-foreground border-t border-sidebar-border hover:bg-sidebar-accent rounded-none h-auto px-5 py-4 group-data-[collapsible=icon]:!w-9 group-data-[collapsible=icon]:!h-9 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:rounded-md group-data-[collapsible=icon]:border-t-0"
              >
                <Link
                  href="/login"
                  className="flex items-center gap-3 group-data-[collapsible=icon]:justify-center"
                >
                  <LogOut className="w-4 h-4 text-primary" />
                  <span className="font-mono text-[11px] group-data-[collapsible=icon]:hidden">
                    Sign In
                  </span>
                </Link>
              </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail className="hover:after:bg-primary/30" />
    </Sidebar>
  );
}
