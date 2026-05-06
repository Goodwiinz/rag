import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';

const TRIGGER_API_URL =
  process.env.TRIGGER_API_URL ?? 'https://api.trigger.dev';
const TRIGGER_SECRET_KEY = process.env.TRIGGER_SECRET_KEY;

export async function GET(
  _request: NextRequest,
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

  const { runId } = await params;

  const res = await fetch(`${TRIGGER_API_URL}/api/v3/runs/${runId}`, {
    headers: {
      Authorization: `Bearer ${TRIGGER_SECRET_KEY}`,
    },
  });

  if (!res.ok) {
    const text = await res.text();
    return NextResponse.json(
      { error: `Trigger.dev error: ${text}` },
      { status: res.status }
    );
  }

  const run = await res.json();

  return NextResponse.json({
    runId: run.id,
    status: run.status,
    metadata: run.metadata ?? {},
    output: run.output ?? null,
    error: run.error ?? null,
    createdAt: run.createdAt,
    updatedAt: run.updatedAt,
  });
}
