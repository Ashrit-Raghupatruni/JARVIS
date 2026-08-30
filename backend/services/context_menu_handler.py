"""
Windows Explorer Right-Click Context Menu Invocation Handler.

Invoked when the user right-clicks any file or folder in Windows Explorer
and clicks 'Analyze with JARVIS' or 'Summarize with JARVIS'.
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error
import subprocess
import ctypes

BACKEND_URL = "http://127.0.0.1:8000"


def show_toast(title: str, message: str) -> None:
    """Show a non-blocking Windows Message / Notification."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000040)  # MB_ICONINFORMATION
    except Exception:
        print(f"[{title}] {message}")


def is_backend_healthy() -> bool:
    """Check if JARVIS backend is reachable."""
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_jarvis_backend() -> bool:
    """Launch JARVIS backend if not currently running."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    start_bat = os.path.join(project_root, "start.bat")

    if os.path.exists(start_bat):
        print("⚡ JARVIS backend offline — starting service...")
        subprocess.Popen(["cmd.exe", "/c", start_bat], cwd=project_root, creationflags=subprocess.CREATE_NEW_CONSOLE)
        
        # Wait up to 15 seconds for backend to initialize
        for _ in range(15):
            time.sleep(1)
            if is_backend_healthy():
                print("✓ JARVIS backend online!")
                return True
    return False


def dispatch_action(action: str, target_path: str) -> dict:
    """Dispatch the context action to the running JARVIS backend."""
    url = f"{BACKEND_URL}/api/v1/desktop/context_action"
    payload = json.dumps({"action": action, "target_path": target_path}).encode("utf-8")
    
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    if len(sys.argv) < 3:
        print("Usage: context_menu_handler.py <analyze|summarize> <target_path>")
        sys.exit(1)

    action = sys.argv[1].lower().strip()
    target_path = os.path.abspath(sys.argv[2])

    print(f"JARVIS Explorer Action: '{action}' on '{target_path}'")

    # Step 1: Ensure backend is running
    if not is_backend_healthy():
        started = start_jarvis_backend()
        if not started:
            show_toast("JARVIS Error", "Could not connect to JARVIS backend. Please run start.bat.")
            sys.exit(1)

    # Step 2: Dispatch action
    res = dispatch_action(action, target_path)
    
    if res.get("status") == "ok":
        result_text = res.get("result", "Operation completed.")
        base_name = os.path.basename(target_path)
        title = f"JARVIS {action.capitalize()}: {base_name}"
        print(f"\n{'='*50}\n{title}\n{'='*50}\n{result_text}\n{'='*50}\n")
        show_toast(title, result_text[:1000] + ("..." if len(result_text) > 1000 else ""))
    else:
        err = res.get("message", "Unknown error")
        show_toast("JARVIS Error", f"Action '{action}' failed:\n{err}")


if __name__ == "__main__":
    main()
