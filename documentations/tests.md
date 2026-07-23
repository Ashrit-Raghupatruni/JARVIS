# 🧪 JARVIS Test & Verification Matrix — Natural Language Commands & Expected Responses

This document provides a testing catalog of **user voice/text commands**, **mobile gateway interactions**, and the **expected natural language responses and output cards from JARVIS**. **Last Updated:** July 22, 2026

---

## 🎯 Command & Response Verification Catalog

### 1. Dedicated Android Mobile Companion & Security Gatekeeper Tests
* **Command**: `POST /api/v1/mobile/pair/initiate`
  * **Expected Response**:
    ```json
    {
      "pairing_session_id": "8a32f91b-...",
      "pairing_code": "492817",
      "server_public_key": "JARVIS_ED25519_PUBKEY_SIMULATED",
      "expires_in_seconds": 300
    }
    ```

* **Command**: `POST /api/v1/mobile/approvals/respond`
  * **Payload**: `{"approval_id": "appr_101", "decision": "approve"}`
  * **Expected Response**:
    ```json
    {
      "status": "decision_processed",
      "approval_id": "appr_101",
      "decision": "approve"
    }
    ```

* **Command**: `"Check mobile companion telemetry stream"`
  * **Expected Response**: Real-time WebSocket frame at `ws://localhost:8000/api/v1/mobile/ws/stream` broadcasting CPU %, RAM %, GPU %, and active task metrics every 1000ms.

---

### 2. Native Windows UI Automation (UIA) Tests
* **Command**: `"Click Save button in Notepad"`
  * **Expected Output from JARVIS**:
    ```text
    "I have clicked the 'Save' button in Notepad via Win32 UI Automation, sir."
    ```

* **Command**: `"Search local files for budget report"`
  * **Expected Output from JARVIS**: Sub-second search result list powered by SQLite FTS5 (`FileIndexerService`).
