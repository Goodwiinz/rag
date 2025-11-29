import React from 'react';
import { Link } from 'react-router-dom';

export const EvaluationManagementPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Evaluation Management</h1>
        <Link
          to="/evaluation/create"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Create Evaluation
        </Link>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-gray-600">Manage and view your RAG system evaluations.</p>
      </div>
    </div>
  );
};

export default EvaluationManagementPage;
