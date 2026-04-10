import { createBrowserClient } from '@supabase/ssr';
import type { SupabaseClient } from '@supabase/supabase-js';

let _client: SupabaseClient | null = null;

/**
 * Create or return a cached Supabase browser client (SSR-compatible).
 * Uses @supabase/ssr for automatic cookie-based session management.
 */
export function createClient(): SupabaseClient {
  if (_client) return _client;

  const supabaseUrl =
    process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://localhost:54321';
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

  _client = createBrowserClient(supabaseUrl, supabaseAnonKey);
  return _client;
}
