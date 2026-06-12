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
  style: ['normal', 'italic'],
  axes: ['opsz'],
});

export const metadata: Metadata = {
  title: 'NOUS | Multimodal Intelligence',
  description:
    'NOUS — Multimodal intelligence platform for research, document processing, and knowledge graph capabilities',
};

/**
 * Force dynamic rendering app-wide.
 *
 * proxy.ts (#699) sets a per-request CSP `script-src 'self' 'nonce-…'
 * 'strict-dynamic'` with no `unsafe-inline`. Next only stamps that per-request
 * nonce onto its inline bootstrap scripts when a route renders dynamically; a
 * statically prerendered page's scripts carry no matching nonce, so
 * strict-dynamic blocks every script and the page renders blank (login,
 * register, home and the other auth pages were all statically optimized).
 * A nonce-based CSP is incompatible with static prerendering, so the app must
 * render dynamically for the nonce to apply.
 */
export const dynamic = 'force-dynamic';

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
      <head>
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, viewport-fit=cover"
        />
      </head>
      <body
        className={`${inter.className} antialiased bg-background text-foreground`}
        suppressHydrationWarning
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
