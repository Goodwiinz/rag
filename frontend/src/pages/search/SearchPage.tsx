import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const SearchPage: React.FC = () => {
  return (
    <div className="container mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>Advanced Search</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Advanced search interface coming soon...
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default SearchPage;