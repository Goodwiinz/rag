-- Sync existing users from public.users to auth.users
-- This creates Supabase Auth identities for existing users
-- Password hashes are compatible (both use bcrypt)
--
-- NOTE: GoTrue requires certain varchar columns to be empty strings (not NULL).
-- These include email_change, phone_change, phone_change_token, recovery_token,
-- reauthentication_token, email_change_token_new, email_change_token_current.
-- The phone column must remain NULL due to a unique constraint.

INSERT INTO auth.users (
  id,
  instance_id,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  role,
  created_at,
  updated_at,
  confirmation_token,
  aud,
  email_change,
  email_change_token_new,
  email_change_token_current,
  email_change_confirm_status,
  phone_change,
  phone_change_token,
  recovery_token,
  reauthentication_token,
  is_sso_user,
  is_anonymous
)
SELECT
  u.id,
  '00000000-0000-0000-0000-000000000000'::uuid,
  u.email,
  u.password_hash,
  now(),
  jsonb_build_object('provider', 'email', 'providers', ARRAY['email'], 'role', u.role),
  jsonb_build_object('first_name', u.first_name, 'last_name', u.last_name),
  'authenticated',
  u.created_at,
  u.updated_at,
  '',
  'authenticated',
  '',   -- email_change
  '',   -- email_change_token_new
  '',   -- email_change_token_current
  0,    -- email_change_confirm_status
  '',   -- phone_change
  '',   -- phone_change_token
  '',   -- recovery_token
  '',   -- reauthentication_token
  false, -- is_sso_user
  false  -- is_anonymous
FROM public.users u
WHERE NOT EXISTS (
  SELECT 1 FROM auth.users au WHERE au.id = u.id
);

-- Create identities for each user
INSERT INTO auth.identities (
  id,
  user_id,
  identity_data,
  provider,
  provider_id,
  last_sign_in_at,
  created_at,
  updated_at
)
SELECT
  u.id,
  u.id,
  jsonb_build_object('sub', u.id::text, 'email', u.email),
  'email',
  u.id::text,
  u.last_login,
  u.created_at,
  u.updated_at
FROM public.users u
WHERE NOT EXISTS (
  SELECT 1 FROM auth.identities ai WHERE ai.user_id = u.id
);
