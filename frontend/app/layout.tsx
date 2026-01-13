import { LayoutWrapper } from '@/components/layout/LayoutWrapper';
import type { Metadata } from 'next';
import { Inter, JetBrains_Mono, Outfit } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

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
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable} ${outfit.variable}`}>
      <body className={`${inter.className} antialiased`} suppressHydrationWarning>
        <Providers>
          <LayoutWrapper>
            {children}
          </LayoutWrapper>
        </Providers>
      </body>
    </html>
  );
}