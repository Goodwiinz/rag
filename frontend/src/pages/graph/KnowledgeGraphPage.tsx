import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const KnowledgeGraphPage: React.FC = () => {
  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>Knowledge Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Knowledge graph visualization coming soon...
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default KnowledgeGraphPage;