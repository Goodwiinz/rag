import React from 'react';

export const UserSettingsPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">User Settings</h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Manage your personal preferences and profile.
        </p>
      </div>
    </div>
  );
};

export default UserSettingsPage;
