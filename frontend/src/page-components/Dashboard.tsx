import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Navigate } from 'react-router-dom';

interface DashboardProps {
  children?: React.ReactNode;
}

export const Dashboard: React.FC<DashboardProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Dashboard content will be implemented in later tasks */}
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-foreground mb-4">
          Multimodal RAG System Dashboard
        </h1>
        <p className="text-foreground">
          Welcome! The dashboard interface is being built.
        </p>
        {children}
      </div>
    </div>
  );
};

export default Dashboard;
