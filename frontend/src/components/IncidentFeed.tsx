import React from 'react';

export interface Incident {
  id: string;
  title: string;
  severity: 'P0' | 'P1' | 'P2' | 'P3';
  status: string;
  timestamp: string;
}

interface IncidentFeedProps {
  activeIncidentId?: string;
  onSelectIncident?: (id: string) => void;
}

export const IncidentFeed: React.FC<IncidentFeedProps> = ({
  activeIncidentId,
  onSelectIncident
}) => {
  const mockIncidents: Incident[] = [
    {
      id: 'INC-892',
      title: 'Database connection pool exhausted',
      severity: 'P1',
      status: 'INVESTIGATING',
      timestamp: '2026-06-27T11:15:00Z'
    },
    {
      id: 'INC-893',
      title: 'High latency checkout service API',
      severity: 'P0',
      status: 'TRIAGED',
      timestamp: '2026-06-27T11:20:00Z'
    }
  ];

  return (
    <div className="incident-feed-panel">
      {mockIncidents.map((incident) => (
        <div
          key={incident.id}
          className={`incident-card ${incident.severity.toLowerCase()} ${
            activeIncidentId === incident.id ? 'active' : ''
          }`}
          onClick={() => onSelectIncident?.(incident.id)}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontWeight: 'bold' }}>{incident.id}</span>
            <span className={`severity-badge ${incident.severity.toLowerCase()}`}>
              {incident.severity}
            </span>
          </div>
          <p style={{ fontSize: '0.95rem', margin: '4px 0' }}>{incident.title}</p>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px' }}>
            <span>{incident.status}</span>
            <span>{new Date(incident.timestamp).toLocaleTimeString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default IncidentFeed;
