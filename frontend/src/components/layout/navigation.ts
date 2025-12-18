import {
  BarChart3,
  ClipboardList,
  FileText,
  FlaskConical,
  HelpCircle,
  LayoutDashboard,
  LucideIcon,
  MessageSquare,
  Monitor,
  Network,
  Search,
  Settings,
  TrendingUp,
} from 'lucide-react';

export interface NavigationItem {
  name: string;
  href: string;
  icon: LucideIcon;
  badge?: number;
}

export interface NavigationGroup {
  name: string;
  items: NavigationItem[];
}

export const mainNavigation: NavigationItem[] = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Search', href: '/search', icon: Search },
  { name: 'LLM Chat', href: '/llm-chat', icon: MessageSquare },
  { name: 'Knowledge Graph', href: '/graph', icon: Network },
  { name: 'Analytics', href: '/analytics/overview', icon: BarChart3 },
  { name: 'Evaluations', href: '/evaluation', icon: ClipboardList },
  { name: 'A/B Testing', href: '/ab-testing', icon: FlaskConical },
  { name: 'Search Analytics', href: '/search-analytics', icon: TrendingUp },
  { name: 'Monitoring', href: '/monitoring', icon: Monitor },
];

export const bottomNavigation: NavigationItem[] = [
  { name: 'Help', href: '/help', icon: HelpCircle },
  { name: 'Settings', href: '/settings', icon: Settings },
];

// Legacy export for backwards compatibility
export const navigation: NavigationItem[] = [
  ...mainNavigation,
  ...bottomNavigation,
];
