import React, { useState } from 'react';

export const ActionConsole: React.FC = () => {
  const [outputLogs, setOutputLogs] = useState<string[]>([
    '[Console Init] Ready to execute runbooks.'
  ]);

  const triggerRunbook = (runbookId: string) => {
    setOutputLogs((prev) => [...prev, `[Action] Triggered ${runbookId} execution...`]);
    setTimeout(() => {
      setOutputLogs((prev) => [
        ...prev,
        `[${runbookId} Output] Simulated runbook completed. Connections recycled successfully.`
      ]);
    }, 1000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
      <div style={{ display: 'flex', gap: '8px' }}>
        <button className="btn" onClick={() => triggerRunbook('RB-DB-004')}>
          Reset DB Pool
        </button>
        <button className="btn" onClick={() => triggerRunbook('RB-CACHE-001')}>
          Flush Cache
        </button>
      </div>

      <div style={{ flex: 1, background: '#070913', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', overflowY: 'auto', minHeight: '150px' }}>
        {outputLogs.map((log, idx) => (
          <div key={idx} style={{ marginBottom: '4px', color: log.includes('[Action]') ? 'var(--color-yellow)' : 'var(--text-secondary)' }}>
            {log}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ActionConsole;
