import { HashRouter as Router, Routes, Route } from "react-router-dom";
import "./css/styles.css";
import "./css/mission_control.css";
import { Navbar } from "./components/Navbar";
import { Dashboard } from "./pages/Dashboard";
import { IncidentDetail } from "./pages/IncidentDetail";
import { SystemStream } from "./pages/SystemStream";
import { SystemHealth } from "./pages/SystemHealth";

function App() {
  return (
    <Router>
      <div className="mission-control-container">
        {/* Observability Navbar Header */}
        <Navbar />

        {/* Dynamic Route Content Port */}
        <main style={{ flexGrow: 1, display: "flex", flexDirection: "column" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incident/:id" element={<IncidentDetail />} />
            <Route path="/stream" element={<SystemStream />} />
            <Route path="/health" element={<SystemHealth />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
