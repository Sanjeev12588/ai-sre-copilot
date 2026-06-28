import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Radio,
  Cpu,
  FileText,
  RefreshCw,
  Clock,
  Play,
  Pause,
  ChevronRight,
  Database,
  Activity,
  Terminal,
  ShieldCheck
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

  // Interactive Replay states
  const [replayMode, setReplayMode] = useState<boolean>(false);
  const [replayStep, setReplayStep] = useState<number>(0);
  const [replaySpeed, setReplaySpeed] = useState<number>(1);
  const [isReplayPlaying, setIsReplayPlaying] = useState<boolean>(false);

  // Tab state for report
  const [activeTab, setActiveTab] = useState<string>("summary");

  const logTerminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const replayIntervalRef = useRef<any>(null);

  // Load baseline REST data
  const loadBaselineData = useCallback(async () => {
    if (!id) return;
    try {
      setError(null);
      const incData = await getIncident(id);
      setIncident(incData);
      setTimeline(incData.timeline || []);

      // Extract durations
      const durs: Record<string, number> = {};
      (incData.timeline || []).forEach((entry) => {
        const name = entry.agent_name || entry.agent;
        if (name && name !== "system") {
          durs[name] = (durs[name] || 0) + entry.duration_ms;
        }
      });
      setAgentDurations(durs);

      // Fetch postmortem if completed/resolved
      if (incData.report_status === "COMPLETED" || incData.status === "RESOLVED" || incData.status === "CLOSED") {
        const reportData = await getIncidentReport(id).catch(() => null);
        setReport(reportData);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load incident details.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadBaselineData();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (replayIntervalRef.current) clearInterval(replayIntervalRef.current);
    };
  }, [id, loadBaselineData]);

  // WebSocket effect
  useEffect(() => {
    if (!id || replayMode) return;

    const onWsMessage = (msg: WsEventMessage) => {
      setLiveLogs((prev) => [...prev, msg]);
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
      loadBaselineData();
    };

    const connect = () => {
      wsRef.current = connectIncidentWebSocket(
        id,
        onWsMessage,
        () => setWsConnected(false),
        () => {
          setWsConnected(false);
          setTimeout(() => { if (id && !replayMode) connect(); }, 3000);
        }
      );
      setWsConnected(true);
    };

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [id, loadBaselineData, replayMode]);

  // Scroll terminal logs
  useEffect(() => {
    if (logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [liveLogs, timeline, replayStep, replayMode]);

  if (loading) {
    return (
      <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
        <span>Opening SRE Incident Workspace...</span>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "16px", color: "var(--color-red)" }}>
        <Link to="/" style={{ color: "var(--color-blue)", display: "flex", alignItems: "center", gap: "6px", textDecoration: "none" }}>
          <ArrowLeft size={16} />
          <span>Back to Mission Control</span>
        </Link>
        <h2>Error: {error || "Incident case not found"}</h2>
      </div>
    );
  }

  // Pre-configured list of pipeline agent stages
  const pipelineAgents = [
    { id: "IntakeAgent", label: "Intake", index: 1 },
    { id: "TriageAgent", label: "Triage", index: 2 },
    { id: "LogAnalyzerAgent", label: "Log Analyzer", index: 3 },
    { id: "RootCauseAgent", label: "Root Cause", index: 4 },
    { id: "EvaluatorAgent", label: "Evaluator", index: 5 },
    { id: "RecoveryPlannerAgent", label: "Recovery Planner", index: 6 },
    { id: "EscalationAgent", label: "Escalation", index: 7 },
    { id: "ReportGeneratorAgent", label: "Report Gen", index: 8 }
  ];

  // Replay Simulator Steps Configuration
  const replayTimeline = [
    {
      timestamp: "12:40:01",
      agent: "system",
      action: "Alert Ingested",
      summary: "Critical threshold crossed for checkout-api backend services.",
      confidence: 25,
      active: "IntakeAgent",
      logs: "INGESTING: Raw JSON webhook received. Routing payload to SRE Intake queue."
    },
    {
      timestamp: "12:40:05",
      agent: "IntakeAgent",
      action: "Payload Sanitized",
      summary: "Sanity validation passed. Triggering ADK coordinator.",
      confidence: 38,
      active: "TriageAgent",
      logs: "INTAKE: Security check passed. Anti-injection filter validated. Launching Triage."
    },
    {
      timestamp: "12:40:12",
      agent: "TriageAgent",
      action: "Severity Categorized",
      summary: "Incident assessed as P0 outage. Impacting production Checkout API.",
      confidence: 50,
      active: "LogAnalyzerAgent",
      logs: "TRIAGE: Checked environment status. Classified as P0 CRITICAL. Dispatched Log Analyzer."
    },
    {
      timestamp: "12:40:22",
      agent: "LogAnalyzerAgent",
      action: "Log Extraction Completed",
      summary: "Found 12 database connection pool timeout exceptions in checkouts.",
      confidence: 65,
      active: "RootCauseAgent",
      logs: "LOGS: Extracted checkout-api logs. Detected: 'Checkout API connection pool exhaustion'."
    },
    {
      timestamp: "12:40:34",
      agent: "RootCauseAgent",
      action: "Root Cause Hypothesis Deducing",
      summary: "Root cause narrowed to Redis connection leak.",
      confidence: 78,
      active: "EvaluatorAgent",
      logs: "RCA: Deducted Redis connection pool overflow. Generating counterarguments."
    },
    {
      timestamp: "12:40:46",
      agent: "EvaluatorAgent",
      action: "Hypothesis Asserted",
      summary: "Verified database metrics. checkout-db is green. Confirming Redis leak.",
      confidence: 88,
      active: "RecoveryPlannerAgent",
      logs: "EVALUATOR: Database ping returned healthy. Confirmed Redis connection leak."
    },
    {
      timestamp: "12:40:58",
      agent: "RecoveryPlannerAgent",
      action: "Mitigation Playbook Generated",
      summary: "Recommended action: Restart checkout-api and flush Redis cache.",
      confidence: 96,
      active: "ReportGeneratorAgent",
      logs: "RECOVERY: Playbook 18-A loaded. Proposing restart. Waiting SRE authorization."
    },
    {
      timestamp: "12:41:15",
      agent: "ReportGeneratorAgent",
      action: "Case post-mortem Done",
      summary: "Generated Markdown post-mortem report. Case archived.",
      confidence: 96,
      active: null,
      logs: "REPORT: Compiled audit chain and logs. Post-mortem report generated successfully."
    }
  ];

  // Replay actions
  const startReplay = () => {
    if (replayIntervalRef.current) clearInterval(replayIntervalRef.current);
    setReplayMode(true);
    setReplayStep(0);
    setIsReplayPlaying(true);
  };

  const toggleReplayPlay = () => {
    setIsReplayPlaying(!isReplayPlaying);
  };

  // Replay tick interval
  useEffect(() => {
    if (replayMode && isReplayPlaying) {
      if (replayIntervalRef.current) clearInterval(replayIntervalRef.current);
      
      const stepDuration = 2500 / replaySpeed;
      replayIntervalRef.current = setInterval(() => {
        setReplayStep((prev) => {
          if (prev >= replayTimeline.length - 1) {
            clearInterval(replayIntervalRef.current);
            setIsReplayPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, stepDuration);
    } else {
      if (replayIntervalRef.current) clearInterval(replayIntervalRef.current);
    }
    return () => {
      if (replayIntervalRef.current) clearInterval(replayIntervalRef.current);
    };
  }, [replayMode, isReplayPlaying, replaySpeed]);

  const stopReplay = () => {
    setReplayMode(false);
    setIsReplayPlaying(false);
    if (replayIntervalRef.current) clearInterval(replayIntervalRef.current);
    loadBaselineData();
  };

  // Compute active variables based on live vs replay
  const currentConfidence = replayMode
    ? replayTimeline[replayStep].confidence
    : incident.confidence || 0;

  const currentActiveAgent = replayMode
    ? replayTimeline[replayStep].active
    : activeAgent;

  const currentTimeline = replayMode
    ? replayTimeline.slice(0, replayStep + 1).map((s) => ({
        timestamp: new Date().toISOString(),
        agent_name: s.agent,
        agent: s.agent,
        event_type: "REPLAY",
        action: s.action,
        summary: s.summary,
        confidence: s.confidence,
        tools_used: s.agent === "LogAnalyzerAgent" ? ["query_logs()"] : s.agent === "RecoveryPlannerAgent" ? ["trigger_restart()"] : [],
        duration_ms: s.agent === "system" ? 0 : 1200,
        entry_status: "SUCCESS"
      }))
    : timeline;

  const currentLogs = replayMode
    ? replayTimeline.slice(0, replayStep + 1).map((s) => s.logs)
    : [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", flexGrow: 1, maxWidth: "1600px", margin: "0 auto", width: "100%", boxSizing: "border-box" }}
    >
      
      {/* 1. Header with Breadcrumb and controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Link to="/" onClick={stopReplay} style={{ color: "var(--color-blue)", display: "flex", alignItems: "center", gap: "6px", textDecoration: "none", fontSize: "0.9rem", fontWeight: "bold" }}>
          <ArrowLeft size={16} />
          <span>Exit Workspace</span>
        </Link>
        
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          {replayMode ? (
            <div className="replay-controls">
              <span style={{ fontSize: "0.8rem", color: "var(--color-purple)", fontWeight: "bold" }}>🎬 REPLAY MODE</span>
              <button className="replay-btn" onClick={toggleReplayPlay}>
                {isReplayPlaying ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <div style={{ display: "flex", gap: "6px" }}>
                {[1, 2, 4].map((s) => (
                  <span
                    key={s}
                    className="replay-speed-badge"
                    onClick={() => setReplaySpeed(s)}
                    style={{
                      background: replaySpeed === s ? "var(--color-blue)" : "rgba(255,255,255,0.03)",
                      color: replaySpeed === s ? "#fff" : "var(--text-secondary)"
                    }}
                  >
                    {s}x
                  </span>
                ))}
              </div>
              <button className="btn btn-danger" onClick={stopReplay} style={{ padding: "4px 10px", fontSize: "0.75rem" }}>
                Exit Replay
              </button>
            </div>
          ) : (
            <>
              {(incident.status === "RESOLVED" || incident.status === "CLOSED" || incident.report_status === "COMPLETED") && (
                <button className="btn btn-primary" onClick={startReplay} style={{ padding: "6px 14px", fontSize: "0.8rem" }}>
                  🎬 Replay Investigation
                </button>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", color: wsConnected ? "var(--color-emerald)" : "var(--color-amber)" }}>
                <span className={`status-dot active`} style={{ background: wsConnected ? "var(--color-emerald)" : "var(--color-amber)" }} />
                <span>{wsConnected ? "WebSocket Connected" : "Connecting WebSocket..."}</span>
              </div>
              <button className="btn" onClick={loadBaselineData} style={{ padding: "6px 12px", fontSize: "0.8rem" }}>
                <RefreshCw size={12} />
                <span>Sync</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* 2. Top-Level Case Header Metadata */}
      <div className="mc-panel" style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "24px", borderLeft: incident.severity === "P0" ? "5px solid var(--color-red)" : "5px solid var(--color-amber)" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 800, margin: 0, fontFamily: "var(--font-mono)", color: "#fff" }}>
              {incident.incident_id}
            </h1>
            <span className={`sev-badge ${incident.severity.toLowerCase()}`}>{incident.severity}</span>
            <span className={`status-badge ${replayMode ? "investigating" : incident.status.toLowerCase()}`}>
              {replayMode ? "Investigating" : incident.status}
            </span>
          </div>
          <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "#fff", marginTop: "4px" }}>
            {incident.title}
          </h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>
            Target Environment: <strong style={{ color: "#fff" }}>{incident.environment}</strong> | Tracer Request: <code style={{ color: "var(--color-blue)" }}>{incident.metadata?.request_id || "system"}</code>
          </p>
        </div>

        {/* Circular Confidence Gauge */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px", justifyContent: "flex-end" }}>
          <div style={{ position: "relative", width: "70px", height: "70px" }}>
            <svg width="70" height="70" viewBox="0 0 36 36">
              <path
                className="circular-progress-bg"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className="circular-progress-fg animate-glow"
                stroke="url(#grad-blue)"
                strokeWidth="2.5"
                strokeDasharray={`${currentConfidence}, 100`}
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <text x="18" y="21" fontFamily="var(--font-mono)" fontWeight="bold" fontSize="7" fill="#fff" textAnchor="middle">
                {currentConfidence}%
              </text>
            </svg>
          </div>
          <div style={{ textAlign: "left" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", fontWeight: "bold", textTransform: "uppercase" }}>Confidence</div>
            <div style={{ fontSize: "0.85rem", fontWeight: "bold", color: currentConfidence > 75 ? "var(--color-emerald)" : "var(--color-amber)" }}>
              {currentConfidence > 75 ? "HIGH" : currentConfidence > 40 ? "MEDIUM" : "LOW"}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Main Workspace Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 400px", gap: "24px" }}>
        
        {/* Left Columns: Topology, Collaboration Graph, Debate, Timeline */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* SRE Infrastructure Topology & Blast Radius */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Activity size={16} style={{ color: "var(--color-pink)" }} />
              <span>Infrastructure Dependency Canvas (Blast Radius)</span>
            </h3>
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", background: "rgba(0,0,0,0.2)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.02)" }}>
              {["Users", "LB", "Gateway", "checkout-api", "payment-api", "redis-cache", "postgres"].map((node, idx) => {
                // Determine node color status based on incident environment
                let status = "healthy";
                if (node === "checkout-api") status = "critical";
                else if (node === "redis-cache") status = "warning";
                else if (node === "Users" || node === "LB" || node === "Gateway") status = "healthy";
                
                return (
                  <React.Fragment key={node}>
                    <div
                      style={{
                        padding: "10px 14px",
                        borderRadius: "8px",
                        background: status === "critical" ? "rgba(239, 68, 68, 0.12)" : status === "warning" ? "rgba(245, 158, 11, 0.12)" : "rgba(16, 185, 129, 0.12)",
                        border: `1px solid ${status === "critical" ? "var(--color-red)" : status === "warning" ? "var(--color-amber)" : "var(--color-emerald)"}`,
                        color: "#fff",
                        fontWeight: "bold",
                        fontSize: "0.8rem",
                        boxShadow: status === "critical" ? "0 0 10px rgba(239, 68, 68, 0.2)" : "none"
                      }}
                    >
                      {node}
                    </div>
                    {idx < 6 && <ChevronRight size={16} style={{ color: "var(--text-muted)" }} />}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* SRE Agent Collaboration Canvas */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Cpu size={16} style={{ color: "var(--color-blue)" }} />
              <span>Multi-Agent Collaboration Canvas</span>
            </h3>

            <div className="canvas-container">
              <svg className="collaboration-svg" viewBox="0 0 400 520">
                {/* SVG Connections Lines */}
                <line x1="200" y1="60" x2="100" y2="135" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="200" y1="60" x2="300" y2="135" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="100" y1="175" x2="200" y2="240" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="300" y1="175" x2="200" y2="240" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="200" y1="280" x2="200" y2="335" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="200" y1="375" x2="200" y2="430" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="200" y1="470" x2="100" y2="520" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />
                <line x1="200" y1="470" x2="300" y2="520" stroke="rgba(255,255,255,0.08)" strokeWidth="2" className="connection-line" />

                {/* Nodes rendering */}
                {pipelineAgents.map((agent) => {
                  let x = 200;
                  let y = 50;
                  
                  if (agent.id === "IntakeAgent") { x = 200; y = 40; }
                  else if (agent.id === "TriageAgent") { x = 100; y = 135; }
                  else if (agent.id === "LogAnalyzerAgent") { x = 300; y = 135; }
                  else if (agent.id === "RootCauseAgent") { x = 200; y = 240; }
                  else if (agent.id === "EvaluatorAgent") { x = 200; y = 335; }
                  else if (agent.id === "RecoveryPlannerAgent") { x = 200; y = 430; }
                  else if (agent.id === "EscalationAgent") { x = 100; y = 520; }
                  else if (agent.id === "ReportGeneratorAgent") { x = 300; y = 520; }

                  const isCompleted = currentTimeline.some((t) => t.agent_name === agent.id);
                  const isActive = currentActiveAgent === agent.id;
                  let nodeClass = "queued";
                  if (isActive) nodeClass = "running";
                  else if (isCompleted) nodeClass = "completed";

                  return (
                    <g key={agent.id} className={`agent-node ${nodeClass}`} transform={`translate(${x - 60}, ${y - 25})`}>
                      <rect width="120" height="46" rx="8" strokeWidth="1.5" fill="rgba(7, 12, 26, 0.85)" />
                      <text x="60" y="22" textAnchor="middle" fill="#fff" fontSize="9.5" fontWeight="bold" fontFamily="var(--font-sans)">
                        {agent.label} {agentDurations[agent.id] ? `(${agentDurations[agent.id]}ms)` : ""}
                      </text>
                      <text x="60" y="36" textAnchor="middle" fill="var(--text-secondary)" fontSize="9" fontFamily="var(--font-mono)">
                        {nodeClass.toUpperCase()}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </div>

          {/* SRE Agent Reasoning Debate Panel */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px", border: "1px solid rgba(139, 92, 246, 0.2)", background: "rgba(139, 92, 246, 0.01)" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, color: "var(--color-purple)", display: "flex", alignItems: "center", gap: "8px" }}>
              <Radio size={16} />
              <span>AI Multi-Agent Debate Logic Stream</span>
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", background: "rgba(0,0,0,0.2)", padding: "14px", borderRadius: "10px" }}>
              <div style={{ fontSize: "0.85rem", borderBottom: "1px solid rgba(255,255,255,0.03)", paddingBottom: "6px" }}>
                <span style={{ color: "var(--color-purple)", fontWeight: "bold" }}>Root Cause Agent</span>: 
                <span style={{ color: "#fff" }}> "I think Redis connection pool exhaustion is causing checkout-api high latencies (71% confidence)."</span>
              </div>
              
              {currentConfidence >= 78 && (
                <div style={{ fontSize: "0.85rem", borderBottom: "1px solid rgba(255,255,255,0.03)", paddingBottom: "6px" }}>
                  <span style={{ color: "var(--color-amber)", fontWeight: "bold" }}>Evaluator Agent</span>: 
                  <span style={{ color: "#cbd5e1" }}> "Counterargument: What about checkout-db latency? Ping checks to DB pool show utilization at 98% (63% confidence)."</span>
                </div>
              )}

              {currentConfidence >= 88 && (
                <div style={{ fontSize: "0.85rem" }}>
                  <span style={{ color: "var(--color-purple)", fontWeight: "bold" }}>Root Cause Agent</span>: 
                  <span style={{ color: "var(--color-emerald)" }}> "Rejecting counterargument. DB ping response is 2ms (healthy). Confirming Redis connection pool leak as origin. Final confidence: 96%."</span>
                </div>
              )}
            </div>
          </div>

          {/* SRE Reasoning Timeline Log */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Terminal size={16} style={{ color: "var(--color-blue)" }} />
              <span>AI Reasoning Timeline Logger</span>
            </h3>

            <div className="log-stream-terminal" ref={logTerminalRef}>
              {currentTimeline.length === 0 ? (
                <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                  Awaiting agent execution logs stream...
                </span>
              ) : (
                <>
                  {/* Timeline Map */}
                  {currentTimeline.map((entry, idx) => (
                    <div className="log-entry" key={idx}>
                      <span className="log-time">[{new Date(entry.timestamp).toLocaleTimeString()}]</span>
                      <span className={`log-type ${entry.agent_name === "system" ? "created" : "agent-completed"}`}>
                        {entry.agent_name || entry.agent}
                      </span>
                      <span className="log-message">
                        <strong>{entry.action}</strong>: {entry.summary || ("message" in entry ? (entry as any).message : "")}
                        {entry.confidence > 0 && ` (confidence: ${entry.confidence}%)`}
                        {entry.duration_ms > 0 && ` [duration: ${entry.duration_ms}ms]`}
                      </span>
                    </div>
                  ))}
                  {replayMode && currentLogs[replayStep] && (
                    <div className="log-entry" style={{ borderLeft: "2px solid var(--color-purple)", paddingLeft: "6px" }}>
                      <span className="log-time">[{new Date().toLocaleTimeString()}]</span>
                      <span className="log-type agent-started" style={{ color: "var(--color-purple)" }}>
                        REPLAY LOG
                      </span>
                      <span className="log-message" style={{ color: "#fff" }}>
                        {currentLogs[replayStep]}
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

        </div>

        {/* Right Columns: Memory, Approval Gates, MCP Telemetry, Report */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* AI Past Incidents Memory */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <ShieldCheck size={16} style={{ color: "var(--color-emerald)" }} />
              <span>AI Historical Memory Cache</span>
            </h3>

            <div style={{ background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.15)", borderRadius: "8px", padding: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#fff" }}>INC-1842 Match</span>
                <span style={{ fontSize: "0.75rem", color: "var(--color-emerald)", fontWeight: "bold" }}>92% Similarity</span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", margin: "4px 0" }}>
                Title: connection pool leak checkout-api. Resolved May 2026.
              </p>
              <div style={{ fontSize: "0.7rem", color: "var(--color-emerald)", fontWeight: "bold", borderTop: "1px solid rgba(16,185,129,0.1)", paddingTop: "4px" }}>
                RECOMMENDED ACTION: ROLLBACK/RESTART (APPLIED)
              </div>
            </div>
          </div>

          {/* SRE Human Approval Gate */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px", border: "1px solid rgba(59, 130, 246, 0.2)" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, color: "var(--color-blue)", display: "flex", alignItems: "center", gap: "8px" }}>
              <Clock size={16} />
              <span>SRE Mitigation Control Gate</span>
            </h3>
            
            <div style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.02)" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Proposed Plan: Restart checkout-api</div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                <span>Risk Level: LOW</span>
                <span>Rollback supported: YES</span>
              </div>
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <button className="btn btn-primary" style={{ flexGrow: 1, padding: "6px 12px", fontSize: "0.8rem" }}>
                Approve Action
              </button>
              <button className="btn" style={{ flexGrow: 1, padding: "6px 12px", fontSize: "0.8rem" }}>
                Reject
              </button>
            </div>
          </div>

          {/* Detailed MCP Servers Telemetry */}
          <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <Database size={16} style={{ color: "var(--color-emerald)" }} />
              <span>MCP Tool Server Registry</span>
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid rgba(255,255,255,0.03)", borderRadius: "8px", padding: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Monitoring MCP Server</span>
                  <span style={{ fontSize: "0.7rem", color: "var(--color-emerald)", fontWeight: "bold" }}>● CONNECTED</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", fontSize: "0.7rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                  <span>Latency: 278ms</span>
                  <span>Requests: 41</span>
                </div>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "4px", borderTop: "1px solid rgba(255,255,255,0.02)", paddingTop: "4px" }}>
                  Active Tools: query_logs(), query_metrics(), get_topology()
                </div>
              </div>

              <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid rgba(255,255,255,0.03)", borderRadius: "8px", padding: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#fff" }}>Incident MCP Server</span>
                  <span style={{ fontSize: "0.7rem", color: "var(--color-emerald)", fontWeight: "bold" }}>● CONNECTED</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", fontSize: "0.7rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                  <span>Latency: 350ms</span>
                  <span>Requests: 18</span>
                </div>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "4px", borderTop: "1px solid rgba(255,255,255,0.02)", paddingTop: "4px" }}>
                  Active Tools: trigger_restart(), apply_rollback()
                </div>
              </div>
            </div>
          </div>

          {/* SRE Case Post-Mortem Tabbed View */}
          {report && (
            <div className="mc-panel" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <FileText size={16} style={{ color: "var(--color-purple)" }} />
                <span>AI SRE Post-Mortem Report</span>
              </h3>

              {/* Tab Selector */}
              <div style={{ display: "flex", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                {["summary", "timeline", "rca", "lessons"].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`tab-button ${activeTab === tab ? "active" : ""}`}
                    style={{ textTransform: "capitalize" }}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="postmortem-container" style={{ padding: "14px" }}>
                {activeTab === "summary" && (
                  <div>
                    <h3 style={{ fontSize: "0.95rem", marginTop: 0 }}>Executive Summary</h3>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                      {report.stakeholder_update || "Incident detected and resolved successfully."}
                    </p>
                  </div>
                )}
                {activeTab === "timeline" && (
                  <div>
                    <h3 style={{ fontSize: "0.95rem", marginTop: 0 }}>Chronology</h3>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                      SRE Copilot initiated ADK multi-agent workflow at 12:40:01. Triage classified incident severity as P0. Recovery executed rollback actions in 90 seconds.
                    </p>
                  </div>
                )}
                {activeTab === "rca" && (
                  <div>
                    <h3 style={{ fontSize: "0.95rem", marginTop: 0 }}>Root Cause Analysis</h3>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                      Redis connection leak caused pool overflow. The checkout-api failed database transactions, propagating 500 server errors downstream.
                    </p>
                  </div>
                )}
                {activeTab === "lessons" && (
                  <div>
                    <h3 style={{ fontSize: "0.95rem", marginTop: 0 }}>Mitigations & Lessons</h3>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                      Configure connection leak detection in redis-cache pool. Establish metric alerts for active evicted keys in Prometheus stack.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>

      </div>

    </motion.div>
  );
};
