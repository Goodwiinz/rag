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
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
} from '@/components/ui/sidebar';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import {
  Activity,
  Bell,
  ChevronUp,
  Cog,
  Files,
  FlaskConical,
  FolderKanban,
  HelpCircle,
  Key,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Search,
  Settings,
  Terminal,
  Upload
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

// Navigation items organized by groups - cleaner structure
const mainNavItems = [
  { title: 'Dashboard', url: '/dashboard', icon: LayoutDashboard, description: 'Overview & stats' },
  { title: 'AI Chat', url: '/chat', icon: MessageSquare, description: 'Chat with AI' },
  { title: 'Search', url: '/search', icon: Search, description: 'Search documents' },
];

const documentsNavItems = [
  { title: 'All Documents', url: '/documents', icon: Files, description: 'Browse files' },
  { title: 'Upload', url: '/documents/upload', icon: Upload, description: 'Add new files' },
  { title: 'Entities', url: '/entities', icon: Terminal, description: 'Knowledge nodes' },
  { title: 'ArXiv Papers', url: '/arxiv', icon: FlaskConical, description: 'Research papers' },
  { title: 'Projects', url: '/projects', icon: FolderKanban, description: 'Research projects' },
];

const systemNavItems = [
  { title: 'Real-time', url: '/realtime', icon: Activity, description: 'Live metrics' },
  { title: 'Settings', url: '/settings', icon: Cog, description: 'Preferences' },
  { title: 'API Keys', url: '/secrets', icon: Key, description: 'Credentials' },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();

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
  const displayEmail = user?.email || 'Not signed in';

  // Reusable NavItem component for cleaner code - Terminal Observatory Theme
  // Using centralized CSS variables from @/theme/constants
  const NavItem = ({ item }: { item: { title: string; url: string; icon: any; description?: string } }) => {
    const active = isActive(item.url);
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          asChild
          isActive={active}
          tooltip={item.title}
          className={cn(
            'font-mono text-sm transition-all duration-200 rounded-lg relative group/item h-10 border group-data-[collapsible=icon]:!size-10 group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:mx-auto',
            active
              ? '!bg-[var(--terminal-elevated)] !border-[var(--terminal-border)] !text-[var(--phosphor-green)] font-medium shadow-[0_0_15px_-5px_rgba(0,0,0,0.3)]'
              : 'border-transparent text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)]'
          )}
        >
          <Link href={item.url} className="flex items-center gap-3 px-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 w-full">
            {/* Active indicator - consistent with ConversationItem */}
            {active && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 rounded-r-full bg-[var(--phosphor-green)] shadow-[0_0_8px_var(--phosphor-green)] transition-opacity duration-200" />
            )}

            {/* Icon Box - matches ConversationItem style */}
            <div className={cn(
              "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 transition-all duration-200",
              active
                ? "bg-[var(--phosphor-green)]/10 !text-[var(--phosphor-green)] shadow-[0_0_10px_var(--phosphor-green-glow)]"
                : "text-[var(--terminal-text-subtle)] group-hover/item:text-[var(--terminal-text-muted)] group-hover:bg-[var(--terminal-elevated)]"
            )}>
              <item.icon className="w-3.5 h-3.5" />
            </div>

            <span className={cn(
              "truncate group-data-[collapsible=icon]:hidden",
              active ? "!text-[var(--phosphor-green)]" : ""
            )}>{item.title}</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  };

  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-[var(--terminal-border)]"
    >
      {/* Header with Logo - Terminal Observatory Theme */}
      <SidebarHeader className="border-b border-[var(--terminal-border)] p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              asChild
              tooltip="RAG System"
              className="hover:bg-[var(--terminal-elevated)] data-[active=true]:bg-[var(--terminal-elevated)] rounded-lg h-12"
            >
              <Link href="/dashboard" className="flex items-center gap-3 px-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg flex-shrink-0">
                  <Terminal className="w-4 h-4 text-[var(--phosphor-green)]" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
                  <span className="font-mono font-bold text-[var(--terminal-text)] text-sm">RAG System</span>
                  <span className="text-[9px] font-mono text-[var(--phosphor-green)]/60 uppercase tracking-wider">
                    v2.0
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="py-3">
        {/* Main Navigation */}
        <SidebarGroup className="py-1 px-2 group-data-[collapsible=icon]:px-0">
          <SidebarGroupLabel className="text-[9px] font-mono uppercase tracking-widest text-[var(--terminal-text-muted)] px-1 mb-2 group-data-[collapsible=icon]:sr-only">
            Main
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {mainNavItems.map((item) => (
                <NavItem key={item.title} item={item} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="!bg-[var(--terminal-border)] mx-3 my-3 group-data-[collapsible=icon]:mx-2" />

        {/* Documents */}
        <SidebarGroup className="py-1 px-2 group-data-[collapsible=icon]:px-0">
          <SidebarGroupLabel className="text-[9px] font-mono uppercase tracking-widest text-[var(--terminal-text-muted)] px-1 mb-2 group-data-[collapsible=icon]:sr-only">
            Documents
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {documentsNavItems.map((item) => (
                <NavItem key={item.title} item={item} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="!bg-[var(--terminal-border)] mx-3 my-3 group-data-[collapsible=icon]:mx-2" />

        {/* System */}
        <SidebarGroup className="py-1 px-2 group-data-[collapsible=icon]:px-0">
          <SidebarGroupLabel className="text-[9px] font-mono uppercase tracking-widest text-[var(--terminal-text-muted)] px-1 mb-2 group-data-[collapsible=icon]:sr-only">
            System
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {systemNavItems.map((item) => (
                <NavItem key={item.title} item={item} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer with User Menu - Terminal Observatory Theme */}
      <SidebarFooter className="border-t border-[var(--terminal-border)] p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    className="hover:bg-[var(--terminal-elevated)] data-[state=open]:bg-[var(--terminal-elevated)]"
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded bg-gradient-to-br from-[var(--phosphor-green)]/20 to-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30">
                      <span className="text-xs font-mono font-medium text-[var(--phosphor-green)]">
                        {getInitials(user?.email)}
                      </span>
                    </div>
                    <div className="flex flex-col gap-0.5 leading-none text-left group-data-[collapsible=icon]:hidden">
                      <span className="font-mono text-sm text-[var(--terminal-text)] truncate">
                        {displayName}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--phosphor-green)]/70 truncate">
                        Administrator
                      </span>
                    </div>
                    <ChevronUp className="ml-auto w-4 h-4 text-[var(--terminal-text-muted)] group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-56 bg-[var(--terminal-surface)] border-[var(--terminal-border)] font-mono"
                  side="top"
                  align="start"
                  sideOffset={4}
                >
                  <DropdownMenuLabel className="text-[var(--terminal-text-dim)] text-xs font-normal">
                    <div className="flex flex-col gap-1">
                      <span className="text-[var(--terminal-text)] font-medium">{displayName}</span>
                      <span className="text-[var(--terminal-text-muted)] text-[10px]">{displayEmail}</span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-[var(--terminal-border)]" />
                  <DropdownMenuItem asChild className="hover:bg-[var(--terminal-elevated)] focus:bg-[var(--terminal-elevated)] cursor-pointer">
                    <Link href="/settings" className="flex items-center gap-2 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]">
                      <Settings className="w-4 h-4" />
                      Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild className="hover:bg-[var(--terminal-elevated)] focus:bg-[var(--terminal-elevated)] cursor-pointer">
                    <Link href="/notifications" className="flex items-center gap-2 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]">
                      <Bell className="w-4 h-4" />
                      Notifications
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild className="hover:bg-[var(--terminal-elevated)] focus:bg-[var(--terminal-elevated)] cursor-pointer">
                    <Link href="/help" className="flex items-center gap-2 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]">
                      <HelpCircle className="w-4 h-4" />
                      Help Center
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-[var(--terminal-border)]" />
                  <DropdownMenuItem
                    onClick={handleLogout}
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
                className="bg-[var(--terminal-surface)] text-[var(--terminal-text)] border border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]"
              >
                <Link href="/login" className="flex items-center gap-2">
                  <LogOut className="w-4 h-4 text-[var(--phosphor-green)]" />
                  <span className="font-mono group-data-[collapsible=icon]:hidden">Sign In</span>
                </Link>
              </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail className="hover:after:bg-[var(--phosphor-green)]/30" />
    </Sidebar>
  );
}
