import React from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const DocumentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>Document Detail</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Document detail view for ID: {id} - Coming soon...
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default DocumentDetailPage;