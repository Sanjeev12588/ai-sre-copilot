import { useState } from 'react';
import './css/styles.css';
import IncidentFeed from './components/IncidentFeed';
import ReasoningTimeline from './components/ReasoningTimeline';
import WhatIfSimulator from './components/WhatIfSimulator';
import ActionConsole from './components/ActionConsole';

function App() {
  const [activeIncident, setActiveIncident] = useState<string>('INC-892');

  return (
    <div className="app-container">
      {/* Premium Header */}
      <header className="header">
        <div className="logo-section">
          <div className="logo-icon" />
          <h1 className="logo-text">AI SRE Copilot</h1>
        </div>
        <div className="status-badge">
          <span className="status-dot" />
          <span>Copilot Agent Core Online</span>
        </div>
      </header>

      {/* Main Grid Layout */}
      <main className="main-layout">
        {/* Left Panel: Active Incidents */}
        <section className="panel panel-left">
          <div className="panel-header">
            <h2 className="panel-title">⚠️ Firing Alerts</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>2 Active</span>
          </div>
          <div className="panel-content">
            <IncidentFeed
              activeIncidentId={activeIncident}
              onSelectIncident={(id) => setActiveIncident(id)}
            />
          </div>
        </section>

        {/* Center Panel: Reasoning Timeline */}
        <section className="panel panel-center">
          <div className="panel-header">
            <h2 className="panel-title">👁️ AI Reasoning Timeline</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Active Step: 3/4</span>
          </div>
          <div className="panel-content">
            <ReasoningTimeline />
          </div>
        </section>

        {/* Right Panel: Controls & Runbooks */}
        <section className="panel panel-right" style={{ display: 'grid', gridTemplateRows: '1fr 1fr', height: '100%', overflow: 'hidden' }}>
          {/* Top Half: What-If Simulator */}
          <div style={{ borderBottom: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="panel-header">
              <h2 className="panel-title">🔮 What-If Simulator</h2>
            </div>
            <div className="panel-content" style={{ overflowY: 'auto' }}>
              <WhatIfSimulator />
            </div>
          </div>

          {/* Bottom Half: Action Console */}
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="panel-header">
              <h2 className="panel-title">🛠️ Remediation Console</h2>
            </div>
            <div className="panel-content" style={{ overflowY: 'auto' }}>
              <ActionConsole />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
