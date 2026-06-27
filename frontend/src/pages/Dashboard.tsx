import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, Play, Plus, RefreshCw, Layers } from "lucide-react";
import { getIncidents, createIncident, type Incident } from "../services/api";

export const Dashboard: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // New alert triggers templates for easy demo
  const [alertTemplate, setAlertTemplate] = useState<string>("db");
  const [customTitle, setCustomTitle] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [successId, setSuccessId] = useState<string | null>(null);

  const fetchList = () => {
    setLoading(true);
    getIncidents()
      .then((data) => {
        // Sort by created_at descending
        const sorted = [...data].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setIncidents(sorted);
        setError(null);
      })
      .catch((err) => {
        setError(err.message || "Failed to load incidents list.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleTriggerAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSuccessId(null);

    // Build template payloads
    let raw_alert: Record<string, any>;
    let title: string;
    let env = "production";

    if (alertTemplate === "db") {
      title = customTitle || "Database connection pool critical degradation";
      raw_alert = {
        alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
        name: "DatabaseDegradation",
        service: "checkout-db",
        severity: "P1",
        annotations: {
          summary: "Checkout DB Connection Pool Full",
          description: "Database pool connections exhausted (utilization at 98%).",
        },
      };
    } else if (alertTemplate === "checkout") {
      title = customTitle || "Checkout API Service response latency high";
      raw_alert = {
        alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
        name: "HighLatencyCheckout",
        service: "checkout-api",
        severity: "P0",
        annotations: {
          summary: "Checkout service API endpoint latencies > 1500ms",
          description: "Checkout processing latencies spiked to 2.3 seconds.",
        },
      };
    } else {
      title = customTitle || "Auth service user CPU spike alert";
      env = "staging";
      raw_alert = {
        alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
        name: "AuthServerCPUSpike",
        service: "auth-service",
        severity: "P2",
        annotations: {
          summary: "Staging Auth service CPU load at 94%",
          description: "Staging identity service CPU utilization spiked.",
        },
      };
    }

    try {
      const result = await createIncident({
        title,
        environment: env,
        raw_alert,
      });
      setSuccessId(result.incident_id);
      setCustomTitle("");
      fetchList();
    } catch (err: any) {
      alert(`Error triggering SRE workflow: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Calculations
  const activeCount = incidents.filter((i) => i.status !== "RESOLVED" && i.status !== "CLOSED").length;
  const resolvedCount = incidents.filter((i) => i.status === "RESOLVED" || i.status === "CLOSED").length;
  const p0Count = incidents.filter((i) => i.severity === "P0").length;

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", flexGrow: 1 }}>
      {/* Overview Stats Dashboard Cards */}
      <div className="stats-grid">
        <div className="stat-card" style={{ borderLeft: "4px solid #3b82f6" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Total Registered</span>
          <span className="stat-value" style={{ color: "#f8fafc" }}>{incidents.length}</span>
        </div>
        <div className="stat-card" style={{ borderLeft: "4px solid #ef4444" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Active Incidents</span>
          <span className="stat-value" style={{ color: activeCount > 0 ? "#ef4444" : "#f8fafc" }}>{activeCount}</span>
        </div>
        <div className="stat-card" style={{ borderLeft: "4px solid #10b981" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Resolved / Closed</span>
          <span className="stat-value" style={{ color: "#10b981" }}>{resolvedCount}</span>
        </div>
        <div className="stat-card" style={{ borderLeft: "4px solid #ec4899" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Sev0 Critical</span>
          <span className="stat-value" style={{ color: p0Count > 0 ? "#ec4899" : "#f8fafc" }}>{p0Count}</span>
        </div>
      </div>

      {/* Main Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: "24px", flexGrow: 1, minHeight: "450px" }}>

        {/* Left Side: Incident List Table */}
        <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px", overflow: "hidden" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
              <ShieldAlert size={18} style={{ color: "var(--color-blue)" }} />
              <span>Incident Registry Log</span>
            </h2>
            <button className="btn" onClick={fetchList} style={{ padding: "6px 12px", fontSize: "0.85rem" }}>
              <RefreshCw size={14} />
              <span>Refresh Log</span>
            </button>
          </div>

          {loading ? (
            <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
              <span>Polling registered incidents database...</span>
            </div>
          ) : error ? (
            <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--color-red)" }}>
              <span>{error}</span>
            </div>
          ) : incidents.length === 0 ? (
            <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
              <span>No incidents registered. Use the Firing Alert simulator on the right to start!</span>
            </div>
          ) : (
            <div style={{ overflowY: "auto", flexGrow: 1 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", color: "var(--text-secondary)" }}>
                    <th style={{ padding: "12px 8px" }}>ID</th>
                    <th style={{ padding: "12px 8px" }}>Title</th>
                    <th style={{ padding: "12px 8px" }}>Env</th>
                    <th style={{ padding: "12px 8px" }}>Severity</th>
                    <th style={{ padding: "12px 8px" }}>Status</th>
                    <th style={{ padding: "12px 8px" }}>Created</th>
                    <th style={{ padding: "12px 8px" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((inc) => (
                    <tr
                      key={inc.incident_id}
                      style={{
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                        transition: "background 0.2s",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <td style={{ padding: "12px 8px", fontFamily: "var(--font-mono)", fontWeight: "bold" }}>
                        {inc.incident_id}
                      </td>
                      <td style={{ padding: "12px 8px", maxWidth: "260px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {inc.title}
                      </td>
                      <td style={{ padding: "12px 8px", textTransform: "capitalize" }}>
                        {inc.environment}
                      </td>
                      <td style={{ padding: "12px 8px" }}>
                        <span className={`sev-badge ${inc.severity.toLowerCase()}`}>
                          {inc.severity || "P1"}
                        </span>
                      </td>
                      <td style={{ padding: "12px 8px" }}>
                        <span className={`status-badge ${inc.status.toLowerCase()}`}>
                          {inc.status}
                        </span>
                      </td>
                      <td style={{ padding: "12px 8px", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                        {new Date(inc.created_at).toLocaleString()}
                      </td>
                      <td style={{ padding: "12px 8px" }}>
                        <Link to={`/incident/${inc.incident_id}`} className="btn" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>
                          <Play size={12} />
                          <span>Monitor</span>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Side: Demo Control Alert Trigger Simulator */}
        <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
            <Plus size={18} style={{ color: "var(--color-green)" }} />
            <span>Firing Alert Simulator</span>
          </h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            Inject alerts directly to the gateway to trigger the ADK multi-agent investigation workflow in the background.
          </p>

          <form onSubmit={handleTriggerAlert} style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "8px" }}>

            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)" }}>Alert Template</label>
              <select
                value={alertTemplate}
                onChange={(e) => setAlertTemplate(e.target.value)}
                style={{
                  width: "100%",
                  background: "var(--bg-secondary)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "8px",
                  padding: "10px",
                  color: "#fff",
                  outline: "none"
                }}
              >
                <option value="db">P1 - DatabaseDegradation (checkout-db)</option>
                <option value="checkout">P0 - HighLatencyCheckout (checkout-api)</option>
                <option value="auth">P2 - AuthServerCPUSpike (auth-service)</option>
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)" }}>Custom Title (Optional)</label>
              <input
                type="text"
                className="console-input"
                placeholder="e.g. Memory leak on payment worker"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
              style={{ width: "100%", marginTop: "8px" }}
            >
              <span>{isSubmitting ? "Triggering System Workflow..." : "Trigger SRE Investigation"}</span>
            </button>

            {successId && (
              <div
                style={{
                  background: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(16, 185, 129, 0.2)",
                  borderRadius: "8px",
                  padding: "12px",
                  color: "var(--color-green)",
                  fontSize: "0.85rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px"
                }}
              >
                <span style={{ fontWeight: "bold" }}>Success! Incident Triggered.</span>
                <Link to={`/incident/${successId}`} style={{ color: "#60a5fa", textDecoration: "underline", display: "flex", alignItems: "center", gap: "4px" }}>
                  <Play size={12} />
                  <span>Monitor live incident: {successId}</span>
                </Link>
              </div>
            )}

          </form>

          <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "16px", marginTop: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "6px" }}>
              <Layers size={14} />
              <span>Observability Console Info</span>
            </span>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
              The ADK sequential agents run in isolated background threads. The websocket streams event updates instantly back to any open Dashboard detail viewport without polling.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
};
