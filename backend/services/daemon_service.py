"""
JARVIS Component B: Session-0 Isolation-Safe Background Service Daemon.

========================================================================================
CRITICAL ARCHITECTURAL SAFEGUARD — WINDOWS SESSION 0 ISOLATION:
========================================================================================
In Windows Vista, 7, 8, 10, and 11, all Windows Services run exclusively in Session 0.
Interactive user desktop sessions run in Session 1, Session 2, etc.

SESSION 0 LIMITATIONS (MANDATORY OPERATING SYSTEM ENFORCEMENT):
1. NO Desktop GUI: Session 0 has no interactive window station or desktop surface.
2. NO Screen Capture: Graphics Device Interface (GDI) / DirectX screen captures return
   black or empty frames in Session 0.
3. NO UI Automation (UIA): Windows Accessibility and pywinauto trees are unreachable.
4. NO Input Injection: SendInput (mouse clicks, keyboard typing) is rejected or isolated.

DO NOT ATTEMPT TO RUN FULL JARVIS DESKTOP AUTOMATION INSIDE THIS SERVICE.
Doing so will silently break all UI automation, screen capture, and vision capabilities.

TWO-COMPONENT ARCHITECTURAL DESIGN:
- Component A (Interactive Desktop Assistant):
  Runs in user session (Session 1+) at user logon via Task Scheduler / Startup.
  Maintains full UIA automation, desktop control, vision spotlight, and audio STT.
- Component B (This Daemon Service):
  Runs as a true Windows Service in Session 0 before any user logs in.
  Dedicated strictly to Session-0-safe headless duties:
  1. System & hardware telemetry (CPU, RAM, Disk, Battery, Network via psutil).
  2. Mobile Remote Wake / Pre-Warm Listener (Port 8001).
  3. Session 1 Triggering (Dispatches Task Scheduler to launch Component A on demand).
========================================================================================
"""

import sys
import os
import json
import time
import socket
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_WIN32SERVICE = True
except ImportError:
    HAS_WIN32SERVICE = False

SERVICE_NAME = "JARVIS_Daemon"
SERVICE_DISPLAY_NAME = "JARVIS Background OS Daemon (Session 0)"
SERVICE_DESCRIPTION = "Lightweight headless service for hardware telemetry and remote mobile wake."
DAEMON_PORT = 8001
_start_time = time.time()


def get_system_telemetry() -> Dict[str, Any]:
    """Retrieve Session-0 safe hardware telemetry."""
    telem = {
        "service": "JARVIS Session-0 Daemon",
        "session": "Session 0 (Headless / Pre-Logon)",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "hostname": socket.gethostname()
    }

    if HAS_PSUTIL:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(os.path.splitdrive(os.getcwd())[0] or "C:")
        bat = psutil.sensors_battery()

        telem.update({
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024 ** 3), 2),
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "battery_percent": bat.percent if bat else None,
            "power_plugged": bat.power_plugged if bat else None
        })

    # Probe if Component A (Interactive Desktop on Port 8000) is online
    comp_a_online = False
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
            comp_a_online = True
    except Exception:
        comp_a_online = False

    telem["component_a_desktop_online"] = comp_a_online
    return telem


def trigger_component_a_wake() -> Dict[str, Any]:
    """
    Signal Windows Task Scheduler or interactive launcher to prepare/launch Component A
    in the interactive user session.
    """
    task_name = "JARVIS_Desktop_Assistant"
    try:
        res = subprocess.run(
            ["schtasks", "/Run", "/TN", task_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            return {"status": "ok", "method": "task_scheduler", "message": f"Successfully triggered task '{task_name}' in Session 1+."}
    except Exception:
        pass

    # Fallback to direct launcher if accessible
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    start_bat = os.path.join(project_root, "start.bat")
    if os.path.exists(start_bat):
        try:
            subprocess.Popen(["cmd.exe", "/c", start_bat], cwd=project_root, creationflags=subprocess.CREATE_NEW_CONSOLE)
            return {"status": "ok", "method": "direct_launcher", "message": "Launched start.bat for Component A."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "warning", "message": "Component A wake signal dispatched (no active task)."}



class DaemonHTTPHandler(BaseHTTPRequestHandler):
    """Minimal, rock-solid HTTP request handler with zero dependencies."""

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path in ("/api/daemon/health", "/health"):
            self._send_json(200, {"status": "ok", "service": "JARVIS_Daemon_Session0", "port": DAEMON_PORT})
        elif self.path in ("/api/daemon/status", "/api/daemon/telemetry", "/status"):
            self._send_json(200, get_system_telemetry())
        else:
            self._send_json(404, {"error": "Endpoint not found", "valid_endpoints": ["/api/daemon/health", "/api/daemon/status", "/api/daemon/wake"]})

    def do_POST(self) -> None:
        if self.path in ("/api/daemon/wake", "/wake"):
            res = trigger_component_a_wake()
            self._send_json(200, {"wake_result": res, "telemetry": get_system_telemetry()})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP logging
        pass


class DaemonServer:
    """Manages the background daemon HTTP server."""

    def __init__(self, port: int = DAEMON_PORT):
        self.port = port
        self.httpd = None
        self._thread = None
        self._running = False

    def start(self, blocking: bool = True):
        self.httpd = HTTPServer(("0.0.0.0", self.port), DaemonHTTPHandler)
        self._running = True
        print(f"✓ JARVIS Component B (Session-0 Daemon) listening on http://0.0.0.0:{self.port}")

        if blocking:
            try:
                self.httpd.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("✓ JARVIS Component B stopped.")


if HAS_WIN32SERVICE:
    class JarvisWindowsService(win32serviceutil.ServiceFramework):
        """Native Windows Service implementation."""
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.server = DaemonServer(DAEMON_PORT)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            self.server.stop()

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            self.server.start(blocking=False)
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)


def check_status() -> Dict[str, Any]:
    """Check if Daemon is reachable on port 8001."""
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{DAEMON_PORT}/api/daemon/status", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"active": True, "data": data}
    except Exception as e:
        return {"active": False, "error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Component B (Session-0 Daemon Service)")
    parser.add_argument("action", nargs="?", default="status",
                        choices=["install", "start", "stop", "remove", "status", "run-standalone", "wake"],
                        help="Action to perform")
    args = parser.parse_args()

    if args.action == "run-standalone":
        server = DaemonServer(DAEMON_PORT)
        server.start(blocking=True)
    elif args.action == "status":
        stat = check_status()
        print(json.dumps(stat, indent=2))
    elif args.action == "wake":
        print(json.dumps(trigger_component_a_wake(), indent=2))
    elif args.action in ("install", "start", "stop", "remove"):
        if not HAS_WIN32SERVICE:
            print("Error: pywin32 is required to install as a Windows Service.")
            sys.exit(1)
        win32serviceutil.HandleCommandLine(JarvisWindowsService, argv=[sys.argv[0], args.action])


if __name__ == "__main__":
    main()
