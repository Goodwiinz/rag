import React, { useState } from 'react';
import AnalyticsDashboard from './AnalyticsDashboard';

interface AnalyticsRouterProps {
  activeView?: string;
}

const AnalyticsRouter: React.FC<AnalyticsRouterProps> = ({ activeView = 'overview' }) => {
  const [currentView, setCurrentView] = useState(activeView);

  const navigationItems = [
    { id: 'overview', label: 'Dashboard Overview', icon: '📊' },
    { id: 'quality', label: 'Quality Metrics', icon: '📈' },
    { id: 'behavior', label: 'User Behavior', icon: '👥' },
    { id: 'performance', label: 'Performance', icon: '⚡' },
    { id: 'recommendations', label: 'Recommendations', icon: '💡' },
  ];

  const renderView = () => {
    switch (currentView) {
      case 'overview':
        return <AnalyticsDashboard />;
      case 'quality':
        return <AnalyticsDashboard />;
      case 'behavior':
        return <AnalyticsDashboard />;
      case 'performance':
        return <AnalyticsDashboard />;
      case 'recommendations':
        return <AnalyticsDashboard />;
      default:
        return <AnalyticsDashboard />;
    }
  };

  return (
    <div className="analytics-router flex h-screen bg-gray-50">
      {/* Sidebar Navigation */}
      <div className="w-64 bg-white shadow-lg">
        <div className="p-6">
          <h2 className="text-xl font-bold text-gray-900">Analytics</h2>
          <p className="text-sm text-gray-600 mt-1">T3 Quality Evaluation System</p>
        </div>
        <nav className="mt-6">
          {navigationItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setCurrentView(item.id)}
              className={`w-full flex items-center px-6 py-3 text-left hover:bg-gray-50 transition-colors ${
                currentView === item.id
                  ? 'border-l-4 border-blue-500 bg-blue-50 text-blue-700'
                  : 'text-gray-700 border-l-4 border-transparent'
              }`}
            >
              <span className="text-xl mr-3">{item.icon}</span>
              <div>
                <div className="font-medium">{item.label}</div>
                {item.id === 'overview' && (
                  <div className="text-xs text-gray-500">Main dashboard view</div>
                )}
                {item.id === 'quality' && (
                  <div className="text-xs text-gray-500">Search quality metrics</div>
                )}
                {item.id === 'behavior' && (
                  <div className="text-xs text-gray-500">User analytics</div>
                )}
                {item.id === 'performance' && (
                  <div className="text-xs text-gray-500">System performance</div>
                )}
                {item.id === 'recommendations' && (
                  <div className="text-xs text-gray-500">AI recommendations</div>
                )}
              </div>
            </button>
          ))}
        </nav>

        {/* System Status Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-gray-200">
          <div className="flex items-center">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="ml-2 text-sm text-gray-600">All systems operational</span>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            Last updated: {new Date().toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto">
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {navigationItems.find(item => item.id === currentView)?.label}
              </h1>
              <p className="text-gray-600 mt-1">
                Monitor and analyze your RAG system performance
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <button className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                Export Data
              </button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                Refresh
              </button>
            </div>
          </div>
        </div>
        <div className="p-6">
          {renderView()}
        </div>
      </div>
    </div>
  );
};

export default AnalyticsRouter;