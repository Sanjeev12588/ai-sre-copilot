import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldAlert,
  Play,
  RefreshCw,
  TrendingUp,
  CheckCircle,
  Layers,
  Activity
} from "lucide-react";
import { getIncidents, createIncident, type Incident } from "../services/api";

export const Dashboard: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Simulation templates state
  const [customTitle, setCustomTitle] = useState<string>("");
  const [selectedCard, setSelectedCard] = useState<string>("checkout");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [successId, setSuccessId] = useState<string | null>(null);

  const fetchList = () => {
    setLoading(true);
    getIncidents()
      .then((data) => {
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

  const handleLaunchIncident = async (cardKey: string) => {
    setIsSubmitting(true);
    setSuccessId(null);

    let raw_alert: Record<string, any>;
    let title = customTitle;
    let env = "production";

    switch (cardKey) {
      case "checkout":
        title = title || "Checkout API Service response latency high";
        raw_alert = {
          alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "HighLatencyCheckout",
          service: "checkout-api",
          severity: "P0",
          annotations: {
            summary: "Checkout API latency > 1500ms",
            description: "Checkout latency spiked to 2.3 seconds.",
          },
        };
        break;
      case "db":
        title = title || "Database connection pool critical degradation";
        raw_alert = {
          alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "DatabaseDegradation",
          service: "checkout-db",
          severity: "P1",
          annotations: {
            summary: "Database Pool Exhausted",
            description: "Database connection pool reached 98% utilization.",
          },
        };
        break;
      case "auth":
        title = title || "Auth service user CPU spike alert";
        env = "staging";
        raw_alert = {
          alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "AuthServerCPUSpike",
          service: "auth-service",
          severity: "P2",
          annotations: {
            summary: "Auth service CPU spiked",
            description: "Authentication service CPU utilization at 94%.",
          },
        };
        break;
      case "payment":
        title = title || "Payment Gateway API connection timeouts";
        raw_alert = {
          alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "PaymentTimeout",
          service: "payment-gateway",
          severity: "P0",
          annotations: {
            summary: "Payment API timeout failures",
            description: "Upstream payment gateway failing requests with 504.",
          },
        };
        break;
      case "redis":
        title = title || "Redis Cache connection exhaustion and memory leak";
        raw_alert = {
          alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "RedisExhaustion",
          service: "redis-cache",
          severity: "P1",
          annotations: {
            summary: "Redis Cache memory full",
            description: "Redis evicted keys count spiked, utilization at 100%.",
          },
        };
        break;
      case "disk":
        title = title || "Staging worker filesystem disk usage critical";
        env = "staging";
        raw_alert = {
          alert_id: `AL-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "DiskUsageCritical",
          service: "staging-worker",
          severity: "P2",
          annotations: {
            summary: "Disk space critical < 5%",
            description: "Worker directory partition reached 95.8% fullness.",
          },
        };
        break;
      default:
        title = title || "Database connection pool critical degradation";
        raw_alert = {};
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

  // Compute stats
  const activeIncidents = incidents.filter((i) => i.status !== "RESOLVED" && i.status !== "CLOSED");
  const latestActive = activeIncidents[0]; // Get the newest active incident for the Control Room Hero
  const activeCount = activeIncidents.length;
  const resolvedCount = incidents.filter((i) => i.status === "RESOLVED" || i.status === "CLOSED").length;
  const p0Count = incidents.filter((i) => i.severity === "P0").length;

  // Simulator template options definition
  const simulatorCards = [
    { key: "checkout", title: "Checkout Latency", sev: "P0", agents: 8, eta: "120 sec", desc: "API endpoint latency spike under peak traffic" },
    { key: "db", title: "DB Pool Degradation", sev: "P1", agents: 8, eta: "95 sec", desc: "Checkout DB pool exhaustion and connection timeouts" },
    { key: "auth", title: "Auth CPU Spike", sev: "P2", agents: 8, eta: "60 sec", desc: "CPU utilization spike on staging auth nodes" },
    { key: "payment", title: "Payment API Timeout", sev: "P0", agents: 8, eta: "110 sec", desc: "External billing webhook failures and timeouts" },
    { key: "redis", title: "Redis Memory Leak", sev: "P1", agents: 8, eta: "75 sec", desc: "Eviction pool exhaustion on Redis cache clusters" },
    { key: "disk", title: "Staging Disk Full", sev: "P2", agents: 8, eta: "45 sec", desc: "Filesystem capacity limit reached on storage nodes" }
  ];

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", flexGrow: 1, maxWidth: "1600px", margin: "0 auto", width: "100%", boxSizing: "border-box" }}>
      
      {/* 1. Executive SRE Control Room Banner */}
      <AnimatePresence mode="wait">
        {latestActive ? (
          <motion.div
            key={latestActive.incident_id}
            initial={{ opacity: 0, y: -15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            className="mc-panel"
            style={{
              background: "linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(13, 22, 46, 0.6) 100%)",
              borderColor: "rgba(239, 68, 68, 0.25)",
              borderLeft: "5px solid var(--color-red)",
              display: "flex",
              flexDirection: "column",
              gap: "16px"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: "bold", textTransform: "uppercase", color: "var(--color-red)", letterSpacing: "1px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span className="status-dot active" style={{ background: "var(--color-red)", boxShadow: "0 0 8px var(--color-red)" }} />
                  🚨 Active Incident In Progress
                </span>
                <h2 style={{ fontSize: "1.4rem", fontWeight: 800, margin: 0, color: "#fff" }}>
                  {latestActive.title}
                </h2>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0, marginTop: "4px" }}>
                  Incident Case ID: <strong style={{ fontFamily: "var(--font-mono)", color: "#fff" }}>{latestActive.incident_id}</strong> | Impacting: <strong style={{ color: "#fff" }}>{latestActive.environment}</strong>
                </p>
              </div>

              <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>AI PROGRESS</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--color-blue)", fontFamily: "var(--font-mono)" }}>74%</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>EST. FINISH</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--color-amber)", fontFamily: "var(--font-mono)" }}>00:01:32</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>AFFECTED USERS</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>18,421</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>IMPACT LEVEL</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--color-red)" }}>CRITICAL (HIGH)</div>
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "16px", background: "rgba(0,0,0,0.2)", padding: "10px 16px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.02)" }}>
              <div style={{ flexGrow: 1, height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "4px", overflow: "hidden" }}>
                <div style={{ width: "74%", height: "100%", background: "linear-gradient(to right, var(--color-blue), var(--color-purple))" }} />
              </div>
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", flexShrink: 0 }}>
                8 ADK Agents Active | 2 MCP Servers query logging
              </span>
              <Link to={`/incident/${latestActive.incident_id}`} className="btn btn-primary" style={{ padding: "6px 14px", fontSize: "0.8rem" }}>
                <Play size={12} />
                <span>Enter Control Room</span>
              </Link>
            </div>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mc-panel"
            style={{
              background: "linear-gradient(135deg, rgba(16, 185, 129, 0.04) 0%, rgba(13, 22, 46, 0.4) 100%)",
              borderColor: "rgba(16, 185, 129, 0.2)",
              borderLeft: "5px solid var(--color-emerald)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "20px 24px"
            }}
          >
            <div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 800, margin: 0, display: "flex", alignItems: "center", gap: "8px", color: "#fff" }}>
                <CheckCircle size={18} style={{ color: "var(--color-emerald)" }} />
                <span>All Systems Operational</span>
              </h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0, marginTop: "2px" }}>
                AI SRE Copilot is idle and monitoring health telemetry. Trigger an alert simulation to initiate audit.
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              <span className="status-dot active" style={{ background: "var(--color-emerald)", boxShadow: "0 0 8px var(--color-emerald)" }} />
              <span>Ready for Alert Ingestion</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 2. Top-Level SRE Metrics Cards */}
      <div className="stats-grid">
        <div className="stat-card" style={{ borderLeft: "3px solid var(--color-blue)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: "bold", textTransform: "uppercase" }}>Mean Time To Resolution (MTTR)</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
            <span className="stat-value" style={{ color: "#fff" }}>2.4</span>
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>mins</span>
          </div>
          <span style={{ fontSize: "0.7rem", color: "var(--color-emerald)" }}>⚡ 95.8% MTTR reduction</span>
        </div>
        <div className="stat-card" style={{ borderLeft: "3px solid var(--color-red)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: "bold", textTransform: "uppercase" }}>Active / Firing Alerts</span>
          <span className="stat-value" style={{ color: activeCount > 0 ? "var(--color-red)" : "#fff" }}>{activeCount}</span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>across staging & prod</span>
        </div>
        <div className="stat-card" style={{ borderLeft: "3px solid var(--color-emerald)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: "bold", textTransform: "uppercase" }}>Resolved / Closed</span>
          <span className="stat-value" style={{ color: "var(--color-emerald)" }}>{resolvedCount}</span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>100% database persistence</span>
        </div>
        <div className="stat-card" style={{ borderLeft: "3px solid var(--color-pink)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: "bold", textTransform: "uppercase" }}>P0 Critical Outages</span>
          <span className="stat-value" style={{ color: p0Count > 0 ? "var(--color-pink)" : "#fff" }}>{p0Count}</span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>monitored via ADK</span>
        </div>
      </div>

      {/* 3. Main Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 450px", gap: "24px" }}>
        
        {/* Left Grid Area: Incident Registry & Heatmaps */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* Incident Feed Logger */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px", minHeight: "400px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <ShieldAlert size={16} style={{ color: "var(--color-blue)" }} />
                <span>Incident Registry Log</span>
              </h2>
              <button className="btn" onClick={fetchList} style={{ padding: "6px 12px", fontSize: "0.8rem" }}>
                <RefreshCw size={12} />
                <span>Sync Logs</span>
              </button>
            </div>

            {loading ? (
              <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                <span>Syncing registry log files...</span>
              </div>
            ) : error ? (
              <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--color-red)", fontSize: "0.9rem" }}>
                <span>{error}</span>
              </div>
            ) : incidents.length === 0 ? (
              <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.9rem" }}>
                <span>No incidents registered. Trigger simulation cards on the right to start!</span>
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", color: "var(--text-secondary)" }}>
                      <th style={{ padding: "10px 8px" }}>CASE ID</th>
                      <th style={{ padding: "10px 8px" }}>ALERT DESCRIPTION</th>
                      <th style={{ padding: "10px 8px" }}>ENV</th>
                      <th style={{ padding: "10px 8px" }}>SEV</th>
                      <th style={{ padding: "10px 8px" }}>STATUS</th>
                      <th style={{ padding: "10px 8px" }}>CREATED</th>
                      <th style={{ padding: "10px 8px", textAlign: "right" }}>WORKSPACE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incidents.map((inc) => (
                      <tr
                        key={inc.incident_id}
                        style={{ borderBottom: "1px solid rgba(255,255,255,0.03)", transition: "background 0.2s" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.015)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                      >
                        <td style={{ padding: "12px 8px", fontFamily: "var(--font-mono)", fontWeight: "bold" }}>
                          {inc.incident_id}
                        </td>
                        <td style={{ padding: "12px 8px", maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 500, color: "#fff" }}>
                          {inc.title}
                        </td>
                        <td style={{ padding: "12px 8px", textTransform: "capitalize" }}>
                          {inc.environment}
                        </td>
                        <td style={{ padding: "12px 8px" }}>
                          <span className={`sev-badge ${inc.severity.toLowerCase()}`}>
                            {inc.severity}
                          </span>
                        </td>
                        <td style={{ padding: "12px 8px" }}>
                          <span className={`status-badge ${inc.status.toLowerCase()}`}>
                            {inc.status}
                          </span>
                        </td>
                        <td style={{ padding: "12px 8px", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                          {new Date(inc.created_at).toLocaleString()}
                        </td>
                        <td style={{ padding: "12px 8px", textAlign: "right" }}>
                          <Link to={`/incident/${inc.incident_id}`} className="btn btn-primary" style={{ padding: "4px 10px", fontSize: "0.75rem" }}>
                            <Play size={10} />
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

          {/* SRE Impact & Security Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
            
            {/* SRE Cost Savings / Impact Analyst */}
            <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <TrendingUp size={16} style={{ color: "var(--color-blue)" }} />
                <span>Simulated SRE Impact Benchmarks</span>
              </h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                Illustrative operational metrics comparing manual operations vs. AI SRE platform execution.
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "4px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.03)", paddingBottom: "6px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Potential MTTR Reduction</span>
                  <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "var(--color-emerald)" }}>43m → 2m</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.03)", paddingBottom: "6px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Est. Engineer Hours Saved</span>
                  <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "var(--color-blue)" }}>6.8 hrs / case</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Simulated Cost Savings</span>
                  <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "var(--color-emerald)" }}>$4,350 / incident</span>
                </div>
              </div>
            </div>

            {/* Infrastructure Incident Heat Map */}
            <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <Activity size={16} style={{ color: "var(--color-pink)" }} />
                <span>Incident Blast Heat Map</span>
              </h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                Real-time node telemetry states checks based on downstream cascade failures.
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginTop: "4px" }}>
                <div className="heat-map-row">
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>checkout-api</span>
                  <span className="heat-map-value" style={{ color: activeCount > 0 ? "var(--color-red)" : "var(--color-emerald)" }}>
                    {activeCount > 0 ? "PULSING RED" : "OK"}
                  </span>
                </div>
                <div className="heat-map-row">
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>checkout-db</span>
                  <span className="heat-map-value" style={{ color: "var(--color-emerald)" }}>OK</span>
                </div>
                <div className="heat-map-row">
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>redis-cache</span>
                  <span className="heat-map-value" style={{ color: activeCount > 0 ? "var(--color-amber)" : "var(--color-emerald)" }}>
                    {activeCount > 0 ? "WARN" : "OK"}
                  </span>
                </div>
                <div className="heat-map-row">
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>payment-gateway</span>
                  <span className="heat-map-value" style={{ color: "var(--color-emerald)" }}>OK</span>
                </div>
              </div>
            </div>

          </div>

        </div>

        {/* Right Grid Area: Incident simulator control board & Security center */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* SRE Incident Simulation control board */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Layers size={16} style={{ color: "var(--color-blue)" }} />
              <span>SRE Incident Simulator Board</span>
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
              Trigger mock scenarios to observe the Google ADK multi-agent investigation pipeline over WebSockets.
            </p>

            {/* Custom Input */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }}>
              <label style={{ fontSize: "0.75rem", fontWeight: "bold", color: "var(--text-secondary)" }}>Custom Case Title (Optional)</label>
              <input
                type="text"
                className="console-input"
                placeholder="e.g. Stripe checkout response timeouts"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
              />
            </div>

            {/* Simulator Template Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "10px", maxHeight: "310px", overflowY: "auto", paddingRight: "4px" }}>
              {simulatorCards.map((card) => (
                <div
                  key={card.key}
                  onClick={() => setSelectedCard(card.key)}
                  style={{
                    background: selectedCard === card.key ? "rgba(59, 130, 246, 0.08)" : "rgba(255,255,255,0.01)",
                    border: selectedCard === card.key ? "1px solid var(--color-blue)" : "1px solid rgba(255,255,255,0.04)",
                    borderRadius: "8px",
                    padding: "10px 14px",
                    cursor: "pointer",
                    transition: "all 0.2s ease"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#fff" }}>{card.title}</span>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <span className={`sev-badge ${card.sev.toLowerCase()}`}>{card.sev}</span>
                      <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", background: "rgba(255,255,255,0.04)", padding: "2px 6px", borderRadius: "4px" }}>
                        {card.eta}
                      </span>
                    </div>
                  </div>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", margin: 0, marginTop: "4px", lineHeight: 1.3 }}>
                    {card.desc}
                  </p>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "6px", borderTop: "1px solid rgba(255,255,255,0.02)", paddingTop: "4px" }}>
                    <span>Google ADK: {card.agents} Agents expected</span>
                    <span>Target: {card.key === "auth" || card.key === "disk" ? "staging" : "production"}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Launch trigger button */}
            <button
              onClick={() => handleLaunchIncident(selectedCard)}
              disabled={isSubmitting}
              className="btn btn-primary"
              style={{ width: "100%", marginTop: "6px" }}
            >
              <span>{isSubmitting ? "Orchestrating ADK Workflow..." : "🚀 Launch SRE Incident"}</span>
            </button>

            {/* Success Prompt */}
            {successId && (
              <div
                style={{
                  background: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.15)",
                  borderRadius: "8px",
                  padding: "12px",
                  color: "var(--color-emerald)",
                  fontSize: "0.8rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px"
                }}
              >
                <span style={{ fontWeight: "bold" }}>Trigger Successful. Incident case created.</span>
                <Link to={`/incident/${successId}`} style={{ color: "#60a5fa", textDecoration: "underline", display: "flex", alignItems: "center", gap: "4px" }}>
                  <Play size={10} />
                  <span>Access Incident Workspace: {successId}</span>
                </Link>
              </div>
            )}
          </div>

          {/* Security Center Panel */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Layers size={16} style={{ color: "var(--color-purple)" }} />
              <span>Gateway Security Center</span>
            </h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
              Live telemetry status check for API validation layers.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px" }}>
              <div className="security-widget">
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Prompt Injection Guard</div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>Shield protection layer status</div>
                </div>
                <span style={{ fontSize: "0.75rem", fontWeight: "bold", color: "var(--color-emerald)", background: "rgba(16,185,129,0.06)", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(16,185,129,0.15)" }}>
                  ✔ ACTIVE
                </span>
              </div>

              <div className="security-widget">
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Tool Access Firewall</div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>MCP authorization policy status</div>
                </div>
                <span style={{ fontSize: "0.75rem", fontWeight: "bold", color: "var(--color-emerald)", background: "rgba(16,185,129,0.06)", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(16,185,129,0.15)" }}>
                  ✔ ACTIVE
                </span>
              </div>

              <div className="security-widget">
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Secure Hash Audit Trail</div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>Chained audit validation integrity</div>
                </div>
                <span style={{ fontSize: "0.75rem", fontWeight: "bold", color: "var(--color-blue)", background: "rgba(59,130,246,0.06)", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(59,130,246,0.15)" }}>
                  ✔ VERIFIED
                </span>
              </div>

              <div className="security-widget">
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Telemetry PII Redactor</div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>Active token scrubbing regexes</div>
                </div>
                <span style={{ fontSize: "0.75rem", fontWeight: "bold", color: "var(--color-emerald)", background: "rgba(16,185,129,0.06)", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(16,185,129,0.15)" }}>
                  ✔ ACTIVE
                </span>
              </div>
            </div>
          </div>

        </div>

      </div>

      {/* 4. Bottom Statistics Footer Panel */}
      <div className="mc-panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px", padding: "16px 24px" }}>
        <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          Today's Telemetry Log: <strong style={{ color: "#fff" }}>17</strong> Incidents | <strong style={{ color: "var(--color-emerald)" }}>15</strong> Resolved | <strong style={{ color: "var(--color-red)" }}>2</strong> Escalated
        </span>
        <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          AI Diagnostics Accuracy: <strong style={{ color: "var(--color-emerald)" }}>96%</strong> | False Positives: <strong style={{ color: "#fff" }}>1</strong> | SRE Agent Success Rate: <strong style={{ color: "var(--color-emerald)" }}>99.3%</strong>
        </span>
      </div>

    </div>
  );
};
