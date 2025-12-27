'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Home,
  Search,
  Bot,
  FileText,
  Database,
  BarChart3,
  Settings,
  HelpCircle,
  LogOut,
  Terminal,
  ChevronUp,
  Sparkles,
  Upload,
  FolderOpen,
  Activity,
  Zap,
  BookOpen,
  Bell,
  Shield,
  Users,
  CreditCard,
  Key,
  MessageSquare,
  LayoutDashboard,
  Files,
  FlaskConical,
  Cog,
} from 'lucide-react';

// Navigation items organized by groups - cleaner structure
const mainNavItems = [
  { title: 'Dashboard', url: '/dashboard', icon: LayoutDashboard, description: 'Overview & stats' },
  { title: 'AI Chat', url: '/chat', icon: MessageSquare, description: 'Chat with AI' },
  { title: 'Search', url: '/search', icon: Search, description: 'Search documents' },
];

const documentsNavItems = [
  { title: 'All Documents', url: '/documents', icon: Files, description: 'Browse files' },
  { title: 'Upload', url: '/documents/upload', icon: Upload, description: 'Add new files' },
  { title: 'ArXiv Papers', url: '/arxiv', icon: FlaskConical, description: 'Research papers' },
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

  // Reusable NavItem component for cleaner code
  const NavItem = ({ item }: { item: { title: string; url: string; icon: any; description?: string } }) => {
    const active = isActive(item.url);
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          asChild
          isActive={active}
          tooltip={item.title}
          className={cn(
            'font-mono text-sm transition-all duration-200 rounded-lg relative group/item h-10',
            active
              ? '!bg-[#00ff9f]/10 !text-[#00ff9f]'
              : 'text-white/60 hover:!text-white hover:!bg-white/5'
          )}
        >
          <Link href={item.url} className="flex items-center gap-3 px-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
            {/* Active indicator - only show in expanded mode */}
            {active && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[#00ff9f] group-data-[collapsible=icon]:hidden" />
            )}
            <item.icon className={cn(
              'w-5 h-5 flex-shrink-0 transition-all duration-200',
              active ? 'text-[#00ff9f]' : 'text-white/50 group-hover/item:text-white/70'
            )} />
            <span className="truncate group-data-[collapsible=icon]:hidden">{item.title}</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  };

  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-[#00ff9f]/10 !bg-[#0a0a0f]"
    >
      {/* Header with Logo - Cleaner design */}
      <SidebarHeader className="border-b border-[#00ff9f]/10 !bg-[#0a0a0f] p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              asChild
              tooltip="RAG System"
              className="hover:!bg-[#00ff9f]/10 data-[active=true]:!bg-[#00ff9f]/10 rounded-lg h-12"
            >
              <Link href="/dashboard" className="flex items-center gap-3 px-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg border border-[#00ff9f]/30 bg-gradient-to-br from-[#00ff9f]/20 to-[#00ff9f]/5 shadow-lg shadow-[#00ff9f]/10 flex-shrink-0">
                  <Terminal className="w-4 h-4 text-[#00ff9f]" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
                  <span className="font-mono font-bold text-white/95 text-sm">RAG System</span>
                  <span className="text-[9px] font-mono text-[#00ff9f]/60 uppercase tracking-wider">
                    v2.0
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="!bg-[#0a0a0f] py-3">
        {/* Main Navigation */}
        <SidebarGroup className="py-1 px-2 group-data-[collapsible=icon]:px-0">
          <SidebarGroupLabel className="text-[9px] font-mono uppercase tracking-widest text-white/30 px-1 mb-2 group-data-[collapsible=icon]:sr-only">
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

        <SidebarSeparator className="!bg-white/5 mx-3 my-3 group-data-[collapsible=icon]:mx-2" />

        {/* Documents */}
        <SidebarGroup className="py-1 px-2 group-data-[collapsible=icon]:px-0">
          <SidebarGroupLabel className="text-[9px] font-mono uppercase tracking-widest text-white/30 px-1 mb-2 group-data-[collapsible=icon]:sr-only">
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

        <SidebarSeparator className="!bg-white/5 mx-3 my-3 group-data-[collapsible=icon]:mx-2" />

        {/* System */}
        <SidebarGroup className="py-1 px-2 group-data-[collapsible=icon]:px-0">
          <SidebarGroupLabel className="text-[9px] font-mono uppercase tracking-widest text-white/30 px-1 mb-2 group-data-[collapsible=icon]:sr-only">
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

      {/* Footer with User Menu */}
      <SidebarFooter className="border-t border-[#00ff9f]/10 !bg-[#0a0a0f] p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    className="hover:!bg-white/5 data-[state=open]:!bg-white/5"
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded bg-gradient-to-br from-[#00ff9f]/20 to-[#00ff9f]/10 border border-[#00ff9f]/30">
                      <span className="text-xs font-mono font-medium text-[#00ff9f]">
                        {getInitials(user?.email)}
                      </span>
                    </div>
                    <div className="flex flex-col gap-0.5 leading-none text-left group-data-[collapsible=icon]:hidden">
                      <span className="font-mono text-sm text-white/80 truncate">
                        {displayName}
                      </span>
                      <span className="text-[10px] font-mono text-[#00ff9f]/70 truncate">
                        Administrator
                      </span>
                    </div>
                    <ChevronUp className="ml-auto w-4 h-4 text-white/40 group-data-[collapsible=icon]:hidden" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-56 bg-[#0d0d12] border-white/10 font-mono"
                  side="top"
                  align="start"
                  sideOffset={4}
                >
                  <DropdownMenuLabel className="text-white/60 text-xs font-normal">
                    <div className="flex flex-col gap-1">
                      <span className="text-white/80 font-medium">{displayName}</span>
                      <span className="text-white/40 text-[10px]">{displayEmail}</span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-white/10" />
                  <DropdownMenuItem asChild className="hover:!bg-white/5 focus:!bg-white/5 cursor-pointer">
                    <Link href="/settings" className="flex items-center gap-2 text-white/70 hover:text-white">
                      <Settings className="w-4 h-4" />
                      Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild className="hover:!bg-white/5 focus:!bg-white/5 cursor-pointer">
                    <Link href="/notifications" className="flex items-center gap-2 text-white/70 hover:text-white">
                      <Bell className="w-4 h-4" />
                      Notifications
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild className="hover:!bg-white/5 focus:!bg-white/5 cursor-pointer">
                    <Link href="/help" className="flex items-center gap-2 text-white/70 hover:text-white">
                      <HelpCircle className="w-4 h-4" />
                      Help Center
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-white/10" />
                  <DropdownMenuItem
                    onClick={handleLogout}
                    className="text-red-400 hover:!text-red-300 hover:!bg-red-500/10 focus:!bg-red-500/10 cursor-pointer"
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
                className="!bg-[#00ff9f]/10 !text-[#00ff9f] border border-[#00ff9f]/30 hover:!bg-[#00ff9f]/20"
              >
                <Link href="/login" className="flex items-center gap-2">
                  <LogOut className="w-4 h-4" />
                  <span className="font-mono group-data-[collapsible=icon]:hidden">Sign In</span>
                </Link>
              </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail className="hover:after:!bg-[#00ff9f]/30" />
    </Sidebar>
  );
}
