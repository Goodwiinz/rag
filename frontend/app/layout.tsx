import type { Metadata } from 'next';
import {
  Inter,
  JetBrains_Mono,
  Outfit,
  Source_Serif_4,
} from 'next/font/google';
import './globals.css';
import './nous-tokens.css';
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
const sourceSerif4 = Source_Serif_4({
  subsets: ['latin'],
  variable: '--font-serif',
  weight: ['300', '400', '600'],
  style: ['normal', 'italic'],
});

export const metadata: Metadata = {
  title: 'NOUS | Multimodal Intelligence',
  description:
    'NOUS — Multimodal intelligence platform for research, document processing, and knowledge graph capabilities',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable} ${outfit.variable} ${sourceSerif4.variable}`}
    >
      <body
        className={`${inter.className} antialiased bg-background text-foreground`}
        suppressHydrationWarning
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
