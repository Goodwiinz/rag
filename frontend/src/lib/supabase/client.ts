import { createBrowserClient } from '@supabase/ssr';
import type { SupabaseClient } from '@supabase/supabase-js';

let _client: SupabaseClient | null = null;

function getMissingBrowserConfigKeys(): string[] {
  return [
    process.env.NEXT_PUBLIC_SUPABASE_URL
      ? null
      : 'NEXT_PUBLIC_SUPABASE_URL',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
      ? null
      : 'NEXT_PUBLIC_SUPABASE_ANON_KEY',
  ].filter((value): value is string => value !== null);
}

function getBrowserConfig(): {
  supabaseUrl: string;
  supabaseAnonKey: string;
} {
  const missingKeys = getMissingBrowserConfigKeys();

  if (missingKeys.length > 0) {
    throw new Error(
      `Supabase browser auth is not configured. ${missingKeys.join(
        ' and '
      )} must be defined at build time for the frontend bundle.`
    );
  }

  return {
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL as string,
    supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY as string,
  };
}

/**
 * Create or return a cached Supabase browser client (SSR-compatible).
 * Uses @supabase/ssr for automatic cookie-based session management.
 */
export function createClient(): SupabaseClient {
  if (_client) return _client;

  const { supabaseUrl, supabaseAnonKey } = getBrowserConfig();

  _client = createBrowserClient(supabaseUrl, supabaseAnonKey);
  return _client;
}
