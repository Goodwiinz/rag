import { createClient } from '@supabase/supabase-js';

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://localhost:54321';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || (process.env.NODE_ENV === 'test' ? 'mock-key-for-tests' : '');

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
