import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';

export const ExperimentDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Handle missing experiment ID
  if (!id) {
    return (
      <div className="p-6">
        <div className="mb-6">
          <button
            onClick={() => navigate('/ab-testing')}
            className="text-blue-600 hover:text-blue-700 mb-4"
          >
            &larr; Back to Experiments
          </button>
          <h1 className="text-2xl font-bold text-foreground">
            Experiment Not Found
          </h1>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-red-600">
            Experiment ID is missing. Please select a valid experiment.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <button
          onClick={() => navigate('/ab-testing')}
          className="text-blue-600 hover:text-blue-700 mb-4"
        >
          &larr; Back to Experiments
        </button>
        <h1 className="text-2xl font-bold text-foreground">
          Experiment Details
        </h1>
        <p className="text-foreground">ID: {id}</p>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          View detailed experiment results and metrics.
        </p>
      </div>
    </div>
  );
};

export default ExperimentDetailsPage;
