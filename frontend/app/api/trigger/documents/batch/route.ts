import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';

const TRIGGER_API_URL =
  process.env.TRIGGER_API_URL ?? 'https://api.trigger.dev';
const TRIGGER_SECRET_KEY = process.env.TRIGGER_SECRET_KEY;

export async function POST(request: NextRequest) {
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

  const body = await request.json();

  if (!Array.isArray(body.documentIds) || body.documentIds.length === 0) {
    return NextResponse.json(
      { error: 'documentIds array is required' },
      { status: 400 }
    );
  }

  const payload = {
    documentIds: body.documentIds,
    priority: body.priority ?? 'normal',
    userId: session.user.id,
  };

  const res = await fetch(
    `${TRIGGER_API_URL}/api/v1/tasks/batch-process-documents/trigger`,
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
  return NextResponse.json({ runId: data.id });
}
