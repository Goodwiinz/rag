'use client';

import { useAuth } from '@/hooks/useAuth';
import {
    BarChart3,
    ChevronUp,
    CreditCard,
    FileText,
    Folder,
    Key,
    LayoutDashboard,
    LogOut,
    MessageSquare,
    Search,
    Settings,
    Sparkles,
    User2,
    Users,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
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
} from '@/components/ui/sidebar';

const projectItems = [
  { title: 'Dashboard', url: '/dashboard', icon: LayoutDashboard },
  { title: 'Chat Assistant', url: '/llm-chat', icon: MessageSquare },
  { title: 'Tambo Chat', url: '/tambo-chat', icon: Sparkles },
  { title: 'Documents', url: '/documents/upload', icon: FileText },
  { title: 'Semantic Search', url: '/search', icon: Search },
  { title: 'Analytics', url: '/analytics', icon: BarChart3 },
];

const orgItems = [
  { title: 'Settings', url: '/settings', icon: Settings },
  { title: 'Team', url: '/team', icon: Users },
  { title: 'Billing', url: '/billing', icon: CreditCard },
  { title: 'Model Secrets', url: '/secrets', icon: Key },
];

interface AppSidebarProps {
  sidebarState?: 'expanded' | 'collapsed' | 'mini';
}

export function AppSidebar({ sidebarState = 'expanded' }: AppSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const displayName = user?.email?.split('@')[0] || 'Account';
  const displayEmail = user?.email || 'Not signed in';

  return (
    <Sidebar
      className={cn(
        "transition-all duration-300",
        sidebarState === 'collapsed' && 'w-0 overflow-hidden',
        sidebarState === 'mini' && 'w-16'
      )}
    >
      {sidebarState !== 'collapsed' && (
        <>
          <SidebarHeader
            className={cn(
              sidebarState === 'mini' && 'px-2'
            )}
          >
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size={sidebarState === 'mini' ? 'default' : 'lg'}
              asChild
              tooltip={sidebarState === 'mini' ? 'RAG System' : undefined}
            >
              <Link href="/dashboard">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 shadow-lg shadow-amber-500/25">
                  <Folder className="size-4 text-white" />
                </div>
                {sidebarState !== 'mini' && (
                  <div className="flex flex-col gap-0.5 leading-none">
                    <span className="font-semibold">RAG System</span>
                    <span className="text-xs text-muted-foreground">Enterprise</span>
                  </div>
                )}
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className={cn(sidebarState === 'mini' && 'px-2')}>
        <SidebarGroup>
          {sidebarState !== 'mini' && <SidebarGroupLabel>Project</SidebarGroupLabel>}
          <SidebarGroupContent>
            <SidebarMenu>
              {projectItems.map((item) => {
                const isActive = pathname === item.url || pathname?.startsWith(item.url + '/');
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={sidebarState === 'mini' ? item.title : undefined}
                    >
                      <Link href={item.url}>
                        <item.icon className="size-4" />
                        {sidebarState !== 'mini' && <span>{item.title}</span>}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          {sidebarState !== 'mini' && <SidebarGroupLabel>Organization</SidebarGroupLabel>}
          <SidebarGroupContent>
            <SidebarMenu>
              {orgItems.map((item) => {
                const isActive = pathname === item.url;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={sidebarState === 'mini' ? item.title : undefined}
                    >
                      <Link href={item.url}>
                        <item.icon className="size-4" />
                        {sidebarState !== 'mini' && <span>{item.title}</span>}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {sidebarState !== 'mini' && (
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                  >
                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500/20 to-orange-500/20 text-amber-600">
                      <User2 className="size-4" />
                    </div>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-semibold">{displayName}</span>
                      <span className="truncate text-xs text-muted-foreground">{displayEmail}</span>
                    </div>
                    <ChevronUp className="ml-auto size-4" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
                  side="top"
                  align="end"
                  sideOffset={4}
                >
                  <DropdownMenuItem asChild>
                    <Link href="/profile">
                      <User2 className="mr-2 size-4" />
                      Profile
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/settings">
                      <Settings className="mr-2 size-4" />
                      Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                    <LogOut className="mr-2 size-4" />
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      )}
      <SidebarRail />
    </>
    </Sidebar>
  );
}
