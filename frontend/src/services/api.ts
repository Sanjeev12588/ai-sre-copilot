/**
 * API Service layer for AI SRE Copilot (Phase 7).
 * Interacts with FastAPI REST endpoints and establishes WebSockets.
 */

const protocol = window.location.protocol;
const host = window.location.host;

// Automatically route to port 8000 if running on Vite dev server (5173)
export const API_BASE = host.includes("5173")
  ? `${protocol}//localhost:8000/api/v1`
  : `${protocol}//${host}/api/v1`;

export const WS_BASE = host.includes("5173")
  ? "ws://localhost:8000/ws/incidents"
  : `${protocol === "https:" ? "wss:" : "ws:"}//${host}/ws/incidents`;

export interface TimelineEntry {
  timestamp: string;
  agent_name: string;
  agent?: string;
  event_type: string;
  action: string;
  summary: string;
  message?: string;
  confidence: number;
  tools_used: string[];
  duration_ms: number;
  entry_status: string;
}

export interface Incident {
  incident_id: string;
  title: string;
  description: string;
  status: string;
  severity: string;
  environment: string;
  assigned_team: string;
  recovery_status: string;
  verification_status: string;
  report_status: string;
  escalation_status: string;
  created_at: string;
  updated_at: string;
  summary: string;
  confidence: number;
  timeline: TimelineEntry[];
  metadata?: {
    request_id?: string;
    [key: string]: any;
  };
}

export interface PostMortemReport {
  incident_id: string;
  report: string;
  stakeholder_update: string;
  generated_at: string;
}

export interface ApiError {
  error_code: string;
  message: string;
  details?: any;
  request_id: string;
  timestamp: string;
}

/**
 * Fetch all incidents from persistence.
 */
export async function getIncidents(): Promise<Incident[]> {
  const res = await fetch(`${API_BASE}/incidents`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `Failed to fetch incidents (HTTP ${res.status})`);
  }
  return res.json();
}

/**
 * Fetch a single incident case file by ID.
 */
export async function getIncident(incidentId: string): Promise<Incident> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `Incident ${incidentId} not found`);
  }
  return res.json();
}

/**
 * Fetch the timeline audit logs for an incident.
 */
export async function getIncidentTimeline(incidentId: string): Promise<TimelineEntry[]> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/timeline`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "Failed to fetch timeline");
  }
  return res.json();
}

/**
 * Fetch the post-mortem report for an incident.
 */
export async function getIncidentReport(incidentId: string): Promise<PostMortemReport> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/report`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "Report not found or not generated yet");
  }
  return res.json();
}

/**
 * Create a new incident and trigger background SRE workflow.
 */
export async function createIncident(payload: {
  title?: string;
  description?: string;
  environment?: string;
  raw_alert: Record<string, any>;
}): Promise<Incident> {
  const res = await fetch(`${API_BASE}/incidents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "Failed to create incident");
  }
  return res.json();
}

/**
 * Fetch health status of the application gateway.
 */
export async function getHealth(): Promise<{ status: string; environment: string; timestamp: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

/**
 * Fetch readiness of the application gateway.
 */
export async function getReady(): Promise<{ status: string; persistence: string }> {
  const res = await fetch(`${API_BASE}/ready`);
  if (!res.ok) throw new Error("Gateway is not ready");
  return res.json();
}

export interface WsEventMessage {
  event_id: string;
  timestamp: string;
  event_type: string;
  incident_id: string;
  request_id: string;
  agent: string;
  status: string;
  payload: Record<string, any>;
}

/**
 * Setup WebSocket connection for real-time incident state streaming.
 */
export function connectIncidentWebSocket(
  incidentId: string,
  onMessage: (event: WsEventMessage) => void,
  onError?: (err: Event) => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/${incidentId}`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error("Malformed WebSocket message received:", e);
    }
  };

  if (onError) ws.onerror = onError;
  if (onClose) ws.onclose = onClose;

  return ws;
}
