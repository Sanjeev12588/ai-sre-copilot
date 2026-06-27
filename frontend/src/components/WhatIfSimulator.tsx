import React, { useState } from 'react';

export const WhatIfSimulator: React.FC = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSimulate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    setResult(null);

    // Simulated API response delay
    setTimeout(() => {
      setLoading(false);
      setResult(
        `[Simulation Result]
Target: restart payments-db-v2
Downstream Impact Scope: P0 CRITICAL IMPACT
- checkout-service: Blocked transactions, expected 504 Gateway Timeouts (99.8% probability)
- billing-worker: Event consumer queues backpressure spike
- recommendation-engine: Degraded state (Cached metrics fallback)

Risk mitigation advisory: Reschedule db restarts to window with lowest load, or trigger replica promotion first.`
      );
    }, 1500);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <form onSubmit={handleSimulate} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Enter a "What-If" action query to simulate downstream service impacts:
        </label>
        <textarea
          className="console-input"
          style={{ minHeight: '80px', resize: 'vertical' }}
          placeholder="e.g., If we restart the payments-db-v2 service now, what downstream services might be affected?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start' }} disabled={loading}>
          {loading ? 'Simulating impact...' : '⚡ Run Simulation'}
        </button>
      </form>

      {result && (
        <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', padding: '16px' }}>
          <h4 style={{ color: 'var(--color-red)', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
            Cascading Risk Analysis
          </h4>
          <pre style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
            {result}
          </pre>
        </div>
      )}
    </div>
  );
};

export default WhatIfSimulator;
