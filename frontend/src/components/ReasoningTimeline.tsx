import React from 'react';

export interface ReasoningStep {
  agentName: string;
  status: 'completed' | 'active' | 'pending';
  thought: string;
  toolUsed?: string;
  timestamp: string;
}

interface ReasoningTimelineProps {
  steps?: ReasoningStep[];
}

export const ReasoningTimeline: React.FC<ReasoningTimelineProps> = ({ steps }) => {
  const defaultSteps: ReasoningStep[] = [
    {
      agentName: 'Incident Intake',
      status: 'completed',
      thought: 'Detected DB Connection Pool Exhaustion alert payload. Normalizing schema.',
      timestamp: '11:15:00'
    },
    {
      agentName: 'Workflow Coordinator',
      status: 'completed',
      thought: 'Created Incident Case File INC-892. Transferring control to Triage Agent.',
      timestamp: '11:15:05'
    },
    {
      agentName: 'Triage Agent',
      status: 'active',
      thought: 'Evaluating scope. Checking topology graph metrics for checkout-service.',
      toolUsed: 'get_metrics()',
      timestamp: '11:15:10'
    },
    {
      agentName: 'Log Analyst',
      status: 'pending',
      thought: 'Waiting to analyze connection logs for leakage detection.',
      timestamp: '--:--:--'
    }
  ];

  const activeSteps = steps || defaultSteps;

  return (
    <div className="timeline-track">
      {activeSteps.map((step, idx) => (
        <div key={idx} className={`timeline-node ${step.status}`}>
          <div className="timeline-node-dot" />
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px 16px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <h4 style={{ fontWeight: 600, color: step.status === 'active' ? 'var(--color-blue)' : 'var(--text-primary)' }}>
                {step.agentName}
              </h4>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{step.timestamp}</span>
            </div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{step.thought}</p>
            {step.toolUsed && (
              <div style={{ marginTop: '8px', display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-purple)' }}>
                  🔧 Tool: {step.toolUsed}
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ReasoningTimeline;
