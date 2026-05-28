import React from 'react';
import { Link } from 'react-router-dom';

export const ABTestingDashboardPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-foreground">
          A/B Testing Dashboard
        </h1>
        <Link
          to="/ab-testing/create"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Create Experiment
        </Link>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Manage and monitor your A/B testing experiments.
        </p>
      </div>
    </div>
  );
};

export default ABTestingDashboardPage;
