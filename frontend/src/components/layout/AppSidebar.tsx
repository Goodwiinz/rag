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
} from 'lucide-react';

// Navigation items organized by groups
const mainNavItems = [
  { title: 'Dashboard', url: '/dashboard', icon: Home },
  { title: 'Search', url: '/search', icon: Search },
  { title: 'AI Chat', url: '/chat', icon: Bot },
];

const documentsNavItems = [
  { title: 'Upload', url: '/documents/upload', icon: Upload },
  { title: 'My Documents', url: '/documents', icon: FolderOpen },
  { title: 'ArXiv Papers', url: '/arxiv', icon: Database },
];

const analyticsNavItems = [
  { title: 'Dashboard', url: '/dashboard', icon: BarChart3 },
  { title: 'Real-time', url: '/realtime', icon: Zap },
];

const settingsNavItems = [
  { title: 'Settings', url: '/settings', icon: Settings },
  { title: 'Team', url: '/team', icon: Users },
  { title: 'API Keys', url: '/secrets', icon: Key },
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

  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-[#00ff9f]/10 !bg-[#0a0a0f]"
    >
      {/* Header with Logo */}
      <SidebarHeader className="border-b border-[#00ff9f]/10 !bg-[#0a0a0f] px-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              asChild
              className="hover:!bg-[#00ff9f]/10 data-[active=true]:!bg-[#00ff9f]/10"
            >
              <Link href="/" className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded border border-[#00ff9f]/30 bg-[#00ff9f]/10 shadow-lg shadow-[#00ff9f]/10">
                  <Terminal className="w-4 h-4 text-[#00ff9f]" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
                  <span className="font-mono font-semibold text-white/90">RAG System</span>
                  <span className="text-[10px] font-mono text-[#00ff9f]/70">
                    Terminal Observatory
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="!bg-[#0a0a0f] px-2">
        {/* Main Navigation */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-[#00ff9f]/50 px-2">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNavItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.url)}
                    tooltip={item.title}
                    className={cn(
                      'font-mono text-sm transition-all rounded-md',
                      isActive(item.url)
                        ? '!bg-[#00ff9f]/15 !text-[#00ff9f] border-l-2 border-[#00ff9f]'
                        : 'text-white/60 hover:!text-white hover:!bg-white/5'
                    )}
                  >
                    <Link href={item.url}>
                      <item.icon className={cn(
                        'w-4 h-4',
                        isActive(item.url) ? 'text-[#00ff9f]' : 'text-white/50'
                      )} />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="!bg-white/5 mx-2" />

        {/* Documents */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-[#00ff9f]/50 px-2 flex items-center gap-1">
            <FileText className="w-3 h-3" />
            <span className="group-data-[collapsible=icon]:hidden">Documents</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {documentsNavItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.url)}
                    tooltip={item.title}
                    className={cn(
                      'font-mono text-sm transition-all rounded-md',
                      isActive(item.url)
                        ? '!bg-[#00ff9f]/15 !text-[#00ff9f] border-l-2 border-[#00ff9f]'
                        : 'text-white/60 hover:!text-white hover:!bg-white/5'
                    )}
                  >
                    <Link href={item.url}>
                      <item.icon className={cn(
                        'w-4 h-4',
                        isActive(item.url) ? 'text-[#00ff9f]' : 'text-white/50'
                      )} />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="!bg-white/5 mx-2" />

        {/* Analytics */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-[#00ff9f]/50 px-2 flex items-center gap-1">
            <Activity className="w-3 h-3" />
            <span className="group-data-[collapsible=icon]:hidden">Analytics</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {analyticsNavItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.url)}
                    tooltip={item.title}
                    className={cn(
                      'font-mono text-sm transition-all rounded-md',
                      isActive(item.url)
                        ? '!bg-[#00ff9f]/15 !text-[#00ff9f] border-l-2 border-[#00ff9f]'
                        : 'text-white/60 hover:!text-white hover:!bg-white/5'
                    )}
                  >
                    <Link href={item.url}>
                      <item.icon className={cn(
                        'w-4 h-4',
                        isActive(item.url) ? 'text-[#00ff9f]' : 'text-white/50'
                      )} />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="!bg-white/5 mx-2" />

        {/* Settings */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-[#00ff9f]/50 px-2 flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            <span className="group-data-[collapsible=icon]:hidden">Configuration</span>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {settingsNavItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.url)}
                    tooltip={item.title}
                    className={cn(
                      'font-mono text-sm transition-all rounded-md',
                      isActive(item.url)
                        ? '!bg-[#00ff9f]/15 !text-[#00ff9f] border-l-2 border-[#00ff9f]'
                        : 'text-white/60 hover:!text-white hover:!bg-white/5'
                    )}
                  >
                    <Link href={item.url}>
                      <item.icon className={cn(
                        'w-4 h-4',
                        isActive(item.url) ? 'text-[#00ff9f]' : 'text-white/50'
                      )} />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer with User Menu */}
      <SidebarFooter className="border-t border-[#00ff9f]/10 !bg-[#0a0a0f] px-2">
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
