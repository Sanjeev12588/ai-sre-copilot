import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Radio,
  Cpu,
  FileText,
  RefreshCw,
  AlertTriangle,
  Clock
} from "lucide-react";
import {
  getIncident,
  getIncidentReport,
  connectIncidentWebSocket,
  type Incident,
  type TimelineEntry,
  type PostMortemReport,
  type WsEventMessage
} from "../services/api";

export const IncidentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [report, setReport] = useState<PostMortemReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket Live Streaming states
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [liveLogs, setLiveLogs] = useState<any[]>([]);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [agentDurations, setAgentDurations] = useState<Record<string, number>>({});

  const logTerminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Load baseline REST data
  const loadBaselineData = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const incData = await getIncident(id);
      setIncident(incData);
      setTimeline(incData.timeline || []);

      // Update durations map from current timeline
      const durs: Record<string, number> = {};
      (incData.timeline || []).forEach((entry) => {
        const name = entry.agent_name || entry.agent;
        if (name && name !== "system") {
          durs[name] = (durs[name] || 0) + entry.duration_ms;
        }
      });
      setAgentDurations(durs);

      // Attempt to load report if status resolved
      if (incData.report_status === "COMPLETED" || incData.status === "RESOLVED" || incData.status === "CLOSED") {
        const reportData = await getIncidentReport(id).catch(() => null);
        setReport(reportData);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load incident detail.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Rest-load effect
  useEffect(() => {
    loadBaselineData();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [id, loadBaselineData]);

  // WebSocket connection & lifecycle translation effect
  useEffect(() => {
    if (!id) return;

    const onWsMessage = (msg: WsEventMessage) => {
      // Append to live console terminal logger
      setLiveLogs((prev) => [...prev, msg]);

      // Check event types to update UI states in real time
      const type = msg.event_type;

      if (type === "agent.started") {
        setActiveAgent(msg.agent);
      } else if (type === "agent.completed") {
        setActiveAgent(null);
        if (msg.payload && msg.payload.duration_ms) {
          setAgentDurations((prev) => ({
            ...prev,
            [msg.agent]: msg.payload.duration_ms
          }));
        }
      }

      // Automatically sync REST data on transitions to keep dashboard accurate
      loadBaselineData();
    };

    const connect = () => {
      wsRef.current = connectIncidentWebSocket(
        id,
        onWsMessage,
        () => {
          setWsConnected(false);
        },
        () => {
          setWsConnected(false);
          // Auto-reconnect after 3 seconds
          setTimeout(() => {
            if (id) connect();
          }, 3000);
        }
      );
      setWsConnected(true);
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [id, loadBaselineData]);

  // Auto-scroll terminal log to bottom (Tail follow logs)
  useEffect(() => {
    if (logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [liveLogs, timeline]);

  if (loading) {
    return (
      <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
        <span>Retrieving incident case file...</span>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "16px", color: "var(--color-red)" }}>
        <Link to="/" style={{ color: "#3b82f6", display: "flex", alignItems: "center", gap: "6px", textDecoration: "none" }}>
          <ArrowLeft size={16} />
          <span>Back to registry</span>
        </Link>
        <h2>Error: {error || "Incident not found"}</h2>
      </div>
    );
  }

  // Pre-populate steps structure for the Agent execution panel
  const pipelineAgents = [
    "IntakeAgent",
    "TriageAgent",
    "LogAnalyzerAgent",
    "RootCauseAgent",
    "EvaluatorAgent",
    "RecoveryPlannerAgent",
    "EscalationAgent",
    "ReportGeneratorAgent"
  ];

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px", flexGrow: 1, overflowY: "auto" }}>

      {/* Header Back Button & WebSocket indicator */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Link to="/" style={{ color: "#3b82f6", display: "flex", alignItems: "center", gap: "6px", textDecoration: "none", fontSize: "0.9rem" }}>
          <ArrowLeft size={16} />
          <span>Back to incident registry</span>
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", color: wsConnected ? "var(--color-green)" : "var(--color-yellow)" }}>
            <Radio size={14} className={wsConnected ? "pulse-green" : ""} />
            <span>{wsConnected ? "WebSocket Live Streaming Active" : "WebSocket Connecting..."}</span>
          </div>
          <button className="btn" onClick={loadBaselineData} style={{ padding: "4px 8px", fontSize: "0.8rem" }}>
            <RefreshCw size={12} />
            <span>Force Sync JSON</span>
          </button>
        </div>
      </div>

      {/* Incident Main Card */}
      <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px", borderLeft: incident.severity === "P0" ? "4px solid #ef4444" : "4px solid #f59e0b" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px" }}>
              <h1 style={{ fontSize: "1.4rem", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{incident.incident_id}</h1>
              <span className={`sev-badge ${incident.severity.toLowerCase()}`}>{incident.severity}</span>
              <span className={`status-badge ${incident.status.toLowerCase()}`}>{incident.status}</span>
            </div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 500, color: "#fff" }}>{incident.title}</h2>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "4px" }}>{incident.description}</p>
          </div>
          <div style={{ textAlign: "right", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            <div>Target Env: <strong style={{ color: "#fff" }}>{incident.environment}</strong></div>
            <div>Trace Request ID: <code style={{ color: "#3b82f6" }}>{incident.metadata?.request_id || "system"}</code></div>
            <div>Registered At: {new Date(incident.created_at).toLocaleString()}</div>
          </div>
        </div>
      </div>

      {/* Grid panels */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "20px" }}>

        {/* Left Side Panels (Timeline logs and Post-Mortem) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>

          {/* Live Timeline Stream Console */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
              <Radio size={16} style={{ color: "var(--color-blue)" }} />
              <span>Real-Time SRE Pipeline Log Terminal</span>
            </h3>

            <div className="log-stream-terminal" ref={logTerminalRef}>
              {/* Combine REST timeline baseline events and new WebSocket logs */}
              {timeline.length === 0 && liveLogs.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                  Awaiting agent telemetry log streams...
                </div>
              ) : (
                <>
                  {/* Render REST timeline items */}
                  {timeline.map((entry, idx) => (
                    <div className="log-entry" key={`rest-${idx}`}>
                      <span className="log-time">[{new Date(entry.timestamp).toLocaleTimeString()}]</span>
                      <span className={`log-type ${entry.agent_name === "system" ? "created" : "agent-completed"}`}>
                        {entry.agent_name || entry.agent}
                      </span>
                      <span className="log-message">
                        <strong>{entry.action}</strong>: {entry.summary || entry.message}
                        {entry.confidence > 0 && ` (confidence: ${entry.confidence}%)`}
                        {entry.duration_ms > 0 && ` [duration: ${entry.duration_ms}ms]`}
                        {entry.tools_used.length > 0 && ` {tools: ${entry.tools_used.join(", ")}}`}
                      </span>
                    </div>
                  ))}

                  {/* Render live WebSocket streams not yet committed to rest timeline */}
                  {liveLogs
                    .filter((log) => !timeline.some((t) => t.timestamp === log.timestamp && t.action === log.payload?.action))
                    .map((log, idx) => (
                      <div className="log-entry" key={`live-${idx}`} style={{ borderLeft: "2px solid #3b82f6", paddingLeft: "6px" }}>
                        <span className="log-time">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className={`log-type ${(log.event_type || "").replace(".", "-")}`}>
                          {log.agent}
                        </span>
                        <span className="log-message" style={{ color: "#fff" }}>
                          <strong>{log.event_type}</strong>: {log.status} - {JSON.stringify(log.payload)}
                        </span>
                      </div>
                    ))}
                </>
              )}
            </div>
          </div>

          {/* Root Cause reasoning Card */}
          {(incident.status !== "NEW" && incident.status !== "TRIAGED") && (
            <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px", border: "1px solid rgba(236, 72, 153, 0.25)", background: "rgba(236, 72, 153, 0.02)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#ec4899", display: "flex", alignItems: "center", gap: "8px" }}>
                  <AlertTriangle size={16} />
                  <span>AI Diagnostics Verdict & Root Cause Analysis</span>
                </h3>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Pipeline Confidence Score:</span>
                  <span style={{ fontWeight: 700, color: "#ec4899", fontSize: "1.1rem" }}>{incident.confidence}%</span>
                </div>
              </div>
              <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: "8px", padding: "16px", border: "1px solid rgba(255,255,255,0.04)" }}>
                {incident.summary ? (
                  <p style={{ fontSize: "0.95rem", lineHeight: 1.5, color: "#cbd5e1" }}>{incident.summary}</p>
                ) : (
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Agent pipeline has not reached root cause diagnostic resolution yet. Watch logs above.</span>
                )}
              </div>
            </div>
          )}

          {/* Markdown Post-Mortem Report Panel */}
          {report && (
            <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                <FileText size={16} style={{ color: "var(--color-purple)" }} />
                <span>AI SRE Post-Mortem Report Artifact</span>
              </h3>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ background: "rgba(139, 92, 246, 0.05)", border: "1px solid rgba(139, 92, 246, 0.15)", borderRadius: "8px", padding: "16px" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--color-purple)", textTransform: "uppercase" }}>Executive Stakeholder Update</span>
                  <p style={{ fontSize: "0.9rem", color: "#e2e8f0", marginTop: "4px", lineHeight: 1.5 }}>
                    {report.stakeholder_update}
                  </p>
                </div>

                <div className="postmortem-container">
                  {/* Clean text formatting of markdown blocks */}
                  {report.report.split("\n").map((line, idx) => {
                    if (line.startsWith("# ")) {
                      return <h1 key={idx}>{line.substring(2)}</h1>;
                    } else if (line.startsWith("## ")) {
                      return <h2 key={idx}>{line.substring(3)}</h2>;
                    } else if (line.startsWith("### ")) {
                      return <h3 key={idx}>{line.substring(4)}</h3>;
                    } else if (line.startsWith("- ") || line.startsWith("* ")) {
                      return <li key={idx} style={{ marginLeft: "16px" }}>{line.substring(2)}</li>;
                    } else if (line.trim() === "") {
                      return <div key={idx} style={{ height: "8px" }} />;
                    } else {
                      return <p key={idx}>{line}</p>;
                    }
                  })}
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Right Side Panel (Agent Workflow State Visualization) */}
        <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px", height: "fit-content" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
            <Cpu size={16} style={{ color: "var(--color-green)" }} />
            <span>Agent Orchestration Flow</span>
          </h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
            Tracks which Google ADK sub-agents have completed execution or are active.
          </p>

          <div className="agent-flow-grid">
            {pipelineAgents.map((agent, index) => {
              // Determine status: is it currently active, completed, or queued
              const isCompleted = timeline.some((entry) => (entry.agent_name || entry.agent) === agent);
              const isActive = activeAgent === agent;

              let statusClass = "queued";
              let statusText = "Queued";
              if (isActive) {
                statusClass = "running";
                statusText = "Active Now";
              } else if (isCompleted) {
                statusClass = "completed";
                statusText = "Completed";
              }

              const dur = agentDurations[agent];

              return (
                <div key={agent} className={`agent-node-card ${statusClass}`}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                        {index + 1}.
                      </span>
                      <strong style={{ fontSize: "0.9rem", color: statusClass === "queued" ? "var(--text-secondary)" : "#fff" }}>
                        {agent}
                      </strong>
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "4px", marginTop: "2px" }}>
                      <Clock size={10} />
                      <span>{statusText}</span>
                    </span>
                  </div>
                  {dur > 0 && (
                    <span style={{ fontSize: "0.8rem", fontFamily: "var(--font-mono)", color: "var(--color-green)" }}>
                      {dur}ms
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
};
