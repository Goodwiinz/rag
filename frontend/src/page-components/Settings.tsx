import React, { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Navigate } from 'react-router-dom';

export const Settings: React.FC = () => {
  const { isAuthenticated, user } = useAuth();
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [emailNotifications, setEmailNotifications] = useState(true);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Profile Information
            </h3>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Name
                </label>
                <p className="mt-1 text-sm text-gray-900">
                  {user?.name || 'N/A'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Email
                </label>
                <p className="mt-1 text-sm text-gray-900">
                  {user?.email || 'N/A'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Role
                </label>
                <p className="mt-1 text-sm text-gray-900 capitalize">
                  {user?.role || 'N/A'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Storage Used
                </label>
                <p className="mt-1 text-sm text-gray-900">
                  {user
                    ? `${(user.storage_quota_used / 1024 / 1024).toFixed(1)} MB`
                    : 'N/A'}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Application Settings
            </h3>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-gray-900">
                    Dark Mode
                  </h4>
                  <p className="text-sm text-gray-500">
                    Toggle dark mode theme
                  </p>
                </div>
                <button
                  role="switch"
                  aria-checked={isDarkMode}
                  aria-label="Toggle dark mode"
                  onClick={() => setIsDarkMode(!isDarkMode)}
                  className={`relative inline-flex flex-shrink-0 h-6 w-11 border-2 border-gray-300 rounded-full cursor-pointer transition-colors ease-in-out duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${isDarkMode ? 'bg-blue-600' : 'bg-gray-200'}`}
                >
                  <span
                    className={`inline-block h-5 w-5 rounded-full bg-white shadow transform ring-0 transition ease-in-out duration-200 ${isDarkMode ? 'translate-x-5' : 'translate-x-0'}`}
                  ></span>
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-gray-900">
                    Email Notifications
                  </h4>
                  <p className="text-sm text-gray-500">
                    Receive email notifications
                  </p>
                </div>
                <button
                  role="switch"
                  aria-checked={emailNotifications}
                  aria-label="Toggle email notifications"
                  onClick={() => setEmailNotifications(!emailNotifications)}
                  className={`relative inline-flex flex-shrink-0 h-6 w-11 border-2 border-gray-300 rounded-full cursor-pointer transition-colors ease-in-out duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${emailNotifications ? 'bg-blue-600' : 'bg-gray-200'}`}
                >
                  <span
                    className={`inline-block h-5 w-5 rounded-full bg-white shadow transform ring-0 transition ease-in-out duration-200 ${emailNotifications ? 'translate-x-5' : 'translate-x-0'}`}
                  ></span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
