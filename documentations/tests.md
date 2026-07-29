# 🧪 JARVIS Test & Verification Matrix — Natural Language Commands & Expected Responses

This document provides a testing catalog of **user voice/text commands**, **3D Face Engine unit tests**, **mobile gateway interactions**, and the **expected natural language responses and output cards from JARVIS**. **Last Updated:** July 29, 2026

---

## 🎯 Command & Response Verification Catalog

### 1. Asset-Based 3D Face Engine Unit Tests (`faceEngine.test.ts`)
* **Test Suite**: `frontend/src/renderer/src/lib/face-engine/tests/faceEngine.test.ts`
  * **Test 1**: `VisemeLipSync.evaluateFromAudio()`
    - Verifies audio amplitude levels (0.0 to 1.0) map correctly into viseme weights (`viseme_aa`, `jawOpen`, `viseme_E`, `viseme_O`).
    - **Result**: **PASSED 100%**
  * **Test 2**: `PromptOptimizer.optimize()`
    - Verifies prompt optimizer strips redundant photorealism buzzwords and applies targeted negative weights.
    - **Result**: **PASSED 100%**
  * **Test 3**: `QualityValidator.validate()`
    - Verifies automatic anomaly detector flags plastic skin reflectance and corrects eye iris symmetry.
    - **Result**: **PASSED 100%**

---

### 2. Dedicated Android Mobile Companion & Security Gatekeeper Tests
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

### 3. Master Upgrade Diagnostic Test Suite Catalog

* **Script**: `scratch/test_chat_history.py`
  * **Coverage**: Session creation, first-message title auto-generation, title renaming, deletion, and message transcript restoration via `MemoryService` and REST endpoints `/api/conversations`.
  * **Result**: **PASSED 100%**

* **Script**: `scratch/test_browser_agent.py`
  * **Coverage**: Autonomous Web Agent perceive-decide-act-observe loop (`run_browser_agent` & `perceive_page_state`) and `browser_agent_task` tool registration.
  * **Result**: **PASSED 100%**

* **Script**: `scratch/test_markl_features.py`
  * **Coverage**: Instant interrupt (`cancel_playback`), exponential backoff retry decorator, 3.0s vision rate-limiter, Windows Registry boot auto-start, Clipboard Quick-Action Intelligence, session memory continuity, background topic monitoring, and Proactive 2.0.
  * **Result**: **PASSED 100%**

* **Script**: `scratch/test_paddleocr.py`
  * **Coverage**: Structured table, layout, and bounding box text extraction with PP-StructureV3 deep vision, pytesseract, and PIL grid fallback.
  * **Result**: **PASSED 100%**

* **Script**: `scratch/test_ocr_and_all_systems.py`
  * **Coverage**: Full multi-subsystem diagnostic audit across all 6 core OS layers.
  * **Result**: **PASSED 100%**

---

### 4. Native Windows UI Automation (UIA) Tests
* **Command**: `"Click Save button in Notepad"`
  * **Expected Output from JARVIS**:
    ```text
    "I have clicked the 'Save' button in Notepad via Win32 UI Automation, sir."
    ```

* **Command**: `"Search local files for budget report"`
  * **Expected Output from JARVIS**: Sub-second search result list powered by SQLite FTS5 (`FileIndexerService`).
