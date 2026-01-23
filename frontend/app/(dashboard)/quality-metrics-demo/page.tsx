"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { QualityMetricsCard } from '@/components/metrics/QualityMetricsCard';

export default function QualityMetricsDemo() {
  const [query, setQuery] = useState("abdel factual");
  const [sessionId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Real-time Quality Metrics Demo</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <Label htmlFor="query">Query to Evaluate</Label>
                <Input
                  id="query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter a query to evaluate..."
                  className="mt-1"
                />
              </div>
              <p className="text-sm text-gray-600">
                This component shows simulated quality metrics in real-time.
                The metrics update every 2 seconds with realistic values.
              </p>
            </div>
          </CardContent>
        </Card>

        <QualityMetricsCard
          query={query}
          sessionId={sessionId || undefined}
        />
      </div>
    </div>
  );
}