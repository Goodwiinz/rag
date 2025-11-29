import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';

export const EvaluationDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Handle missing evaluation ID
  if (!id) {
    return (
      <div className="p-6">
        <div className="mb-6">
          <button
            onClick={() => navigate('/evaluation')}
            className="text-blue-600 hover:text-blue-700 mb-4"
          >
            &larr; Back to Evaluations
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Evaluation Not Found</h1>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-red-600">Evaluation ID is missing. Please select a valid evaluation.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <button
          onClick={() => navigate('/evaluation')}
          className="text-blue-600 hover:text-blue-700 mb-4"
        >
          &larr; Back to Evaluations
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Evaluation Details</h1>
        <p className="text-gray-600">ID: {id}</p>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-gray-600">View detailed evaluation results and metrics.</p>
      </div>
    </div>
  );
};

export default EvaluationDetailsPage;
