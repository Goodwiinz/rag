import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';

const TRIGGER_API_URL =
  process.env.TRIGGER_API_URL ?? 'https://api.trigger.dev';
const TRIGGER_SECRET_KEY = process.env.TRIGGER_SECRET_KEY;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  if (!TRIGGER_SECRET_KEY) {
    return NextResponse.json(
      { error: 'Trigger.dev not configured' },
      { status: 503 }
    );
  }

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { runId: _runId } = await params;
  const body = await request.json();
  const { tokenId, confirmed } = body;

  if (!tokenId || typeof confirmed !== 'boolean') {
    return NextResponse.json(
      { error: 'tokenId and confirmed are required' },
      { status: 400 }
    );
  }

  const res = await fetch(
    `${TRIGGER_API_URL}/api/v1/waitpoints/tokens/${tokenId}/complete`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${TRIGGER_SECRET_KEY}`,
      },
      body: JSON.stringify({ output: { confirmed } }),
    }
  );

  if (!res.ok) {
    const text = await res.text();
    return NextResponse.json(
      { error: `Trigger.dev error: ${text}` },
      { status: res.status }
    );
  }

  return NextResponse.json({ status: 'confirmed' });
}
