import React from 'react';

export const AlertManagementPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Alert Management</h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Manage system alerts and notifications.
        </p>
      </div>
    </div>
  );
};

export default AlertManagementPage;
