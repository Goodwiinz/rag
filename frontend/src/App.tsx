import React, { useState, useEffect } from 'react';
import './App.css';

interface SystemInfo {
  [key: string]: any;
}

function App() {
  const [backendStatus, setBackendStatus] = useState<string>('checking...');
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    // Check backend health
    fetch('/health')
      .then(response => response.json())
      .then((data: SystemInfo) => {
        setBackendStatus('healthy');
        setSystemInfo(data);
      })
      .catch(error => {
        setBackendStatus('unreachable');
        console.error('Backend health check failed:', error);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Multimodal Enterprise RAG System</h1>
        <p>Intelligent cross-modal search across documents, images, audio, and video</p>

        <div className="status-section">
          <h2>System Status</h2>
          <div className="status-grid">
            <div className={`status-item ${backendStatus}`}>
              <span className="status-label">Backend API:</span>
              <span className="status-value">{backendStatus}</span>
            </div>
            <div className="status-item healthy">
              <span className="status-label">Frontend:</span>
              <span className="status-value">running</span>
            </div>
          </div>
        </div>

        {systemInfo && (
          <div className="system-info">
            <h3>System Information</h3>
            <pre>{JSON.stringify(systemInfo, null, 2)}</pre>
          </div>
        )}

        <div className="features-section">
          <h2>Features</h2>
          <div className="features-grid">
            <div className="feature-card">
              <h3>🔍 Semantic Search</h3>
              <p>AI-powered search across all content types</p>
            </div>
            <div className="feature-card">
              <h3>🖼️ Multimodal Analysis</h3>
              <p>Search text, images, audio, and video</p>
            </div>
            <div className="feature-card">
              <h3>🧠 Knowledge Graph</h3>
              <p>Connected entity relationships</p>
            </div>
            <div className="feature-card">
              <h3>⚡ Real-time Processing</h3>
              <p>Background document ingestion</p>
            </div>
          </div>
        </div>
      </header>
    </div>
  );
}

export default App;