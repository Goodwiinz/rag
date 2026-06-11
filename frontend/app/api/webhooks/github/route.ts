import { NextRequest, NextResponse } from 'next/server';
import { createHmac, timingSafeEqual } from 'crypto';

const TRIGGER_API_URL =
  process.env.TRIGGER_API_URL ?? 'https://api.trigger.dev';
const TRIGGER_SECRET_KEY = process.env.TRIGGER_SECRET_KEY;
const GITHUB_WEBHOOK_SECRET = process.env.GITHUB_WEBHOOK_SECRET;

function verifySignature(payload: string, signature: string | null): boolean {
  if (!GITHUB_WEBHOOK_SECRET || !signature) return false;

  const expected = `sha256=${createHmac('sha256', GITHUB_WEBHOOK_SECRET)
    .update(payload)
    .digest('hex')}`;

  try {
    return timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  if (!TRIGGER_SECRET_KEY) {
    return NextResponse.json(
      { error: 'Trigger.dev not configured' },
      { status: 503 }
    );
  }

  // SECURITY (audit #20): fail closed. The signature check used to be gated on
  // `GITHUB_WEBHOOK_SECRET &&` — so on any deployment where the env var was
  // unset (staging clones), an UNAUTHENTICATED attacker could POST a crafted
  // push event and trigger a reindex job with arbitrary payload. The secret is
  // now mandatory: no secret → 503, and the signature is always verified.
  if (!GITHUB_WEBHOOK_SECRET) {
    return NextResponse.json(
      { error: 'Webhook secret not configured' },
      { status: 503 }
    );
  }

  const rawBody = await request.text();
  const signature = request.headers.get('x-hub-signature-256');

  if (!verifySignature(rawBody, signature)) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 });
  }

  const event = request.headers.get('x-github-event');
  if (event !== 'push') {
    return NextResponse.json({ status: 'ignored', event });
  }

  const payload = JSON.parse(rawBody);

  const res = await fetch(
    `${TRIGGER_API_URL}/api/v1/tasks/github-push-reindex/trigger`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${TRIGGER_SECRET_KEY}`,
      },
      body: JSON.stringify({ payload }),
    }
  );

  if (!res.ok) {
    const text = await res.text();
    return NextResponse.json(
      { error: `Trigger.dev error: ${text}` },
      { status: res.status }
    );
  }

  const data = await res.json();
  return NextResponse.json({ status: 'triggered', runId: data.id });
}
