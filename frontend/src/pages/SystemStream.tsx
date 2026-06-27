import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Radio, Filter, Eye } from "lucide-react";
import { getIncidents, type Incident } from "../services/api";

interface StreamEvent {
  incident_id: string;
  timestamp: string;
  agent: string;
  action: string;
  summary: string;
  event_type: string;
}

export const SystemStream: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [filterIncidentId, setFilterIncidentId] = useState<string>("all");
  const [filterEventType, setFilterEventType] = useState<string>("all");

  useEffect(() => {
    getIncidents()
      .then((data) => {
        setIncidents(data);

        // Compile all timeline entries across all incidents into a single timeline
        const allEvents: StreamEvent[] = [];
        data.forEach((inc) => {
          (inc.timeline || []).forEach((entry) => {
            allEvents.push({
              incident_id: inc.incident_id,
              timestamp: entry.timestamp,
              agent: entry.agent_name || entry.agent || "system",
              action: entry.action,
              summary: entry.summary || entry.message || "",
              event_type: entry.event_type,
            });
          });
        });

        // Sort chronologically descending
        allEvents.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        setEvents(allEvents);
      })
      .catch((err) => console.error("Failed to compile stream events:", err))
      .finally(() => setLoading(false));
  }, []);

  const filteredEvents = events.filter((ev) => {
    const matchInc = filterIncidentId === "all" || ev.incident_id === filterIncidentId;
    const matchType = filterEventType === "all" || ev.event_type.toLowerCase().includes(filterEventType.toLowerCase());
    return matchInc && matchType;
  });

  // Removed unused uniqueTypes extraction

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "24px", flexGrow: 1, overflowY: "auto" }}>

      {/* Overview Header */}
      <div className="mc-panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
            <Radio size={20} style={{ color: "var(--color-blue)" }} />
            <span>Global SRE Event Stream Logger</span>
          </h1>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            Aggregated audit log tracing events, tool executions, and state synchronizations across all active incidents.
          </p>
        </div>
        <div style={{ fontSize: "1.4rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-blue)" }}>
          {filteredEvents.length} <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: "normal" }}>events match</span>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="mc-panel" style={{ display: "flex", gap: "16px", padding: "12px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Filter size={16} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Filters:</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Incident ID</span>
          <select
            value={filterIncidentId}
            onChange={(e) => setFilterIncidentId(e.target.value)}
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: "6px",
              padding: "6px 12px",
              color: "#fff",
              outline: "none"
            }}
          >
            <option value="all">All Incidents</option>
            {incidents.map((inc) => (
              <option key={inc.incident_id} value={inc.incident_id}>
                {inc.incident_id} - {inc.title.substring(0, 20)}...
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Event Type</span>
          <select
            value={filterEventType}
            onChange={(e) => setFilterEventType(e.target.value)}
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: "6px",
              padding: "6px 12px",
              color: "#fff",
              outline: "none"
            }}
          >
            <option value="all">All Types</option>
            <option value="CREATED">CREATED (Incident Created)</option>
            <option value="UPDATED">UPDATED (Status updates / Tool calls)</option>
            <option value="COMPLETED">COMPLETED (Agent completed)</option>
            <option value="ERROR">ERROR (Agent errors)</option>
          </select>
        </div>
      </div>

      {/* Global logs grid */}
      <div className="mc-panel" style={{ flexGrow: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {loading ? (
          <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
            <span>Compiling global audit streams...</span>
          </div>
        ) : filteredEvents.length === 0 ? (
          <div style={{ display: "flex", flexGrow: 1, alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
            <span>No events found matching your filter criteria.</span>
          </div>
        ) : (
          <div style={{ overflowY: "auto", flexGrow: 1 }} className="log-stream-terminal">
            {filteredEvents.map((ev, index) => (
              <div
                className="log-entry"
                key={`${ev.incident_id}-${index}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "100px 120px 140px 140px 1fr 80px",
                  padding: "10px 0",
                  alignItems: "center"
                }}
              >
                <span className="log-time" style={{ fontSize: "0.8rem" }}>
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </span>

                <span style={{ fontFamily: "var(--font-mono)", fontWeight: "bold", color: "#3b82f6" }}>
                  {ev.incident_id}
                </span>

                <span style={{
                  color: ev.event_type.includes("ERROR") ? "var(--color-red)" : "var(--color-green)",
                  fontSize: "0.8rem",
                  fontWeight: "bold"
                }}>
                  {ev.event_type}
                </span>

                <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                  {ev.agent}
                </span>

                <span style={{ color: "#e2e8f0" }}>
                  <strong>{ev.action}</strong>: {ev.summary}
                </span>

                <Link to={`/incident/${ev.incident_id}`} className="btn" style={{ padding: "4px 8px", fontSize: "0.75rem", width: "fit-content", justifySelf: "end" }}>
                  <Eye size={12} />
                  <span>Inspect</span>
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
};
