import type { Metadata } from 'next';
import { Inter, JetBrains_Mono, Outfit } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';
import { SkipLink } from '@/components/ui/skip-link';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });
const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
});
const outfit = Outfit({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['300', '400', '500', '600', '700', '800'],
});

export const metadata: Metadata = {
  title: 'RAG System | Terminal Observatory',
  description: 'Advanced Retrieval-Augmented Generation system with multimodal document processing and knowledge graph capabilities',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable} ${outfit.variable} bg-[var(--terminal-bg)]`}>
      <body className={`${inter.className} antialiased bg-[var(--terminal-bg)] text-[var(--terminal-text)]`} suppressHydrationWarning>
        <SkipLink />
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}