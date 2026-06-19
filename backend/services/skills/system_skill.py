"""
System Intelligence Skill for JARVIS.
Handles process monitoring and termination, Windows startup programs management,
WiFi/network controls via netsh, Windows power actions, and clipboard interactions.
"""

import os
import sys
import subprocess
import winreg
import psutil
import pyperclip
from typing import Any, Dict, List, Optional

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger


class SystemSkill(BaseSkill):
    """Enables JARVIS to monitor resource utilization, manage startup, control networks, power, and clipboard."""

    def __init__(self, automation_service=None) -> None:
        self.automation = automation_service
        self._startup_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    # ── Process Monitoring ──────────────────────────────────────────────────

    @skill_tool(
        name="get_top_processes",
        description="Lists the top running processes sorted by resource consumption (CPU or Memory).",
        parameters={
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["cpu", "memory"], "description": "Resource type to sort by. Default is 'memory'."},
                "limit": {"type": "integer", "description": "Number of processes to return. Default is 7."}
            },
            "required": []
        }
    )
    def get_top_processes(self, sort_by: str = "memory", limit: int = 7) -> str:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                mem_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu": info['cpu_percent'] or 0.0,
                    "memory": mem_mb
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort
        if sort_by.lower() == "cpu":
            processes.sort(key=lambda x: x["cpu"], reverse=True)
            sort_label = "CPU %"
        else:
            processes.sort(key=lambda x: x["memory"], reverse=True)
            sort_label = "RAM (MB)"

        lines = [f"Top {limit} processes sorted by {sort_by.upper()}:", f"{'PID':<8}{'Process Name':<30}{sort_label:<15}"]
        lines.append("-" * 53)
        
        for p in processes[:limit]:
            val = f"{p['cpu']:.1f}%" if sort_by == "cpu" else f"{p['memory']:.1f} MB"
            lines.append(f"{p['pid']:<8}{p['name']:<30}{val:<15}")

        # Total System RAM stats
        vmem = psutil.virtual_memory()
        total_ram = vmem.total / (1024**3)
        used_ram = vmem.used / (1024**3)
        lines.append("-" * 53)
        lines.append(f"Total system RAM usage: {used_ram:.1f} GB / {total_ram:.1f} GB ({vmem.percent}% used)")
        
        return "\n".join(lines)

    @skill_tool(
        name="kill_process",
        description="Terminates a process by its PID or common name.",
        parameters={
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "Process ID to terminate"},
                "name": {"type": "string", "description": "Name of the process (e.g. 'chrome.exe', 'notepad')"}
            },
            "required": []
        }
    )
    def kill_process(self, pid: Optional[int] = None, name: Optional[str] = None) -> str:
        if not pid and not name:
            return "Please provide either a PID or a process name to terminate."

        if pid:
            try:
                proc = psutil.Process(pid)
                p_name = proc.name()
                proc.terminate()
                return f"✓ Terminated process '{p_name}' (PID: {pid}) successfully."
            except psutil.NoSuchProcess:
                return f"No running process found with PID: {pid}."
            except psutil.AccessDenied:
                return f"Access Denied. Insufficient permissions to terminate PID: {pid}."

        if name:
            target = name.lower()
            if not target.endswith(".exe") and sys.platform == "win32":
                target += ".exe"
            
            terminated_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == target:
                        proc.terminate()
                        terminated_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if terminated_count > 0:
                return f"✓ Terminated {terminated_count} instances of process '{name}'."
            return f"No running instances of process '{name}' were found."

    # ── Startup Programs Management ─────────────────────────────────────────

    @skill_tool(
        name="list_startup_programs",
        description="Lists all apps registered to run automatically on Windows startup.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def list_startup_programs(self) -> str:
        if sys.platform != "win32":
            return "Startup management is only supported on Windows."

        try:
            programs = []
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._startup_key_path, 0, winreg.KEY_READ) as key:
                index = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(key, index)
                        programs.append(f"- **{name}**: `{val}`")
                        index += 1
                    except OSError:
                        break  # No more values
            
            if not programs:
                return "No custom startup applications registered in Registry."
            return "Windows User Startup Programs:\n" + "\n".join(programs)
        except Exception as e:
            return f"Failed to list startup programs: {e}"

    @skill_tool(
        name="set_startup_program",
        description="Registers or disables an application to run automatically on system boot.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The friendly registry key name (e.g. 'JARVIS')"},
                "executable_path": {"type": "string", "description": "Path to the app's .exe. If omitted, will remove key (disabling startup)"}
            },
            "required": ["name"]
        }
    )
    def set_startup_program(self, name: str, executable_path: Optional[str] = None) -> str:
        if sys.platform != "win32":
            return "Startup management is Windows-only."

        try:
            if executable_path:
                # Add/Enable
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._startup_key_path, 0, winreg.KEY_WRITE) as key:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, executable_path)
                return f"✓ Registered '{name}' to startup with command: `{executable_path}`."
            else:
                # Delete/Disable
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._startup_key_path, 0, winreg.KEY_WRITE) as key:
                    try:
                        winreg.DeleteValue(key, name)
                        return f"✓ Removed '{name}' from startup registry successfully."
                    except FileNotFoundError:
                        return f"Startup program '{name}' was not found in registry."
        except Exception as e:
            return f"Failed to modify startup registry: {e}"

    # ── Network Control via Netsh ───────────────────────────────────────────

    @skill_tool(
        name="get_wifi_status",
        description="Gets details about connected WiFi network and list of visible wireless SSIDs.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def get_wifi_status(self) -> str:
        if sys.platform != "win32":
            return "Network controls are only supported on Windows."

        try:
            # 1. Connection status
            conn_res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, errors="ignore")
            lines = conn_res.stdout.split("\n")
            ssid = "Not Connected"
            signal = "N/A"
            for line in lines:
                if "SSID" in line and "BSSID" not in line:
                    ssid = line.split(":")[1].strip()
                if "Signal" in line:
                    signal = line.split(":")[1].strip()

            # 2. Show visible networks
            net_res = subprocess.run(["netsh", "wlan", "show", "networks"], capture_output=True, text=True, errors="ignore")
            networks = []
            for line in net_res.stdout.split("\n"):
                if "SSID" in line and ":" in line:
                    net_name = line.split(":")[1].strip()
                    if net_name:
                        networks.append(net_name)

            report = [
                f"📶 **Current WiFi Status**:",
                f"- Connection: **{ssid}**",
                f"- Signal Strength: **{signal}**",
                "",
                f"📡 **Available Networks ({len(networks)})**:"
            ]
            for n in networks[:8]:
                report.append(f"  - {n}")
            if len(networks) > 8:
                report.append(f"  - ... and {len(networks) - 8} more.")

            return "\n".join(report)
        except Exception as e:
            return f"Failed to retrieve network status: {e}"

    @skill_tool(
        name="set_wifi_power",
        description="Enables or disables the WiFi interface card.",
        parameters={
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["on", "off"], "description": "Toggle state"}
            },
            "required": ["state"]
        }
    )
    def set_wifi_power(self, state: str) -> str:
        if sys.platform != "win32":
            return "WiFi toggling is Windows-only."

        admin_state = "enabled" if state.lower() == "on" else "disabled"
        try:
            # Command requires administrative credentials on some machines, but let's run it.
            # Interface name is usually "Wi-Fi" or "Wireless Network Connection" on Windows.
            cmd = f'netsh interface set interface name="Wi-Fi" admin={admin_state}'
            logger.info("Executing network power change: {}", cmd)
            
            # Using run_terminal_command from automation if possible, or direct subprocess
            res = subprocess.run(["netsh", "interface", "set", "interface", "name=Wi-Fi", f"admin={admin_state}"], capture_output=True, text=True)
            if res.returncode != 0:
                # Try finding actual wireless adapter name first
                return f"Failed to toggle WiFi interface. Error details:\n{res.stderr.strip() or res.stdout.strip()}"
            return f"✓ WiFi adapter interface set to {state.upper()}."
        except Exception as e:
            return f"Failed to set network power: {e}"

    # ── Power Management ────────────────────────────────────────────────────

    @skill_tool(
        name="get_battery_status",
        description="Gets battery percentages and power source status.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def get_battery_status(self) -> str:
        battery = psutil.sensors_battery()
        if not battery:
            return "No battery detected (Desktop PC)."

        percent = battery.percent
        plugged = "Charging" if battery.power_plugged else "Discharging"
        
        # Calculate time left
        time_left = "Calculating..."
        if battery.secsleft != psutil.POWER_TIME_UNLIMITED and battery.secsleft != psutil.POWER_TIME_UNKNOWN:
            hours = int(battery.secsleft // 3600)
            mins = int((battery.secsleft % 3600) // 60)
            time_left = f"{hours}h {mins}m remaining"
        elif battery.power_plugged:
            time_left = "Plugged in"

        return f"🔋 **Battery Status**: {percent}% ({plugged}) — {time_left}."

    @skill_tool(
        name="set_system_power_action",
        description="Initiates sleep, hibernate, lock, or shutdown schedules.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["sleep", "hibernate", "lock", "shutdown"], "description": "Power state action"},
                "delay_seconds": {"type": "integer", "description": "Delay before execution (only for shutdown)"}
            },
            "required": ["action"]
        }
    )
    def set_system_power_action(self, action: str, delay_seconds: int = 0) -> str:
        act = action.lower().strip()
        
        try:
            if act == "lock":
                if sys.platform == "win32":
                    import ctypes
                    ctypes.windll.user32.LockWorkStation()
                    return "✓ System screen locked."
                return "Locking workstation is only supported on Windows."

            elif act == "sleep":
                if sys.platform == "win32":
                    # Rundll32 power profiles call to sleep
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"], check=True)
                    return "✓ Triggered sleep state."
                return "Sleep is Windows-only."

            elif act == "hibernate":
                if sys.platform == "win32":
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "1", "1", "0"], check=True)
                    return "✓ Triggered hibernation."
                return "Hibernate is Windows-only."

            elif act == "shutdown":
                t = max(0, delay_seconds)
                if sys.platform == "win32":
                    subprocess.run(["shutdown", "/s", "/t", str(t)], check=True)
                    return f"✓ System shutdown scheduled in {t} seconds."
                else:
                    subprocess.run(["shutdown", "-h", f"+{t // 60}"], check=True)
                    return f"✓ Shutdown scheduled in {t} seconds."
        except Exception as e:
            return f"Failed to perform system action '{action}': {e}"

    # ── Clipboard Manager ───────────────────────────────────────────────────

    @skill_tool(
        name="clipboard_copy",
        description="Writes a piece of text to the OS clipboard.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text content to copy"}
            },
            "required": ["text"]
        }
    )
    def clipboard_copy(self, text: str) -> str:
        try:
            pyperclip.copy(text)
            return "✓ Successfully copied text to clipboard."
        except Exception as e:
            return f"Failed to write to clipboard: {e}"

    @skill_tool(
        name="clipboard_paste",
        description="Reads the current text stored in the OS clipboard.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def clipboard_paste(self) -> str:
        try:
            text = pyperclip.paste()
            if not text:
                return "Clipboard is empty or does not contain text."
            # Limit length for output safety
            clipped = text[:800] + "\n...[truncated]" if len(text) > 800 else text
            return f"Clipboard Content:\n{clipped}"
        except Exception as e:
            return f"Failed to read clipboard: {e}"
