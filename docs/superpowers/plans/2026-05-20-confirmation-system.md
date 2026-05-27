# Confirmation System Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic Supabase confirmation email and static pending screen with a fully branded NOUS experience — custom email template, custom SMTP, resend/retry UX, and PKCE-based verify-email page.

**Architecture:** Supabase-native approach. Custom HTML email template referenced in `config.toml`. Frontend gets two new/rewritten components: `PendingEmailConfirmation` (extracted from register page) and a rewritten `verify-email` page with PKCE token exchange. The Supabase browser client (`@/lib/supabase/client`) is used directly in components for `resend()` and `verifyOtp()` calls — no auth store changes needed.

**Tech Stack:** Supabase Auth (GoTrue), Next.js 15, React, framer-motion, Tailwind CSS, Zustand (existing auth store)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `supabase/templates/confirmation.html` | Create | Branded HTML email template |
| `supabase/config.toml` | Modify | Reference template, uncomment SMTP |
| `frontend/src/components/auth/PendingEmailConfirmation.tsx` | Create | Resend button, cooldown, spam hint, reset link |
| `frontend/app/(auth)/register/page.tsx` | Modify | Use PendingEmailConfirmation component |
| `frontend/app/(auth)/verify-email/page.tsx` | Rewrite | PKCE verification, loading/error/success states |

---

### Task 1: Create branded email template

**Files:**
- Create: `supabase/templates/confirmation.html`

- [ ] **Step 1: Create the templates directory and HTML file**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Confirm Your Identity — NOUS</title>
</head>
<body style="margin:0;padding:0;background-color:#0A0A0E;font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0A0A0E;padding:40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;">
          <!-- Wordmark -->
          <tr>
            <td style="padding:0 0 32px 0;text-align:center;">
              <span style="font-size:28px;font-weight:700;color:#F7F7F5;letter-spacing:0.15em;">NOUS</span>
            </td>
          </tr>
          <!-- Card -->
          <tr>
            <td style="background-color:#141418;border:1px solid #2a2a2e;border-radius:16px;padding:40px 32px;">
              <!-- Heading -->
              <h1 style="margin:0 0 16px 0;font-size:18px;font-weight:700;color:#F7F7F5;text-transform:uppercase;letter-spacing:0.15em;text-align:center;">
                Confirm Your Identity
              </h1>
              <!-- Copy -->
              <p style="margin:0 0 32px 0;font-size:13px;color:#a0a0a5;line-height:1.6;text-align:center;">
                Click below to verify your email and activate your NOUS account.
              </p>
              <!-- CTA Button -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center">
                    <a href="{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup"
                       style="display:inline-block;padding:14px 32px;background-color:#D4A039;color:#0A0A0E;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.2em;text-decoration:none;border-radius:8px;">
                      Verify Identity
                    </a>
                  </td>
                </tr>
              </table>
              <!-- Fallback URL -->
              <p style="margin:24px 0 0 0;font-size:10px;color:#666;text-align:center;word-break:break-all;">
                Or copy this link: {{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:24px 0 0 0;text-align:center;">
              <p style="margin:0;font-size:10px;color:#555;line-height:1.5;">
                You received this because you signed up for NOUS.<br />
                If you didn't request this, you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add supabase/templates/confirmation.html
git commit -m "feat(auth): add branded NOUS confirmation email template"
```

---

### Task 2: Update Supabase config for template and SMTP

**Files:**
- Modify: `supabase/config.toml:219-232`

- [ ] **Step 1: Uncomment and configure SMTP block**

Replace the commented SMTP block (lines 219-227) with:

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

- [ ] **Step 2: Add confirmation template reference**

Replace the commented template block (lines 229-232) with:

```toml
[auth.email.template.confirmation]
subject = "NOUS — Confirm Your Identity"
content_path = "./supabase/templates/confirmation.html"
```

- [ ] **Step 3: Commit**

```bash
git add supabase/config.toml
git commit -m "feat(auth): configure custom SMTP and confirmation email template"
```

---

### Task 3: Create PendingEmailConfirmation component

**Files:**
- Create: `frontend/src/components/auth/PendingEmailConfirmation.tsx`

- [ ] **Step 1: Create the component**

```tsx
'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { Mail, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

interface PendingEmailConfirmationProps {
  email: string;
  onReset: () => void;
}

export default function PendingEmailConfirmation({
  email,
  onReset,
}: PendingEmailConfirmationProps) {
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendStatus, setResendStatus] = useState<
    'idle' | 'sending' | 'sent' | 'error'
  >('idle');
  const [showSpamHint, setShowSpamHint] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowSpamHint(true), 30_000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const interval = setInterval(
      () => setResendCooldown((prev) => prev - 1),
      1000
    );
    return () => clearInterval(interval);
  }, [resendCooldown]);

  const handleResend = useCallback(async () => {
    if (resendCooldown > 0) return;
    setResendStatus('sending');
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.resend({
        type: 'signup',
        email,
      });
      if (error) throw error;
      setResendStatus('sent');
      setResendCooldown(60);
    } catch {
      setResendStatus('error');
    }
  }, [email, resendCooldown]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
          {/* Animated mail icon */}
          <motion.div
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6"
          >
            <Mail className="w-8 h-8 text-[var(--phosphor-green)]" />
          </motion.div>

          <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
            Verify Your Identity
          </h2>

          <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-8 leading-relaxed">
            We sent a verification link to{' '}
            <span className="text-[var(--phosphor-green)]">{email}</span>. Check
            your inbox and click the link to activate your account.
          </p>

          {/* Resend button */}
          <button
            onClick={handleResend}
            disabled={resendCooldown > 0 || resendStatus === 'sending'}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] font-mono text-xs font-bold uppercase tracking-[0.15em] text-[var(--terminal-text-muted)] hover:border-[var(--phosphor-green)]/50 hover:text-[var(--phosphor-green)] disabled:opacity-40 disabled:cursor-not-allowed transition-all mb-4"
          >
            {resendStatus === 'sending' ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Sending...
              </>
            ) : resendCooldown > 0 ? (
              <>Resend in {resendCooldown}s</>
            ) : (
              <>
                <RefreshCw className="w-3.5 h-3.5" />
                Resend Verification
              </>
            )}
          </button>

          {/* Resend status feedback */}
          {resendStatus === 'sent' && resendCooldown > 0 && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-[var(--phosphor-green)] mb-4"
            >
              Verification email sent!
            </motion.p>
          )}
          {resendStatus === 'error' && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-red-400 mb-4"
            >
              Failed to resend. Please try again.
            </motion.p>
          )}

          {/* Spam hint */}
          {showSpamHint && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-[var(--terminal-text-dim)] mb-6"
            >
              Not seeing it? Check your spam or junk folder.
            </motion.p>
          )}

          {/* Wrong email / back links */}
          <div className="flex flex-col items-center gap-3 pt-4 border-t border-[var(--terminal-border)]">
            <button
              onClick={onReset}
              className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
            >
              Wrong email? Try again
            </button>
            <Link
              href="/login"
              className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
            >
              Return to Access Terminal
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/auth/PendingEmailConfirmation.tsx
git commit -m "feat(auth): add PendingEmailConfirmation component with resend and cooldown"
```

---

### Task 4: Wire PendingEmailConfirmation into register page

**Files:**
- Modify: `frontend/app/(auth)/register/page.tsx:1-171`

- [ ] **Step 1: Add the import**

At the top of the file, add after the existing imports:

```tsx
import PendingEmailConfirmation from '@/components/auth/PendingEmailConfirmation';
```

- [ ] **Step 2: Add reset handler and replace the pendingEmailConfirmation block**

Inside `RegisterPage`, add a reset handler before the `return` statements:

```tsx
const handleResetConfirmation = () => {
  setFormData({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    organization_name: '',
  });
};
```

Note: `pendingEmailConfirmation` is from `useAuth()`. The `onReset` needs to also clear it. Since the auth store doesn't expose a setter, we use the store directly. Add this import at the top:

```tsx
import { useAuthStore } from '@/stores/authStore';
```

And update the handler:

```tsx
const handleResetConfirmation = () => {
  useAuthStore.setState({ pendingEmailConfirmation: false });
  setFormData({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    organization_name: '',
  });
};
```

- [ ] **Step 3: Replace the inline pending email block**

Replace lines 139-171 (the `if (pendingEmailConfirmation)` block) with:

```tsx
if (pendingEmailConfirmation) {
  return (
    <PendingEmailConfirmation
      email={formData.email}
      onReset={handleResetConfirmation}
    />
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(auth\)/register/page.tsx
git commit -m "feat(auth): wire PendingEmailConfirmation into register page"
```

---

### Task 5: Rewrite verify-email page with PKCE verification

**Files:**
- Rewrite: `frontend/app/(auth)/verify-email/page.tsx`

- [ ] **Step 1: Rewrite the verify-email page**

Replace the entire file with:

```tsx
'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useState } from 'react';

type VerifyStatus = 'verifying' | 'success' | 'error';

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<VerifyStatus>('verifying');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const tokenHash = searchParams.get('token_hash');
  const type = searchParams.get('type');

  useEffect(() => {
    if (!tokenHash || !type) {
      setStatus('success');
      return;
    }

    const verify = async () => {
      try {
        const supabase = createClient();
        const { error } = await supabase.auth.verifyOtp({
          token_hash: tokenHash,
          type: type as 'signup' | 'email',
        });
        if (error) throw error;
        setStatus('success');
      } catch (err) {
        setStatus('error');
        setErrorMessage(
          err instanceof Error ? err.message : 'Verification failed'
        );
      }
    };

    verify();
  }, [tokenHash, type]);

  useEffect(() => {
    if (status !== 'success') return;
    const timer = setTimeout(() => router.push('/login'), 4000);
    return () => clearTimeout(timer);
  }, [status, router]);

  const handleResend = useCallback(async () => {
    setErrorMessage('Please return to the registration page to resend.');
  }, []);

  if (status === 'verifying') {
    return (
      <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
        <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6">
          <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin" />
        </div>
        <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
          Verifying Identity
        </h2>
        <p className="text-sm font-mono text-[var(--terminal-text-muted)] leading-relaxed">
          Please wait while we confirm your email...
        </p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
        <div className="flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 mx-auto mb-6">
          <AlertCircle className="w-8 h-8 text-red-400" />
        </div>
        <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
          Verification Failed
        </h2>
        <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-6 leading-relaxed">
          {errorMessage || 'The verification link may have expired or already been used.'}
        </p>
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleResend}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] font-mono text-xs font-bold uppercase tracking-[0.15em] text-[var(--terminal-text-muted)] hover:border-[var(--phosphor-green)]/50 hover:text-[var(--phosphor-green)] transition-all"
          >
            Resend Verification
          </button>
          <Link
            href="/register"
            className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
          >
            Return to Registration
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6">
        <CheckCircle className="w-8 h-8 text-[var(--phosphor-green)]" />
      </div>
      <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
        Identity Verified
      </h2>
      <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-6 leading-relaxed">
        Your account has been activated. Redirecting to login...
      </p>
      <div className="h-1 w-24 mx-auto rounded-full bg-[var(--terminal-border)] overflow-hidden mb-6">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: '100%' }}
          transition={{ duration: 4 }}
          className="h-full bg-[var(--phosphor-green)]"
        />
      </div>
      <Link
        href="/login"
        className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
      >
        Go to Access Terminal
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <Suspense
          fallback={
            <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
              <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin mx-auto" />
            </div>
          }
        >
          <VerifyEmailContent />
        </Suspense>
      </motion.div>
    </div>
  );
}
```

Note: `useSearchParams()` requires a `<Suspense>` boundary in Next.js 15, which is why `VerifyEmailContent` is wrapped in `<Suspense>`.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(auth\)/verify-email/page.tsx
git commit -m "feat(auth): rewrite verify-email with PKCE verification and error states"
```

---

### Task 6: Smoke test and final commit

- [ ] **Step 1: Type-check the frontend**

```bash
cd frontend && npm run type-check
```

Expected: no errors.

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm run test -- --passWithNoTests 2>&1 | tail -20
```

Expected: all existing tests pass (no new tests needed — components are UI-only with Supabase SDK calls that require a running auth service to test meaningfully).

- [ ] **Step 3: Verify the email template renders**

Open `supabase/templates/confirmation.html` in a browser to visually inspect layout. Verify:
- Dark background with centered card
- "NOUS" wordmark
- "Confirm Your Identity" heading
- Gold "VERIFY IDENTITY" button
- Fallback URL text
- Footer text

- [ ] **Step 4: Push all changes**

```bash
git push origin develop
```
