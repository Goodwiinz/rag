import React from 'react';

export const OrganizationSettingsPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Organization Settings</h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-gray-600">Configure organization settings and preferences.</p>
      </div>
    </div>
  );
};

export default OrganizationSettingsPage;
