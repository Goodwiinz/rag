import React from 'react';
import { useNavigate } from 'react-router-dom';

export const CreateEvaluationPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="p-6">
      <div className="mb-6">
        <button
          onClick={() => navigate('/evaluation')}
          className="text-blue-600 hover:text-blue-700 mb-4"
        >
          &larr; Back to Evaluations
        </button>
        <h1 className="text-2xl font-bold text-foreground">
          Create New Evaluation
        </h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Configure and create a new RAG evaluation.
        </p>
      </div>
    </div>
  );
};

export default CreateEvaluationPage;
