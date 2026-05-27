# Confirmation System Overhaul — Design Spec

**Date**: 2026-05-20
**Status**: Approved
**Approach**: Supabase-native (custom template + SMTP + frontend UX)

## Overview

Replace the generic Supabase confirmation email and static pending screen with a fully branded NOUS experience: custom HTML email template, custom SMTP sender, improved post-signup UX with resend/retry, and a verify-email page that handles PKCE token exchange with proper loading/error states.

## 1. Custom Branded Email Template

**File**: `supabase/templates/confirmation.html`

HTML email using inline styles (email client compatibility). Design:

- Background: `#0A0A0E` (Erebus)
- Text: `#F7F7F5` (Selene)
- Accent/CTA: `#D4A039` (Sol)
- Font: system monospace stack (`ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace`)
- Layout: centered single-column, max-width 480px

Content structure:
1. NOUS wordmark (text-based, no image dependency)
2. "Confirm Your Identity" heading
3. Brief copy: "Click below to verify your email and activate your NOUS account."
4. CTA button: "VERIFY IDENTITY" linking to `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup`
5. Fallback: plain-text URL below the button
6. Footer: "You received this because you signed up for NOUS." + muted timestamp

**Config changes** (`supabase/config.toml`):
```toml
[auth.email.template.confirmation]
subject = "NOUS — Confirm Your Identity"
content_path = "./supabase/templates/confirmation.html"
```

**Hosted project**: paste the same template HTML into the Supabase dashboard under Authentication > Email Templates > Confirm signup.

## 2. Custom SMTP Configuration

**Local** (`supabase/config.toml`):
```toml
[auth.email.smtp]
enabled = true
host = "smtp.sendgrid.net"
port = 587
user = "apikey"
pass = "env(SENDGRID_API_KEY)"
admin_email = "noreply@gen-text.app"
sender_name = "NOUS"
```

**Hosted project**: configure in Supabase dashboard under Authentication > SMTP Settings with the same SendGrid credentials.

Note: SMTP configuration requires a verified SendGrid sender for `noreply@gen-text.app`. If SendGrid is not yet set up, the template and UX improvements can ship independently — Supabase's default mailer will use the custom template.

## 3. Frontend — Pending Confirmation Screen

**File**: `frontend/app/(auth)/register/page.tsx` (lines 139-171, the `pendingEmailConfirmation` block)

Replace the static screen with an interactive component. Extract to `frontend/src/components/auth/PendingEmailConfirmation.tsx` for reuse.

**Props**: `email: string`, `onReset: () => void`

**Features**:
- Animated mail icon (subtle pulse via framer-motion)
- "We sent a verification link to {email}" message
- **Resend button**: calls `supabase.auth.resend({ type: 'signup', email })`, 60-second cooldown with visible countdown, shows success/error toast
- **"Wrong email?"** link: calls `onReset()` which clears `pendingEmailConfirmation` state and resets the form
- **Spam folder hint**: appears after 30 seconds via setTimeout, fades in with "Check your spam or junk folder"
- **"Return to Access Terminal"** link to `/login`

State:
- `resendCooldown: number` (seconds remaining, 0 = can resend)
- `resendStatus: 'idle' | 'sending' | 'sent' | 'error'`
- `showSpamHint: boolean`

## 4. Frontend — Verify Email Page

**File**: `frontend/app/(auth)/verify-email/page.tsx`

Replace the current auto-redirect page with a page that handles PKCE token exchange.

**Flow**:
1. On mount, read `token_hash` and `type` from URL search params
2. If params present: call `supabase.auth.verifyOtp({ token_hash, type })` 
3. Show loading state ("Verifying your identity...")
4. On success: show "Identity Verified" with checkmark animation, progress bar, auto-redirect to `/login` after 4 seconds (same as current)
5. On error: show error state with message, "Resend Verification" button (calls `resend`), and "Return to Register" link
6. If no params (direct navigation): show the current success state (backwards compatible with the existing redirect-based flow)

State:
- `status: 'verifying' | 'success' | 'error'`
- `errorMessage: string | null`

## 5. Auth Callback Route Update

**File**: `frontend/app/auth/callback/route.ts`

No structural changes needed beyond the X-Forwarded-Host fix already shipped. The PKCE flow uses `/auth/confirm` (handled by Supabase client-side), not `/auth/callback`. The callback route continues to handle the code-exchange flow for OAuth and magic links.

## Files Changed

| File | Change |
|------|--------|
| `supabase/templates/confirmation.html` | New — branded email template |
| `supabase/config.toml` | Add template reference, uncomment SMTP |
| `frontend/src/components/auth/PendingEmailConfirmation.tsx` | New — extracted pending confirmation component |
| `frontend/app/(auth)/register/page.tsx` | Use PendingEmailConfirmation component |
| `frontend/app/(auth)/verify-email/page.tsx` | Add PKCE verification, loading/error states |

## Out of Scope

- Email analytics/tracking
- Custom email for password reset, invite, or email change (can follow same pattern later)
- SMS/phone verification
- CAPTCHA on signup
