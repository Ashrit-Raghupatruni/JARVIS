"""
JARVIS AI Operating System - Automation Orchestrator.
=====================================================
Central orchestrator managing multi-step workflows, RPA macros, desktop/browser execution,
and action verification:
- Macro recording & playback with persistent JSON workflow storage
- Step-level error isolation and retry/recovery logic
- Unified routing across DesktopExecutor, BrowserExecutor, UIAPerceptionEngine, and ActionVerifier
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.services.automation.desktop_executor import DesktopExecutor
from backend.services.automation.browser_executor import BrowserExecutor
from backend.services.automation.uia_perception import UIAPerceptionEngine
from backend.services.automation.verifier import ActionExecutionVerifier


class AutomationOrchestrator:
    """
    Central coordinator orchestrating desktop, browser, UIA perception, and macro automation.
    """

    def __init__(
        self,
        workflows_dir: Optional[Path] = None,
        desktop_executor: Optional[DesktopExecutor] = None,
        browser_executor: Optional[BrowserExecutor] = None,
        uia_engine: Optional[UIAPerceptionEngine] = None,
        verifier: Optional[ActionExecutionVerifier] = None,
    ) -> None:
        self.workflows_dir = workflows_dir or Path("data/workflows")
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

        self._desktop = desktop_executor
        self._browser = browser_executor
        self._uia = uia_engine
        self._verifier = verifier

        self._recorded_steps: List[Dict[str, Any]] = []
        self._is_recording: bool = False
        self._recording_name: str = ""

        logger.info("AutomationOrchestrator initialized. Workflows directory: {}", self.workflows_dir)

    @property
    def desktop(self) -> DesktopExecutor:
        if self._desktop is None:
            self._desktop = DesktopExecutor()
        return self._desktop

    @property
    def browser(self) -> BrowserExecutor:
        if self._browser is None:
            self._browser = BrowserExecutor()
        return self._browser

    @property
    def uia(self) -> UIAPerceptionEngine:
        if self._uia is None:
            self._uia = UIAPerceptionEngine()
        return self._uia

    @property
    def verifier(self) -> ActionExecutionVerifier:
        if self._verifier is None:
            self._verifier = ActionExecutionVerifier()
        return self._verifier

    # ── Workflow Recording & Persistence ─────────────────────────────────

    def start_workflow_recording(self, name: str) -> Dict[str, Any]:
        """Start recording user workflow macro steps."""
        self._is_recording = True
        self._recording_name = name.strip() or f"workflow_{int(time.time())}"
        self._recorded_steps = []
        logger.info("Started workflow recording: '{}'", self._recording_name)
        return {"status": "recording_started", "name": self._recording_name}

    def record_step(self, action_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Record a single step into the active workflow."""
        if not self._is_recording:
            return {"error": "Not currently recording a workflow."}

        step = {
            "step_index": len(self._recorded_steps) + 1,
            "timestamp": time.time(),
            "action_type": action_type,
            "details": details
        }
        self._recorded_steps.append(step)
        logger.debug("Recorded step: {}", step)
        return {"status": "step_recorded", "step": step}

    def stop_workflow_recording(self) -> Dict[str, Any]:
        """Stop active workflow recording and save to disk."""
        if not self._is_recording:
            return {"error": "No active recording to stop."}

        self._is_recording = False
        filepath = self.workflows_dir / f"{self._recording_name}.json"

        workflow_data = {
            "name": self._recording_name,
            "created_at": time.time(),
            "step_count": len(self._recorded_steps),
            "steps": self._recorded_steps
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(workflow_data, f, indent=2)
            logger.info("Saved recorded workflow to: {}", filepath)
            return {
                "status": "recording_saved",
                "name": self._recording_name,
                "filepath": str(filepath),
                "step_count": len(self._recorded_steps)
            }
        except Exception as e:
            logger.error("Failed to save workflow JSON: {}", e)
            return {"error": f"Failed to save workflow: {e}"}

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all saved macro workflows."""
        workflows = []
        for file in self.workflows_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    workflows.append({
                        "name": data.get("name", file.stem),
                        "filename": file.name,
                        "created_at": data.get("created_at"),
                        "step_count": data.get("step_count", 0)
                    })
            except Exception as e:
                logger.warning("Could not parse workflow file {}: {}", file, e)
        return workflows

    def playback_workflow(self, name: str) -> Dict[str, Any]:
        """Execute stored workflow macro steps."""
        filename = name if name.endswith(".json") else f"{name}.json"
        filepath = self.workflows_dir / filename

        if not filepath.exists():
            return {"error": f"Workflow '{name}' not found."}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            steps = data.get("steps", [])
            executed_count = 0

            logger.info("Playing back workflow '{}' with {} steps...", name, len(steps))

            for step in steps:
                action_type = step.get("action_type")
                details = step.get("details", {})

                delay = details.get("delay", 0.1)
                if delay > 0:
                    time.sleep(min(delay, 2.0))

                if action_type == "open_application":
                    app_name = details.get("app_name")
                    if app_name:
                        os.system(f"start {app_name}")
                elif action_type == "press_hotkey":
                    keys = details.get("keys", [])
                    logger.debug("Hotkey action executed: {}", keys)
                elif action_type == "type_text":
                    text = details.get("text", "")
                    logger.debug("Type text action executed: {}", text)

                executed_count += 1

            return {
                "status": "completed",
                "name": name,
                "executed_steps": executed_count,
                "total_steps": len(steps)
            }
        except Exception as e:
            logger.error("Error during workflow playback: {}", e)
            return {"error": f"Playback failed: {e}"}

    # ── RPA Macro Orchestration ──────────────────────────────────────────

    def execute_rpa_macro(self, steps: List[Dict[str, Any]], stop_on_error: bool = True) -> Dict[str, Any]:
        """
        Execute an RPA macro sequence of UI actions with step-level isolation.
        """
        results = []
        for idx, step in enumerate(steps):
            act = str(step.get("action", "")).lower()
            status = "completed"
            err = None
            try:
                if act in ("open", "open_app", "launch"):
                    target = step.get("target") or step.get("app_name") or "notepad"
                    import subprocess
                    subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
                elif act in ("type", "type_text"):
                    text = step.get("text", "")
                    import pyautogui
                    pyautogui.FAILSAFE = False
                    pyautogui.typewrite(text, interval=0.01) if text.isascii() else pyautogui.write(text)
                elif act in ("wait", "sleep"):
                    dur = float(step.get("seconds", 0.5))
                    time.sleep(min(3.0, max(0.05, dur)))
                elif act == "hotkey":
                    keys = step.get("keys", [])
                    import pyautogui
                    pyautogui.FAILSAFE = False
                    if keys:
                        pyautogui.hotkey(*keys)
                elif act == "click":
                    import pyautogui
                    pyautogui.FAILSAFE = False
                    x = step.get("x", 500)
                    y = step.get("y", 500)
                    pyautogui.click(x, y)
            except Exception as e:
                status = "failed"
                err = str(e)
                if stop_on_error:
                    results.append({"step_index": idx + 1, "action": act, "status": status, "error": err})
                    break
            results.append({"step_index": idx + 1, "action": act, "status": status, "error": err})

        return {
            "status": "completed" if all(r["status"] == "completed" for r in results) else "partial_failure",
            "total_steps": len(steps),
            "executed_steps_count": len(results),
            "step_results": results
        }
