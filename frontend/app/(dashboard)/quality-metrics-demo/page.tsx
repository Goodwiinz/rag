'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { QualityMetricsCard } from '@/components/metrics/QualityMetricsCard';

export default function QualityMetricsDemo() {
  const [query, setQuery] = useState('abdel factual');
  const [sessionId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-background p-6 md:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-semibold text-foreground">
              Quality metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="query">Query to evaluate</Label>
                <Input
                  id="query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter a query to evaluate"
                />
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Live retrieval quality for a query. When a real-time connection
                is unavailable, the panel below shows representative sample
                values, refreshed every couple of seconds, so you can preview
                the layout.
              </p>
            </div>
          </CardContent>
        </Card>

        <QualityMetricsCard query={query} sessionId={sessionId || undefined} />
      </div>
    </div>
  );
}
