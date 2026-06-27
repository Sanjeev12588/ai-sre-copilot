"""Immutable Audit Logger with Hash-Chain Integrity — Phase 8 Security Hardening.

Writes a tamper-evident append-only JSONL audit trail using SHA-256 hash chaining:

    entry_hash_n = SHA256(entry_hash_(n-1) + json(current_entry))

This means:
  - Any modification to a historical entry invalidates all subsequent hashes
  - Judges/auditors can verify the chain integrity with a single pass
  - Provides a "tamper-evident" trail (not tamper-proof — that requires HSM)

Each audit entry includes:
  - request_id: API request trace ID
  - trace_id: Global system-flow ID (API → Agent → Tool → WS → UI)
  - incident_id: Associated incident
  - actor: Who performed the action (user/agent_name/system)
  - timestamp: ISO-8601 UTC
  - action: What happened (verb)
  - metadata: Contextual details
  - prev_hash: Hash of the previous entry
  - entry_hash: Hash of this entry (for chain verification)

Usage:
    from backend.security.audit_logger import audit_logger

    audit_logger.log_incident_created(
        request_id="req-abc",
        trace_id="trace-xyz",
        incident_id="INC-ABCD1234",
        actor="user",
        metadata={"environment": "production"},
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel hash for the very first entry (genesis block)
_GENESIS_HASH = "0" * 64


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Thread-safe append-only audit logger with SHA-256 hash chaining.

    File is created on first write. Directory is created if it does not exist.
    All writes are serialized with a lock to prevent concurrent corruption.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._lock = Lock()
        self._prev_hash: str = _GENESIS_HASH
        self._entry_count: int = 0
        self._log_dir: Path | None = None
        self._log_file: Path | None = None

        if log_dir:
            self._set_log_dir(log_dir)

    def _set_log_dir(self, log_dir: Path) -> None:
        """Initialize the log directory and file path."""
        self._log_dir = log_dir
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._log_file = log_dir / "audit.jsonl"
            # If file exists, load the last hash to maintain chain continuity
            self._prev_hash = self._load_last_hash()
            logger.info(
                "AuditLogger initialized | file=%s | prev_hash=%.16s...",
                self._log_file,
                self._prev_hash,
            )
        except Exception as exc:
            logger.error(
                "AuditLogger: Failed to initialize log dir %s: %s. "
                "Audit logging will be in-memory only.",
                log_dir,
                exc,
            )
            self._log_file = None

    def initialize(self, log_dir: Path) -> None:
        """Late initialization (called from lifespan after config is loaded)."""
        with self._lock:
            self._set_log_dir(log_dir)

    def _load_last_hash(self) -> str:
        """Read the last entry_hash from existing audit file to maintain chain."""
        if not self._log_file or not self._log_file.exists():
            return _GENESIS_HASH

        try:
            last_hash = _GENESIS_HASH
            with self._log_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        last_hash = entry.get("entry_hash", _GENESIS_HASH)
            return last_hash
        except Exception as exc:
            logger.warning("AuditLogger: Could not read previous hash: %s", exc)
            return _GENESIS_HASH

    def _compute_hash(self, prev_hash: str, entry: dict[str, Any]) -> str:
        """Compute SHA-256 hash of (prev_hash + JSON(entry)).

        Args:
            prev_hash: Hash of the previous audit entry.
            entry: Current audit entry dict (without entry_hash field).

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        entry_json = json.dumps(entry, sort_keys=True, default=str)
        chain_input = prev_hash + entry_json
        return hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    def _write_entry(
        self,
        action: str,
        actor: str,
        incident_id: str,
        request_id: str,
        trace_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Build, hash-chain, and append one audit entry.

        Returns the written entry dict.
        """
        with self._lock:
            self._entry_count += 1
            timestamp = datetime.now(timezone.utc).isoformat()

            # Build entry without hash fields first
            entry: dict[str, Any] = {
                "seq": self._entry_count,
                "timestamp": timestamp,
                "action": action,
                "actor": actor,
                "incident_id": incident_id,
                "request_id": request_id,
                "trace_id": trace_id,
                "metadata": metadata,
                "prev_hash": self._prev_hash,
            }

            # Compute hash: SHA256(prev_hash + JSON(entry))
            entry_hash = self._compute_hash(self._prev_hash, entry)
            entry["entry_hash"] = entry_hash
            self._prev_hash = entry_hash

            # Persist to JSONL file (append-only)
            if self._log_file:
                try:
                    with self._log_file.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(entry, default=str) + "\n")
                        fh.flush()
                        os.fsync(fh.fileno())  # Force disk write
                except Exception as exc:
                    logger.error("AuditLogger: Failed to write entry: %s", exc)

            logger.debug(
                "Audit | seq=%d | action=%s | actor=%s | incident=%s | hash=%.16s...",
                self._entry_count,
                action,
                actor,
                incident_id,
                entry_hash,
            )
            return entry

    def verify_chain_integrity(self) -> dict[str, Any]:
        """Verify the hash chain integrity of the entire audit log.

        Returns:
            Dict with 'valid': True/False, 'entries_checked', and 'first_broken_seq'.
        """
        if not self._log_file or not self._log_file.exists():
            return {
                "valid": True,
                "entries_checked": 0,
                "message": "No audit log file found.",
            }

        try:
            prev_hash = _GENESIS_HASH
            entries_checked = 0
            with self._log_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    entries_checked += 1

                    stored_hash = entry.pop("entry_hash", None)
                    computed_hash = self._compute_hash(prev_hash, entry)

                    if stored_hash != computed_hash:
                        return {
                            "valid": False,
                            "entries_checked": entries_checked,
                            "first_broken_seq": entry.get("seq"),
                            "message": f"Hash chain broken at entry seq={entry.get('seq')}",
                        }
                    prev_hash = stored_hash

            return {
                "valid": True,
                "entries_checked": entries_checked,
                "message": "Audit log chain is intact.",
            }
        except Exception as exc:
            return {"valid": False, "entries_checked": 0, "message": str(exc)}

    def get_recent_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the last N audit entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of audit entry dicts, most recent last.
        """
        if not self._log_file or not self._log_file.exists():
            return []

        try:
            entries = []
            with self._log_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
            return entries[-limit:]
        except Exception as exc:
            logger.error("AuditLogger: Failed to read entries: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Domain-specific logging helpers
    # ------------------------------------------------------------------

    def log_incident_created(
        self,
        request_id: str,
        trace_id: str,
        incident_id: str,
        actor: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an incident creation event."""
        self._write_entry(
            action="INCIDENT_CREATED",
            actor=actor,
            incident_id=incident_id,
            request_id=request_id,
            trace_id=trace_id,
            metadata=metadata or {},
        )

    def log_agent_decision(
        self,
        request_id: str,
        trace_id: str,
        incident_id: str,
        agent_name: str,
        decision: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an agent decision or state transition."""
        self._write_entry(
            action="AGENT_DECISION",
            actor=agent_name,
            incident_id=incident_id,
            request_id=request_id,
            trace_id=trace_id,
            metadata={"decision": decision, **(metadata or {})},
        )

    def log_tool_execution(
        self,
        request_id: str,
        trace_id: str,
        incident_id: str,
        agent_name: str,
        tool_name: str,
        allowed: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a tool execution attempt (allowed or blocked)."""
        self._write_entry(
            action="TOOL_EXECUTION" if allowed else "TOOL_BLOCKED",
            actor=agent_name,
            incident_id=incident_id,
            request_id=request_id,
            trace_id=trace_id,
            metadata={"tool_name": tool_name, "allowed": allowed, **(metadata or {})},
        )

    def log_security_rejection(
        self,
        request_id: str,
        trace_id: str,
        incident_id: str,
        error_code: str,
        field: str = "",
        layer: int = 0,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a security rejection (injection blocked, rate limit, etc.)."""
        self._write_entry(
            action="SECURITY_REJECTION",
            actor=actor,
            incident_id=incident_id,
            request_id=request_id,
            trace_id=trace_id,
            metadata={
                "error_code": error_code,
                "field": field,
                "detection_layer": layer,
                **(metadata or {}),
            },
        )

    def log_websocket_event(
        self,
        trace_id: str,
        incident_id: str,
        event_type: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a WebSocket event broadcast."""
        self._write_entry(
            action="WEBSOCKET_EVENT",
            actor=source,
            incident_id=incident_id,
            request_id="ws",
            trace_id=trace_id,
            metadata={"event_type": event_type, **(metadata or {})},
        )

    def log_rate_limit_violation(
        self,
        request_id: str,
        trace_id: str,
        key: str,
        limit_type: str,
        client_ip: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a rate limit violation."""
        self._write_entry(
            action="RATE_LIMIT_VIOLATION",
            actor=client_ip or "unknown",
            incident_id="none",
            request_id=request_id,
            trace_id=trace_id,
            metadata={"key": key, "limit_type": limit_type, **(metadata or {})},
        )

    def log_simulation_event(
        self,
        request_id: str,
        trace_id: str,
        simulation_type: str,
        actor: str = "admin",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a threat simulation event (demo mode)."""
        self._write_entry(
            action="THREAT_SIMULATION",
            actor=actor,
            incident_id="SIMULATION",
            request_id=request_id,
            trace_id=trace_id,
            metadata={"simulation_type": simulation_type, **(metadata or {})},
        )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

audit_logger = AuditLogger()
