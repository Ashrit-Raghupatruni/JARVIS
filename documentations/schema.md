# 🗄️ Database Schemas & Data Structures

This document outlines the SQLite WAL database schemas, IPC message structures, goal checkpoint tables, and JSON schema definitions used across JARVIS. **Last Updated:** August 8, 2026

---

## 1. SQLite WAL Goal Queue & Checkpointing Schema (`data/jarvis.db`)

Managed by `LongHorizonCheckpointService` ([`backend/services/long_horizon_checkpoint.py`](file:///c:/Users/ashri/JARVIS/backend/services/long_horizon_checkpoint.py)).

### Table: `goal_queue`
```sql
CREATE TABLE IF NOT EXISTS goal_queue (
    goal_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'running', -- running | paused | completed | failed | cancelled
    progress REAL NOT NULL DEFAULT 0.0,
    total_steps INTEGER DEFAULT 1,
    completed_steps INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

### Table: `agent_checkpoints`
```sql
CREATE TABLE IF NOT EXISTS agent_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    step_title TEXT NOT NULL,
    state_data TEXT NOT NULL, -- JSON string of step payload / artifacts
    created_at REAL NOT NULL,
    FOREIGN KEY (goal_id) REFERENCES goal_queue (goal_id) ON DELETE CASCADE
);
```

---

## 2. Inter-Process Communication (IPC) Message Schema

Managed by `AgentEcosystemService` ([`backend/services/agent_ecosystem.py`](file:///c:/Users/ashri/JARVIS/backend/services/agent_ecosystem.py)).

```json
{
  "id": "ipc_a1b2c3d4",
  "sender": "CodeAgent",
  "recipient": "SecurityAgent",
  "content": "Requesting safety policy audit for: 'Refactor API endpoints'",
  "message_type": "request", // request | response | alert | audit
  "payload": {
    "command": "git status",
    "risk_level": "low"
  },
  "timestamp": 1785489000.0,
  "formatted_time": "10:30:00"
}
```

---

## 3. Trusted Mobile Device & JWT Payload Schema

Managed by `MobileAuthService` ([`backend/services/mobile_auth.py`](file:///c:/Users/ashri/JARVIS/backend/services/mobile_auth.py)).

### JWT Payload (`HS256` signed)
```json
{
  "sub": "android-companion-1",
  "friendly_name": "Ashrit's Android Phone",
  "iat": 1785480000,
  "exp": 1817016000
}
```
