import React, { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ShieldAlert, Radio, Server, Activity, Cpu, Database } from "lucide-react";
import { getHealth, getIncidents } from "../services/api";

export const Navbar: React.FC = () => {
  const [online, setOnline] = useState<boolean>(true);
  const [activeCount, setActiveCount] = useState<number>(0);
  const [wsStatus, setWsStatus] = useState<string>("Disconnected");
  const location = useLocation();

  const checkStatus = () => {
    // Check general API health
    getHealth()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));

    // Fetch incident list to compute active count
    getIncidents()
      .then((data) => {
        const count = data.filter(
          (i) => i.status !== "RESOLVED" && i.status !== "CLOSED"
        ).length;
        setActiveCount(count);
      })
      .catch(() => {});
  };

  useEffect(() => {
    checkStatus();
    const timer = setInterval(checkStatus, 10000);
    return () => clearInterval(timer);
  }, []);

  // Update WebSocket display based on route
  useEffect(() => {
    if (location.pathname.startsWith("/incident/")) {
      setWsStatus("Connected");
    } else {
      setWsStatus("Idle");
    }
  }, [location.pathname]);

  return (
    <header className="header">
      <div className="logo-section" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <NavLink to="/" style={{ display: "flex", alignItems: "center", gap: "12px", textDecoration: "none" }}>
          <div className="logo-icon" />
          <h1 className="logo-text" style={{ fontSize: "1.1rem", fontWeight: 800 }}>AI SRE Mission Control</h1>
        </NavLink>
      </div>

      <nav style={{ display: "flex", gap: "12px", alignItems: "center" }}>
        <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <ShieldAlert size={14} />
            <span>Incidents</span>
          </div>
        </NavLink>
        <NavLink to="/stream" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Radio size={14} />
            <span>Event Stream</span>
          </div>
        </NavLink>
        <NavLink to="/health" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Server size={14} />
            <span>Health Checks</span>
          </div>
        </NavLink>
      </nav>

      {/* Observability Telemetry Badges */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        {/* Active Incident Counter */}
        {activeCount > 0 && (
          <div
            className="status-badge"
            style={{
              background: "rgba(239, 68, 68, 0.12)",
              borderColor: "rgba(239, 68, 68, 0.25)",
              color: "var(--color-red)",
            }}
          >
            <ShieldAlert size={12} className="pulse-red" />
            <span>{activeCount} Firing Alerts</span>
          </div>
        )}

        {/* Gateway Status Badge */}
        <div
          className="status-badge"
          style={{
            background: online ? "rgba(16, 185, 129, 0.08)" : "rgba(239, 68, 68, 0.08)",
            borderColor: online ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
            color: online ? "var(--color-emerald)" : "var(--color-red)",
          }}
        >
          <span className={`status-dot active`} style={{ background: online ? "var(--color-emerald)" : "var(--color-red)" }} />
          <Database size={12} style={{ opacity: 0.8 }} />
          <span>API: {online ? "Healthy" : "Offline"}</span>
        </div>

        {/* Gemini Engine Status */}
        <div
          className="status-badge"
          style={{
            background: online ? "rgba(139, 92, 246, 0.08)" : "rgba(100, 116, 139, 0.08)",
            borderColor: online ? "rgba(139, 92, 246, 0.15)" : "rgba(100, 116, 139, 0.15)",
            color: online ? "var(--color-purple)" : "var(--text-secondary)",
          }}
        >
          <Cpu size={12} style={{ opacity: 0.8 }} />
          <span>Gemini: {online ? "Active" : "Offline"}</span>
        </div>

        {/* WS Stream Status */}
        <div
          className="status-badge"
          style={{
            background: wsStatus === "Connected" ? "rgba(59, 130, 246, 0.08)" : "rgba(100, 116, 139, 0.08)",
            borderColor: wsStatus === "Connected" ? "rgba(59, 130, 246, 0.15)" : "rgba(100, 116, 139, 0.15)",
            color: wsStatus === "Connected" ? "var(--color-blue)" : "var(--text-secondary)",
          }}
        >
          <Activity size={12} style={{ opacity: 0.8 }} />
          <span>WS: {wsStatus}</span>
        </div>
      </div>
    </header>
  );
};
