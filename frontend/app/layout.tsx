import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'react-hot-toast';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Multimodal Enterprise RAG System',
  description: 'Advanced Retrieval-Augmented Generation system with multimodal document processing and knowledge graph capabilities',
  keywords: ['RAG', 'Knowledge Graph', 'Document Processing', 'AI', 'Multimodal', 'Enterprise'],
  authors: [{ name: 'RAG Development Team' }],
  creator: 'RAG System',
  publisher: 'Enterprise AI Solutions',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    title: 'Multimodal Enterprise RAG System',
    description: 'Advanced document processing with AI-powered search and knowledge graph visualization',
    type: 'website',
    locale: 'en_US',
    siteName: 'RAG System',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Multimodal Enterprise RAG System',
    description: 'Advanced document processing with AI-powered search',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <div className="min-h-screen bg-background text-foreground">
          <main className="flex-1">
            {children}
          </main>
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: 'hsl(var(--card))',
                color: 'hsl(var(--card-foreground))',
                border: '1px solid hsl(var(--border))',
              },
            }}
          />
        </div>
      </body>
    </html>
  );
}