import React from 'react';
import { useNavigate } from 'react-router-dom';

export const CreateExperimentPage: React.FC = () => {
  const navigate = useNavigate();

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
          Create New Experiment
        </h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Configure and create a new A/B testing experiment.
        </p>
      </div>
    </div>
  );
};

export default CreateExperimentPage;
