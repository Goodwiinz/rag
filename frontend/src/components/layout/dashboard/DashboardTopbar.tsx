'use client';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { Book, ChevronRight, HelpCircle, User as UserIcon } from 'lucide-react';
import { usePathname } from 'next/navigation';

export function DashboardTopbar() {
  const pathname = usePathname();
  const { user } = useAuth();

  const getBreadcrumbs = () => {
    if (pathname?.startsWith('/chat')) return ['Goodwiinz', 'Chat Assistant'];
    if (pathname?.startsWith('/documents/upload')) return ['Goodwiinz', 'Documents'];
    if (pathname?.startsWith('/search')) return ['Goodwiinz', 'Semantic Search'];
    if (pathname?.startsWith('/settings')) return ['Goodwiinz', 'Settings'];
    return ['Goodwiinz', 'Dashboard'];
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="h-16 border-b border-[#27272A] bg-[#0E1015]/80 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-20 ml-64 transition-all duration-300">
      
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500 font-medium">{breadcrumbs[0]}</span>
        <ChevronRight className="w-4 h-4 text-gray-700" />
        <span className="text-white font-medium">{breadcrumbs[1]}</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-white/5 hidden md:flex gap-2 h-8 border border-[#27272A] rounded-full px-4">
          Feedback
        </Button>

        <div className="h-4 w-[1px] bg-[#27272A] mx-1 hidden md:block"></div>

        <a href="#" className="flex items-center text-sm text-gray-400 hover:text-white gap-1.5 transition-colors">
          <Book className="w-4 h-4" />
          <span className="hidden sm:inline">Docs</span>
        </a>

        <a href="#" className="flex items-center text-sm text-gray-400 hover:text-white gap-1.5 transition-colors mr-2">
          <HelpCircle className="w-4 h-4" />
          <span className="hidden sm:inline">Support</span>
        </a>

        <div className="ml-2 flex items-center gap-3 pl-4 border-l border-[#27272A]">
            <div className="flex flex-col items-end mr-1">
                <span className="text-xs font-medium text-white leading-none">{user?.email?.split('@')[0] || 'User'}</span>
                <span className="text-[10px] text-gray-500 leading-none mt-1">Admin</span>
            </div>
            <div className="h-8 w-8 rounded-full bg-[#27272A] border border-gray-700 flex items-center justify-center text-gray-300 hover:border-gray-500 cursor-pointer transition">
                <UserIcon className="w-4 h-4" />
            </div>
        </div>
      </div>
    </header>
  );
}
