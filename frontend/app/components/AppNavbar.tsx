'use client';

import { useAuth } from '@/hooks/useAuth';
import { Navbar02 } from '@/components/ui/shadcn-io/navbar-02';
import { useRouter } from 'next/navigation';
import { 
  Home,
  Search, 
  MessageSquare, 
  FileText, 
  LayoutGrid,
  BarChart
} from 'lucide-react';

export function AppNavbar() {
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();

  const navLinks = [
    { href: '/', label: 'Home' },
    {
      label: 'Features',
      submenu: true,
      type: 'icon' as const,
      items: [
        { 
          href: '/search', 
          label: 'Semantic Search', 
          icon: 'BookOpenIcon', 
          description: 'Find information across documents using AI-powered vector search.' 
        },
        { 
          href: '/llm-chat', 
          label: 'AI Chat Assistant', 
          icon: 'LifeBuoyIcon', 
          description: 'Chat with your documents using local LLMs like Llama 3.2.' 
        },
        { 
          href: '/documents', 
          label: 'Knowledge Graph', 
          icon: 'InfoIcon', 
          description: 'Visualize connections and entities within your knowledge base.' 
        },
      ],
    }
  ];

  return (
    <Navbar02 
      logo={
        <div className="flex items-center gap-2 font-bold text-xl">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground shadow-sm">
            R
          </div>
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/80">
            RAG System
          </span>
        </div>
      }
      logoHref="/"
      ctaText={isAuthenticated ? "Dashboard" : "Get Started"}
      ctaHref={isAuthenticated ? "/documents" : "/register"}
      signInText={isAuthenticated ? "Sign Out" : "Login"}
      signInHref={isAuthenticated ? "#" : "/login"}
      onSignInClick={isAuthenticated ? logout : () => router.push('/login')}
      onCtaClick={() => router.push(isAuthenticated ? '/documents' : '/register')}
      navigationLinks={navLinks}
    />
  );
}
