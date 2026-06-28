#!/usr/bin/env python3
"""Programmatically generates 10 scalable vector graphic (SVG) diagrams for repository documentation."""

import os

SVG_DIR = (
    r"c:\Users\gadam\OneDrive\Desktop\Capstone project\ai-sre-copilot\docs\diagrams"
)
os.makedirs(SVG_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# SVG HELPER CLASSES & FUNCTIONS
# ---------------------------------------------------------------------------


class SVGCanvas:
    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height
        self.title = title
        self.elements = []
        self._defs = []
        self._setup_defs()

    def _setup_defs(self):
        # Drop shadow filter
        self._defs.append("""
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
        <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000000" flood-opacity="0.06" />
    </filter>
""")
        self._defs.append("""
    <filter id="shadow-sm" x="-5%" y="-5%" width="110%" height="110%">
        <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.04" />
    </filter>
""")
        # Gradients
        self._defs.append("""
    <linearGradient id="grad-blue" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#3B82F6" />
        <stop offset="100%" stop-color="#1D4ED8" />
    </linearGradient>
""")
        self._defs.append("""
    <linearGradient id="grad-purple" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#8B5CF6" />
        <stop offset="100%" stop-color="#6D28D9" />
    </linearGradient>
""")
        self._defs.append("""
    <linearGradient id="grad-orange" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#F59E0B" />
        <stop offset="100%" stop-color="#D97706" />
    </linearGradient>
""")
        self._defs.append("""
    <linearGradient id="grad-green" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#10B981" />
        <stop offset="100%" stop-color="#047857" />
    </linearGradient>
""")
        self._defs.append("""
    <linearGradient id="grad-gray" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#6B7280" />
        <stop offset="100%" stop-color="#374151" />
    </linearGradient>
""")
        self._defs.append("""
    <linearGradient id="grad-red" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#EF4444" />
        <stop offset="100%" stop-color="#B91C1C" />
    </linearGradient>
""")
        self._defs.append("""
    <linearGradient id="grad-light-blue" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#EFF6FF" />
        <stop offset="100%" stop-color="#DBEAFE" />
    </linearGradient>
""")
        # Arrow marker
        self._defs.append("""
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#4B5563" />
    </marker>
""")
        self._defs.append("""
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#2563EB" />
    </marker>
""")

    def add_card(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        subtitle: str = "",
        fill_grad: str = "grad-blue",
        is_dark: bool = True,
    ):
        border_col = "none"
        text_col = "#FFFFFF" if is_dark else "#1E293B"
        sub_col = "#E2E8F0" if is_dark else "#64748B"

        self.elements.append(f"""
    <!-- Card: {title} -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="url(#{fill_grad})" stroke="{border_col}" stroke-width="1.5" filter="url(#shadow)" />
""")

        if subtitle:
            # Multi-line card
            self.elements.append(f"""
    <text x="{x + 16}" y="{y + h//2 - 4}" font-family="'Inter', sans-serif" font-weight="bold" font-size="14" fill="{text_col}">{title}</text>
    <text x="{x + 16}" y="{y + h//2 + 16}" font-family="'Inter', sans-serif" font-size="12" fill="{sub_col}">{subtitle}</text>
""")
        else:
            # Single-line card (centered title)
            self.elements.append(f"""
    <text x="{x + w//2}" y="{y + h//2 + 5}" font-family="'Inter', sans-serif" font-weight="bold" font-size="14" fill="{text_col}" text-anchor="middle">{title}</text>
""")

    def add_subcard(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        subtitle: str = "",
        border_color: str = "#E2E8F0",
        fill_color: str = "#FFFFFF",
    ):
        self.elements.append(f"""
    <!-- Subcard: {title} -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill_color}" stroke="{border_color}" stroke-width="1" filter="url(#shadow-sm)" />
""")
        if subtitle:
            self.elements.append(f"""
    <text x="{x + 12}" y="{y + h//2 - 2}" font-family="'Inter', sans-serif" font-weight="bold" font-size="12" fill="#1E293B">{title}</text>
    <text x="{x + 12}" y="{y + h//2 + 14}" font-family="'Inter', sans-serif" font-size="10.5" fill="#64748B">{subtitle}</text>
""")
        else:
            self.elements.append(f"""
    <text x="{x + w//2}" y="{y + h//2 + 4}" font-family="'Inter', sans-serif" font-weight="bold" font-size="12" fill="#1E293B" text-anchor="middle">{title}</text>
""")

    def add_arrow(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        label: str = "",
        color: str = "#4B5563",
        stroke_dash: str = "",
        marker: str = "arrow",
    ):
        self.elements.append(f"""
    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" stroke-dasharray="{stroke_dash}" marker-end="url(#{marker})" />
""")
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self.elements.append(f"""
    <text x="{mx}" y="{my - 6}" font-family="'Inter', sans-serif" font-size="11" fill="{color}" font-weight="bold" text-anchor="middle">{label}</text>
""")

    def add_curved_arrow(
        self,
        path_d: str,
        label: str = "",
        color: str = "#4B5563",
        stroke_dash: str = "",
        marker: str = "arrow",
        label_x: int = 0,
        label_y: int = 0,
    ):
        self.elements.append(f"""
    <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{stroke_dash}" marker-end="url(#{marker})" />
""")
        if label and label_x and label_y:
            self.elements.append(f"""
    <text x="{label_x}" y="{label_y}" font-family="'Inter', sans-serif" font-size="11" fill="{color}" font-weight="bold" text-anchor="middle">{label}</text>
""")

    def add_label(
        self,
        x: int,
        y: int,
        text: str,
        font_size: int = 14,
        font_weight: str = "bold",
        color: str = "#1E293B",
        text_anchor: str = "start",
    ):
        self.elements.append(f"""
    <text x="{x}" y="{y}" font-family="'Inter', sans-serif" font-weight="{font_weight}" font-size="{font_size}" fill="{color}" text-anchor="{text_anchor}">{text}</text>
""")

    def add_group_boundary(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        label: str,
        fill_color: str = "#F8FAFC",
        border_color: str = "#CBD5E1",
    ):
        self.elements.append(f"""
    <!-- Group Boundary: {label} -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill_color}" stroke="{border_color}" stroke-dasharray="4,4" stroke-width="1.5" />
    <rect x="{x + 16}" y="{y - 10}" width="{len(label)*8 + 16}" height="20" rx="6" fill="#FFFFFF" stroke="{border_color}" stroke-width="1" />
    <text x="{x + 24}" y="{y + 4}" font-family="'Inter', sans-serif" font-weight="bold" font-size="11" fill="#475569">{label}</text>
""")

    def build_xml(self) -> str:
        defs_str = "\n".join(self._defs)
        elements_str = "\n".join(self.elements)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="100%" height="100%">
    <defs>
        {defs_str}
    </defs>

    <!-- Background Canvas -->
    <rect width="{self.width}" height="{self.height}" fill="#FFFFFF" />
    <rect width="{self.width}" height="{self.height}" fill="#F1F5F9" opacity="0.4" />

    {elements_str}
</svg>"""

    def save(self, filename: str):
        filepath = os.path.join(SVG_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.build_xml())
        print(f"Generated diagram: {filename}")


# ---------------------------------------------------------------------------
# DIAGRAM GENERATORS
# ---------------------------------------------------------------------------


def generate_system_architecture():
    c = SVGCanvas(1000, 700, "System Architecture")

    # Boundary Groups
    c.add_group_boundary(30, 80, 240, 560, "USER INTERFACE")
    c.add_group_boundary(290, 80, 240, 560, "API & EVENT GATEWAY")
    c.add_group_boundary(550, 80, 420, 560, "GOOGLE ADK AGENT ORCHESTRATION")

    # Nodes in UI
    c.add_card(
        50, 140, 200, 70, "React Dashboard", "DD-style UI Widget Suite", "grad-blue"
    )
    c.add_card(
        50,
        320,
        200,
        70,
        "Action Console",
        "Firing alert simulation / override",
        "grad-blue",
    )
    c.add_card(
        50,
        480,
        200,
        70,
        "Reasoning Timeline",
        "Live-scrolling terminal feed",
        "grad-blue",
    )

    # Nodes in Gateway
    c.add_card(
        310, 140, 200, 70, "FastAPI Gateway", "API routing & WS handling", "grad-purple"
    )
    c.add_card(
        310,
        280,
        200,
        70,
        "WebSocket Manager",
        "Real-time updates router",
        "grad-purple",
    )
    c.add_card(
        310, 400, 200, 70, "Event Bus Bridge", "Internal Event broker", "grad-purple"
    )
    c.add_card(
        310, 520, 200, 70, "Persistence Store", "JSON Case-File Store", "grad-gray"
    )

    # Nodes in Agent / Engine
    c.add_card(
        580,
        140,
        360,
        70,
        "ADK Workflow Orchestrator",
        "Initializes case files & controls workflow",
        "grad-red",
    )

    c.add_group_boundary(575, 235, 370, 255, "8 SPECIALIZED COOPERATIVE AGENTS")
    c.add_subcard(590, 270, 160, 45, "Intake Agent", "Alert triage & sanity check")
    c.add_subcard(765, 270, 160, 45, "Triage Agent", "Impact & severity categorization")
    c.add_subcard(590, 330, 160, 45, "Log Analyzer", "Pattern recognition & errors")
    c.add_subcard(765, 330, 160, 45, "Root Cause Agent", "Hypothesis testing")
    c.add_subcard(590, 390, 160, 45, "Evaluator Agent", "Verification & checks")
    c.add_subcard(765, 390, 160, 45, "Recovery Planner", "Action roadmap creation")
    c.add_subcard(590, 440, 160, 40, "Escalation Agent", "PagerDuty integration")
    c.add_subcard(765, 440, 160, 40, "Report Generator", "JSON & MD post-mortem")

    c.add_card(
        580,
        520,
        360,
        70,
        "MCP Tool Registry",
        "Monitoring & Incident MCP Toolkits",
        "grad-green",
    )

    # Arrows
    c.add_arrow(150, 210, 150, 320, "", "#4B5563")
    c.add_arrow(250, 175, 310, 175, "REST Requests", "#3B82F6")
    c.add_arrow(310, 315, 250, 315, "WebSocket Push", "#10B981")
    c.add_arrow(510, 175, 580, 175, "Execute Workflow", "#8B5CF6")

    c.add_arrow(760, 210, 760, 270, "Spawn", "#EF4444")
    c.add_arrow(760, 495, 760, 520, "Call Tools", "#10B981")
    c.add_arrow(580, 555, 510, 555, "Data", "#10B981")
    c.add_arrow(410, 470, 410, 520, "", "#6B7280")
    c.add_arrow(410, 350, 410, 400, "", "#6B7280")

    c.save("system_architecture.svg")


def generate_adk_agent_workflow():
    c = SVGCanvas(900, 720, "Google ADK Agent Workflow")

    c.add_label(30, 40, "GOOGLE ADK MULTI-AGENT INCIDENT LIFECYCLE WORKFLOW", 16)

    # Grid of Agent stages
    c.add_card(
        50, 90, 180, 60, "1. Alert Ingestion", "Web Hook / Simulator", "grad-gray"
    )
    c.add_card(
        270, 90, 180, 60, "2. Intake Agent", "Sanity filter & validation", "grad-orange"
    )
    c.add_card(
        490, 90, 180, 60, "3. Coordinator", "ADK Orchestration Engine", "grad-red"
    )

    c.add_card(
        490,
        210,
        180,
        60,
        "4. Triage Agent",
        "Incident severity & impact",
        "grad-orange",
    )
    c.add_card(
        270, 210, 180, 60, "5. Log Analyzer", "Log tailing & extraction", "grad-orange"
    )
    c.add_card(
        50, 210, 180, 60, "6. Root Cause Agent", "Heuristic deduction", "grad-orange"
    )

    c.add_card(
        50,
        330,
        180,
        60,
        "7. Evaluator Agent",
        "Verify hypothesis/health",
        "grad-orange",
    )
    c.add_card(
        270,
        330,
        180,
        60,
        "8. Recovery Planner",
        "Suggest playbook runbook",
        "grad-orange",
    )
    c.add_card(
        490,
        330,
        180,
        60,
        "9. Escalation Agent",
        "Alert stakeholder/pager",
        "grad-orange",
    )

    c.add_card(
        490, 450, 180, 60, "10. Report Generator", "Generate post-mortem", "grad-orange"
    )
    c.add_card(
        270, 450, 180, 60, "11. Incident Closed", "Archive Case File", "grad-green"
    )

    # Loops
    c.add_group_boundary(
        690,
        90,
        180,
        420,
        "MITIGATION LOOP",
        fill_color="#FEF3C7",
        border_color="#F59E0B",
    )
    c.add_card(700, 130, 160, 80, "Manual Approval", "Wait for human OK", "grad-purple")
    c.add_card(
        700, 250, 160, 80, "Mitigation Agent", "Execute rollback / fix", "grad-orange"
    )
    c.add_card(
        700, 370, 160, 80, "Verification Run", "Assert health metrics", "grad-gray"
    )

    # Connection lines
    c.add_arrow(230, 120, 270, 120, "", "#4B5563")
    c.add_arrow(450, 120, 490, 120, "", "#4B5563")
    c.add_arrow(580, 150, 580, 210, "", "#4B5563")
    c.add_arrow(490, 240, 450, 240, "", "#4B5563")
    c.add_arrow(270, 240, 230, 240, "", "#4B5563")
    c.add_arrow(140, 270, 140, 330, "", "#4B5563")
    c.add_arrow(230, 360, 270, 360, "", "#4B5563")
    c.add_arrow(450, 360, 490, 360, "", "#4B5563")
    c.add_arrow(580, 390, 580, 450, "", "#4B5563")
    c.add_arrow(490, 480, 450, 480, "", "#4B5563")

    # Loop arrows
    c.add_arrow(360, 330, 700, 170, "Request", "#8B5CF6", stroke_dash="2,2")
    c.add_arrow(780, 210, 780, 250, "Approve", "#10B981")
    c.add_arrow(780, 330, 780, 370, "Run Fix", "#10B981")
    c.add_arrow(700, 410, 360, 450, "Healthy", "#10B981")

    c.save("adk_agent_workflow.svg")


def generate_mcp_architecture():
    c = SVGCanvas(900, 600, "MCP Architecture")

    c.add_label(30, 40, "MODEL CONTEXT PROTOCOL (MCP) INTERFACE ARCHITECTURE", 16)

    c.add_group_boundary(40, 90, 250, 440, "GOOGLE ADK AGENTS (CLIENTS)")
    c.add_card(
        60, 150, 210, 70, "Log Analyzer Agent", "Reads logs through MCP", "grad-orange"
    )
    c.add_card(
        60, 250, 210, 70, "Evaluator Agent", "Checks health endpoints", "grad-orange"
    )
    c.add_card(
        60, 350, 210, 70, "Recovery Planner", "Runs runbook mitigations", "grad-orange"
    )

    c.add_card(
        340,
        240,
        200,
        80,
        "MCP Tool Registry\n(Protocol Layer)",
        "JSON-RPC over STDIO/HTTP",
        "grad-purple",
    )

    c.add_group_boundary(590, 90, 270, 440, "DECOUPLED MCP SERVERS")
    c.add_card(
        610,
        130,
        230,
        80,
        "Monitoring MCP Server",
        "Exposes metrics & telemetry",
        "grad-green",
    )
    c.add_subcard(630, 220, 190, 40, "Prometheus / Logs API", "Data resource access")

    c.add_card(
        610,
        310,
        230,
        80,
        "Incident MCP Server",
        "Exposes topology & action tools",
        "grad-green",
    )
    c.add_subcard(
        630, 400, 190, 40, "System Actions tool", "Docker & database API tools"
    )

    # Connectors
    c.add_arrow(270, 185, 340, 260, "", "#4B5563")
    c.add_arrow(270, 285, 340, 285, "", "#4B5563")
    c.add_arrow(270, 385, 340, 300, "", "#4B5563")

    c.add_arrow(540, 270, 610, 180, "Standardized JSON-RPC", "#8B5CF6")
    c.add_arrow(540, 290, 610, 360, "Standardized JSON-RPC", "#8B5CF6")

    c.save("mcp_architecture.svg")


def generate_sequence_diagram():
    c = SVGCanvas(950, 650, "Sequence Diagram")

    c.add_label(30, 40, "COOPERATIVE SRE INCIDENT RESOLUTION SEQUENCE DIAGRAM", 16)

    # Participants
    participants = [
        ("User", 100),
        ("Dashboard", 220),
        ("FastAPI", 360),
        ("Orchestrator", 500),
        ("Agents (ADK)", 660),
        ("MCP Servers", 820),
    ]

    for name, x in participants:
        c.elements.append(f"""
    <!-- Participant Line: {name} -->
    <line x1="{x}" y1="80" x2="{x}" y2="580" stroke="#CBD5E1" stroke-width="2" stroke-dasharray="4,4" />
    <rect x="{x - 50}" y="80" width="100" height="36" rx="6" fill="#1E293B" filter="url(#shadow-sm)" />
    <text x="{x}" y="103" font-family="'Inter', sans-serif" font-weight="bold" font-size="12" fill="#FFFFFF" text-anchor="middle">{name}</text>
""")

    # Interactions
    interactions = [
        (100, 220, 140, "Simulate Alert"),
        (220, 360, 180, "POST /api/incidents"),
        (360, 500, 220, "Trigger execute_workflow"),
        (500, 660, 260, "Initialize ADK Agents"),
        (660, 820, 300, "Call MCP Tools (e.g. read logs)"),
        (820, 660, 350, "JSON-RPC Response"),
        (660, 500, 400, "Yield execution progress event"),
        (500, 360, 440, "Publish to Event Bus"),
        (360, 220, 480, "WebSocket Event Broadcast"),
        (220, 100, 520, "Visual Notification on UI"),
    ]

    for x1, x2, y, label in interactions:
        marker = "arrow-blue" if x2 > x1 else "arrow"
        color = "#2563EB" if x2 > x1 else "#4B5563"
        c.add_arrow(x1, y, x2, y, label, color, marker=marker)

    c.save("sequence_diagram.svg")


def generate_incident_lifecycle():
    c = SVGCanvas(900, 600, "Incident Lifecycle")

    c.add_label(30, 40, "STATE TRANSITION DIAGRAM & ESCALATION LIFECYCLE", 16)

    # State boxes
    c.add_card(60, 100, 160, 60, "NEW", "Incident registered", "grad-blue")
    c.add_arrow(220, 130, 280, 130, "Intake", "#4B5563")

    c.add_card(280, 100, 160, 60, "TRIAGED", "Severity assessed", "grad-orange")
    c.add_arrow(440, 130, 500, 130, "Investigation", "#4B5563")

    c.add_card(500, 100, 160, 60, "INVESTIGATING", "Log analysis active", "grad-orange")
    c.add_arrow(660, 130, 720, 130, "Deduction", "#4B5563")

    c.add_card(720, 100, 160, 60, "ROOT CAUSE", "Origin verified", "grad-orange")

    # Line down
    c.add_arrow(800, 160, 800, 240, "Propose Fix", "#4B5563")

    c.add_card(720, 240, 160, 60, "EVALUATING", "Impact evaluated", "grad-orange")
    c.add_arrow(720, 270, 660, 270, "Actionable?", "#4B5563")

    c.add_card(500, 240, 160, 60, "MITIGATING", "Playbook run", "grad-orange")
    c.add_arrow(500, 270, 440, 270, "Verify", "#4B5563")

    c.add_card(280, 240, 160, 60, "RESOLVED", "Metric healthy", "grad-green")
    c.add_arrow(280, 270, 220, 270, "Close", "#10B981")

    c.add_card(60, 240, 160, 60, "CLOSED", "Case post-mortem done", "grad-gray")

    # Escalation path
    c.add_group_boundary(
        220,
        360,
        440,
        180,
        "ESCALATION BYPASS",
        fill_color="#FEE2E2",
        border_color="#EF4444",
    )
    c.add_card(
        250, 420, 160, 60, "PENDING APPROVAL", "Manual gate active", "grad-purple"
    )
    c.add_card(470, 420, 160, 60, "ESCALATED", "Paged human operator", "grad-red")

    # Curved arrows for escalation
    c.add_curved_arrow(
        "M 580 160 C 580 320, 330 320, 330 420",
        "Requires Approval",
        "#EF4444",
        stroke_dash="2,2",
        label_x=450,
        label_y=350,
    )
    c.add_curved_arrow(
        "M 330 480 C 330 520, 580 520, 580 300",
        "Approved",
        "#10B981",
        label_x=450,
        label_y=510,
    )
    c.add_arrow(410, 450, 470, 450, "Timeout / Denied", "#EF4444")

    c.save("incident_lifecycle.svg")


def generate_security_pipeline():
    c = SVGCanvas(950, 550, "Security Pipeline")

    c.add_label(30, 40, "GATEWAY 5-STAGE PIPELINE & TRUST BOUNDARIES", 16)

    # Trust boundary
    c.add_group_boundary(
        20, 90, 180, 380, "UNTRUSTED ZONE", fill_color="#FFF1F2", border_color="#FDA4AF"
    )
    c.add_label(30, 120, "External Inputs", 12, "bold", "#991B1B")
    c.add_card(
        30,
        170,
        160,
        70,
        "Webhook Payload\n(Alert Data)",
        "REST JSON Ingestion",
        "grad-red",
    )
    c.add_card(
        30,
        300,
        160,
        70,
        "WebSocket Feed\n(Client Commands)",
        "Pong & Controls",
        "grad-red",
    )

    # Trust Line
    c.elements.append(
        '<line x1="210" y1="90" x2="210" y2="470" stroke="#EF4444" stroke-width="3" stroke-dasharray="6,4" />'
    )
    c.add_label(220, 110, "TRUST BOUNDARY / GATEWAY FIREWALL", 11, "bold", "#EF4444")

    # Security pipeline nodes
    c.add_card(
        240, 140, 150, 60, "1. Rate Limiter", "Per-IP Sliding Window", "grad-purple"
    )
    c.add_card(
        410, 140, 150, 60, "2. DTO Validation", "Pydantic Schemas", "grad-purple"
    )
    c.add_card(
        580,
        140,
        150,
        60,
        "3. LLM Injection Det.",
        "3-Layer prompt check",
        "grad-purple",
    )
    c.add_card(
        750, 140, 150, 60, "4. Tool Firewall", "MCP request audit", "grad-purple"
    )

    c.add_card(
        490, 270, 170, 70, "5. Audit Logger", "Hash-chained security log", "grad-gray"
    )

    # Trusted execution zone
    c.add_group_boundary(
        240,
        370,
        660,
        140,
        "TRUSTED COGNITIVE EXECUTION ZONE (offline / sanitized)",
        fill_color="#ECFDF5",
        border_color="#6EE7B7",
    )
    c.add_subcard(
        260, 420, 180, 50, "Google ADK Orchestrator", "Multi-Agent Workflow Engine"
    )
    c.add_subcard(480, 420, 180, 50, "MCP Registry", "Tool access execution")
    c.add_subcard(
        700, 420, 180, 50, "JSON Incident Store", "Secured filesystem storage"
    )

    # Connectors
    c.add_arrow(190, 200, 240, 170, "", "#4B5563")
    c.add_arrow(190, 310, 240, 180, "", "#4B5563")
    c.add_arrow(390, 170, 410, 170, "", "#4B5563")
    c.add_arrow(560, 170, 580, 170, "", "#4B5563")
    c.add_arrow(730, 170, 750, 170, "", "#4B5563")

    c.add_arrow(825, 200, 825, 370, "Execute", "#10B981")
    c.add_arrow(580, 270, 580, 200, "Log Block", "#EF4444", stroke_dash="2,2")

    c.save("security_pipeline.svg")


def generate_event_bus_architecture():
    c = SVGCanvas(900, 500, "Event Bus Architecture")

    c.add_label(30, 40, "PUB-SUB EVENT BROKER & REAL-TIME WS STREAMING", 16)

    c.add_group_boundary(40, 90, 220, 360, "EVENT PRODUCERS")
    c.add_card(60, 150, 180, 60, "Intake Agent", "INCIDENT_CREATED", "grad-orange")
    c.add_card(
        60, 240, 180, 60, "Root Cause Agent", "ROOT_CAUSE_DETECTED", "grad-orange"
    )
    c.add_card(60, 330, 180, 60, "Report Generator", "REPORT_GENERATED", "grad-orange")

    c.add_card(
        320,
        210,
        220,
        100,
        "Internal Event Bus\n(Pub-Sub Broker)",
        "Synchronous memory dispatch",
        "grad-purple",
    )

    c.add_group_boundary(600, 90, 250, 360, "EVENT CONSUMERS")
    c.add_card(
        620,
        140,
        210,
        60,
        "WebSocket Bridge",
        "Broadcasts events to clients",
        "grad-blue",
    )
    c.add_card(
        620,
        240,
        210,
        60,
        "Audit Trail Logger",
        "Saves events to audit.jsonl",
        "grad-gray",
    )
    c.add_card(
        620, 340, 210, 60, "Case File Timeline", "Appends visual logs", "grad-gray"
    )

    # Connectors
    c.add_arrow(240, 180, 320, 230, "", "#4B5563")
    c.add_arrow(240, 270, 320, 270, "", "#4B5563")
    c.add_arrow(240, 360, 320, 290, "", "#4B5563")

    c.add_arrow(540, 230, 620, 170, "", "#4B5563")
    c.add_arrow(540, 260, 620, 270, "", "#4B5563")
    c.add_arrow(540, 290, 620, 370, "", "#4B5563")

    c.save("event_bus_architecture.svg")


def generate_persistence_layer():
    c = SVGCanvas(900, 500, "Persistence Layer")

    c.add_label(30, 40, "STATE PERSISTENCE & CASE FILE SERIALIZATION", 16)

    c.add_card(
        50,
        180,
        180,
        90,
        "IncidentState\n(Pydantic Schema)",
        "Title, Description, Environment, Timeline, Status, Report",
        "grad-orange",
    )

    c.add_arrow(230, 225, 320, 225, "Serialize", "#4B5563")

    c.add_card(
        320,
        140,
        220,
        170,
        "JsonIncidentStore\n(Persistence Engine)",
        "Directory: data/incidents/\n\nMethods:\n- save()\n- update()\n- load()\n- delete()",
        "grad-purple",
    )

    c.add_arrow(540, 225, 630, 225, "Write to file", "#4B5563")

    c.add_card(
        630,
        180,
        220,
        90,
        "Filesystem / Storage\n(JSON files)",
        "INC-XXXXXXXX.json\n\nDemo: file-system isolation",
        "grad-gray",
    )

    c.save("persistence_layer.svg")


def generate_frontend_architecture():
    c = SVGCanvas(950, 550, "Frontend Architecture")

    c.add_label(30, 40, "REACT SINGLE PAGE APPLICATION ARCHITECTURE", 16)

    c.add_group_boundary(30, 90, 450, 400, "VIEW LAYER (REACT PAGES & COMPONENTS)")
    c.add_card(
        50, 140, 190, 65, "Dashboard (/)", "Incidents grid & statistics", "grad-blue"
    )
    c.add_card(
        260,
        140,
        190,
        65,
        "IncidentDetail (/incident/:id)",
        "Terminal feed & agent workflows",
        "grad-blue",
    )
    c.add_card(
        50,
        250,
        190,
        65,
        "SystemHealth (/health)",
        "Gateway readiness widgets",
        "grad-blue",
    )
    c.add_card(
        260,
        250,
        190,
        65,
        "SystemStream (/stream)",
        "Global event log viewer",
        "grad-blue",
    )
    c.add_subcard(
        50,
        350,
        400,
        110,
        "Premium SRE Stylesheet (mission_control.css)",
        "Modern glassmorphism UI, vibrant dark mode palette, smooth gradients, grid alignments, micro-animations, Inter typography.",
    )

    c.add_group_boundary(520, 90, 390, 400, "SERVICE & TRANSPORT LAYER")
    c.add_card(
        540,
        150,
        350,
        80,
        "API Client (services/api.ts)",
        "REST requests via Fetch API",
        "grad-purple",
    )
    c.add_card(
        540,
        280,
        350,
        80,
        "WebSocket Connection Client",
        "Live event receiver & auto-reconnection",
        "grad-purple",
    )
    c.add_subcard(
        540, 400, 350, 60, "Event Dispatcher", "Updates local React states dynamically"
    )

    # Connectors
    c.add_arrow(450, 200, 540, 200, "REST calls", "#3B82F6")
    c.add_arrow(540, 320, 450, 320, "WebSocket stream", "#10B981")

    c.save("frontend_architecture.svg")


def generate_deployment_architecture():
    c = SVGCanvas(950, 550, "Deployment Architecture")

    c.add_label(30, 40, "LOCAL DEMO / KAGGLE SUBMISSION DEPLOYMENT MODEL", 16)

    c.add_group_boundary(30, 90, 250, 410, "CLIENT ZONE (BROWSER)")
    c.add_card(
        50, 160, 210, 80, "Browser Client", "Renders HTML5/CSS3/JS app", "grad-blue"
    )
    c.add_card(
        50, 310, 210, 80, "React Runtime", "Handles UI views & WebSocket", "grad-blue"
    )

    c.add_group_boundary(330, 90, 330, 410, "LOCAL GATEWAY HOST (PYTHON)")
    c.add_card(
        350,
        140,
        290,
        70,
        "Vite Dev Server (Port 5173)",
        "Serves compiled frontend bundle",
        "grad-purple",
    )
    c.add_card(
        350,
        260,
        290,
        70,
        "FastAPI / Uvicorn (Port 8000)",
        "Serves REST API and WebSockets",
        "grad-purple",
    )
    c.add_card(
        350,
        380,
        290,
        70,
        "MCP Servers (STDIO process)",
        "Pruned mock data & CLI tool execution",
        "grad-green",
    )

    c.add_group_boundary(700, 90, 220, 410, "EXTERNAL APIS")
    c.add_card(
        720,
        200,
        180,
        80,
        "Gemini API\n(Google GenAI SDK)",
        "Cognitive reasoning\n& plan evaluation",
        "grad-red",
    )
    c.add_card(
        720,
        340,
        180,
        80,
        "Local JSON DB\n(data/incidents/)",
        "Saves state to disk",
        "grad-gray",
    )

    # Connectors
    c.add_arrow(260, 200, 350, 175, "HTTP", "#3B82F6")
    c.add_arrow(260, 350, 350, 295, "REST / WS", "#3B82F6")

    c.add_arrow(640, 295, 720, 240, "GenAI Calls", "#EF4444")
    c.add_arrow(640, 305, 720, 380, "Disk writes", "#6B7280")
    c.add_arrow(495, 330, 495, 380, "Stdout stdio", "#10B981")

    c.save("deployment_architecture.svg")


# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating vector SVG diagrams inside docs/diagrams/ ...")
    generate_system_architecture()
    generate_adk_agent_workflow()
    generate_mcp_architecture()
    generate_sequence_diagram()
    generate_incident_lifecycle()
    generate_security_pipeline()
    generate_event_bus_architecture()
    generate_persistence_layer()
    generate_frontend_architecture()
    generate_deployment_architecture()
    print("All diagrams generated successfully.")
