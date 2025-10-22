import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const DocumentsPage: React.FC = () => {
  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Document management interface coming soon...
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default DocumentsPage;