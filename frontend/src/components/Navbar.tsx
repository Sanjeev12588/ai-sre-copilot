import React, { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { ShieldAlert, Radio, Server } from "lucide-react";
import { getHealth } from "../services/api";

export const Navbar: React.FC = () => {
  const [online, setOnline] = useState<boolean>(true);

  // Poll health status to show in navbar header
  useEffect(() => {
    const check = () => {
      getHealth()
        .then(() => setOnline(true))
        .catch(() => setOnline(false));
    };
    check();
    const timer = setInterval(check, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="header">
      <div className="logo-section">
        <NavLink to="/" style={{ display: "flex", alignItems: "center", gap: "12px", textDecoration: "none" }}>
          <div className="logo-icon" />
          <h1 className="logo-text">AI SRE Mission Control</h1>
        </NavLink>
      </div>

      <nav style={{ display: "flex", gap: "16px", alignItems: "center" }}>
        <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <ShieldAlert size={16} />
            <span>Incidents</span>
          </div>
        </NavLink>
        <NavLink to="/stream" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Radio size={16} />
            <span>Event Stream</span>
          </div>
        </NavLink>
        <NavLink to="/health" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Server size={16} />
            <span>Health Checks</span>
          </div>
        </NavLink>
      </nav>

      <div className="status-badge" style={{
        background: online ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
        borderColor: online ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
        color: online ? "var(--color-green)" : "var(--color-red)"
      }}>
        <span className="status-dot" style={{
          background: online ? "var(--color-green)" : "var(--color-red)",
          boxShadow: online ? "0 0 8px var(--color-green)" : "0 0 8px var(--color-red)"
        }} />
        <span>{online ? "Gateway Online" : "Gateway Offline"}</span>
      </div>
    </header>
  );
};
