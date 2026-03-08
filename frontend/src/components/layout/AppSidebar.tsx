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
  Terminal,
  Upload,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

// Navigation items organized by section
const mainNavItems = [
  { title: 'Overview', url: '/dashboard', icon: LayoutDashboard },
  { title: 'Chat', url: '/chat', icon: MessageSquare },
  { title: 'Search', url: '/search', icon: Search },
];

const documentsNavItems = [
  { title: 'All Documents', url: '/documents', icon: Files },
  { title: 'Upload', url: '/documents/upload', icon: Upload },
  { title: 'Entities', url: '/entities', icon: Network },
];

const researchNavItems = [
  { title: 'ArXiv Papers', url: '/arxiv', icon: BookOpen },
  { title: 'Research', url: '/research', icon: FolderKanban },
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

  // Auto-collapse sidebar on specific routes like /chat
  useEffect(() => {
    if (pathname === '/chat' || pathname?.startsWith('/chat/')) {
      setOpen(false);
    } else {
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
              ? 'bg-[#00FF88]/10 text-[#fafafa] border-l-[#00FF88] group-data-[collapsible=icon]:bg-[#00FF88]/15'
              : 'text-[#a1a1aa] border-l-transparent hover:text-[#fafafa] hover:bg-[#1A1A1A] hover:border-l-[#00FF88]/50 group-data-[collapsible=icon]:hover:bg-[#1A1A1A]'
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
                  ? 'text-[#00ff9f]'
                  : 'text-[#a1a1aa] group-hover/nav:text-[#00ff9f]'
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
    <div className="px-5 py-2 font-mono text-[9px] font-medium tracking-wider text-[#00FF88] uppercase group-data-[collapsible=icon]:hidden">
      {`// ${children}`}
    </div>
  );

  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-[#1A1A1A] !bg-[#0A0A0A] z-50"
    >
      {/* Header with Logo */}
      <SidebarHeader className="border-b border-[#1A1A1A] px-5 py-4 group-data-[collapsible=icon]:px-1 group-data-[collapsible=icon]:py-2 bg-[#0A0A0A]">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 group-data-[collapsible=icon]:justify-center"
        >
          <Terminal className="w-8 h-8 text-[#00FF88] flex-shrink-0 group-data-[collapsible=icon]:w-5 group-data-[collapsible=icon]:h-5" />
          <div className="flex flex-col gap-0.5 group-data-[collapsible=icon]:hidden">
            <span className="font-mono font-semibold text-[13px] text-[#fafafa] tracking-wider">
              RAG SYSTEM
            </span>
            <span className="font-mono text-[9px] text-[#a1a1aa]">v2.1.0</span>
          </div>
        </Link>
      </SidebarHeader>

      <SidebarContent className="flex flex-col justify-between py-6 group-data-[collapsible=icon]:py-2 bg-[#0A0A0A]">
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

          {/* Documents Navigation */}
          <SidebarGroup className="py-0 mt-4 group-data-[collapsible=icon]:mt-2 group-data-[collapsible=icon]:px-1">
            <SectionLabel>DOCUMENTS</SectionLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-0.5 group-data-[collapsible=icon]:space-y-1">
                {documentsNavItems.map((item) => (
                  <NavItem key={item.title} item={item} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {/* Research Navigation */}
          <SidebarGroup className="py-0 mt-4 group-data-[collapsible=icon]:mt-2 group-data-[collapsible=icon]:px-1">
            <SectionLabel>RESEARCH</SectionLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-0.5 group-data-[collapsible=icon]:space-y-1">
                {researchNavItems.map((item) => (
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
          <div className="bg-[#0A0A0A] border-y border-[#1A1A1A] px-5 py-3">
            <SectionLabel>SYSTEM STATUS</SectionLabel>
            <div className="space-y-2 mt-2">
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-[#a1a1aa]">
                  UPTIME
                </span>
                <span className="font-mono text-[10px] font-medium text-[#00ff9f]">
                  {metrics.uptime}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-[#a1a1aa]">
                  CPU
                </span>
                <span className="font-mono text-[10px] font-medium text-[#fafafa]">
                  {metrics.cpu}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-[#a1a1aa]">
                  MEMORY
                </span>
                <span className="font-mono text-[10px] font-medium text-[#ffb700]">
                  {metrics.memory}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-[#a1a1aa]">
                  QUERIES
                </span>
                <span className="font-mono text-[10px] font-medium text-[#00d4ff]">
                  {metrics.queries}
                </span>
              </div>
            </div>
          </div>

          {/* Premium Upgrade Card */}
          <div className="mx-5 mt-4 p-4 border-2 border-[#00FF88]/25 rounded-none group-data-[collapsible=icon]:hidden">
            <div className="flex items-center gap-2 mb-2">
              <span className="bg-[#00ff9f]/15 text-[#00ff9f] font-mono text-[9px] font-semibold px-2 py-1 rounded">
                PRO
              </span>
              <span className="font-mono text-[11px] font-semibold text-[#00ff9f]">
                UNLOCK PREMIUM
              </span>
            </div>
            <p className="font-mono text-[10px] text-[#a1a1aa] leading-relaxed mb-3">
              Advanced RAG features, unlimited queries, and priority support.
            </p>
            <button className="w-full bg-[#00FF88] text-[#050505] font-mono text-[9px] font-bold py-2.5 hover:bg-[#00FF88]/90 transition-colors flex items-center justify-center gap-1.5">
              <Sparkles className="w-3 h-3" />
              UPGRADE NOW
            </button>
          </div>
        </div>
      </SidebarContent>

      {/* Footer with User Menu */}
      <SidebarFooter className="border-t border-[#1A1A1A] p-0 group-data-[collapsible=icon]:p-1.5 bg-[#0A0A0A]">
        <SidebarMenu>
          <SidebarMenuItem>
            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    data-testid="user-menu"
                    className="h-auto px-5 py-3 hover:bg-[#0A0A0A] data-[state=open]:bg-[#0A0A0A] rounded-none group-data-[collapsible=icon]:!w-9 group-data-[collapsible=icon]:!h-9 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:rounded-md group-data-[collapsible=icon]:mx-auto"
                  >
                    {/* Avatar */}
                    <div className="flex items-center justify-center w-8 h-8 border border-[#00FF88]/30 rounded flex-shrink-0 bg-[#00FF88]/10">
                      <span className="font-mono text-[10px] font-semibold text-[#00ff9f]">
                        {getInitials(user?.email)}
                      </span>
                    </div>
                    {/* User Info */}
                    <div className="flex flex-col gap-0.5 leading-none text-left flex-1 group-data-[collapsible=icon]:hidden">
                      <span className="font-mono text-[11px] font-medium text-[#fafafa] truncate">
                        {displayName}
                      </span>
                      <span className="font-mono text-[9px] text-[#a1a1aa] truncate">
                        Administrator
                      </span>
                    </div>
                    <ChevronsUpDown className="w-4 h-4 text-[#4A4A4A] flex-shrink-0 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-56 bg-[#0A0A0A] border-[#1A1A1A] font-mono"
                  side="top"
                  align="start"
                  sideOffset={4}
                >
                  <DropdownMenuLabel className="text-[#a1a1aa] text-xs font-normal">
                    <div className="flex flex-col gap-1">
                      <span className="text-[#fafafa] font-medium">
                        {displayName}
                      </span>
                      <span className="text-[#a1a1aa] text-[10px]">
                        {user?.email || 'Not signed in'}
                      </span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-[#1A1A1A]" />
                  <DropdownMenuItem
                    asChild
                    className="hover:bg-[#1A1A1A] focus:bg-[#1A1A1A] cursor-pointer"
                  >
                    <Link
                      href="/settings"
                      className="flex items-center gap-2 text-[#a1a1aa] hover:text-[#fafafa]"
                    >
                      <Settings className="w-4 h-4" />
                      Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    asChild
                    className="hover:bg-[#1A1A1A] focus:bg-[#1A1A1A] cursor-pointer"
                  >
                    <Link
                      href="/notifications"
                      className="flex items-center gap-2 text-[#a1a1aa] hover:text-[#fafafa]"
                    >
                      <Bell className="w-4 h-4" />
                      Notifications
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    asChild
                    className="hover:bg-[#1A1A1A] focus:bg-[#1A1A1A] cursor-pointer"
                  >
                    <Link
                      href="/help"
                      className="flex items-center gap-2 text-[#a1a1aa] hover:text-[#fafafa]"
                    >
                      <HelpCircle className="w-4 h-4" />
                      Help Center
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-[#1A1A1A]" />
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
                className="bg-[#0A0A0A] text-[#fafafa] border-t border-[#1A1A1A] hover:bg-[#1A1A1A] rounded-none h-auto px-5 py-4 group-data-[collapsible=icon]:!w-9 group-data-[collapsible=icon]:!h-9 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:rounded-md group-data-[collapsible=icon]:border-t-0"
              >
                <Link
                  href="/login"
                  className="flex items-center gap-3 group-data-[collapsible=icon]:justify-center"
                >
                  <LogOut className="w-4 h-4 text-[#00FF88]" />
                  <span className="font-mono text-[11px] group-data-[collapsible=icon]:hidden">
                    Sign In
                  </span>
                </Link>
              </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail className="hover:after:bg-[#00FF88]/30" />
    </Sidebar>
  );
}
