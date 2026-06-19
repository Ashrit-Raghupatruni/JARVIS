"""
Deep Application Integration Skill for JARVIS.
Provides Excel/Word COM automation (pywin32), VS Code launching, and tab controls.
"""

import sys
import os
import subprocess
import time
from typing import Any, Dict, List, Optional
import pyautogui

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger

# Try import win32com.client safely
win32com_available = False
if sys.platform == "win32":
    try:
        import win32com.client
        win32com_available = True
    except ImportError:
        logger.warning("win32com.client not available; Microsoft Word/Excel COM tools are disabled.")


class AppControlSkill(BaseSkill):
    """Enables JARVIS to automate active desktop applications (Office, VS Code, browsers)."""

    def __init__(self, automation_service=None) -> None:
        self.automation = automation_service

    # ── Excel / Word COM Automation ────────────────────────────────────────

    @skill_tool(
        name="excel_sum_column",
        description="Sums all numerical values in a specific column of the active Excel worksheet (e.g., 'B').",
        parameters={
            "type": "object",
            "properties": {
                "column_letter": {"type": "string", "description": "The column letter to sum (e.g. 'A', 'B', 'C')"}
            },
            "required": ["column_letter"]
        }
    )
    def excel_sum_column(self, column_letter: str) -> str:
        if not win32com_available:
            return "Excel automation requires win32com package, which is not available."

        col = column_letter.upper().strip()
        try:
            # Bind to active Excel application
            xl = win32com.client.GetObject(Class="Excel.Application")
            xl.Visible = True
            sheet = xl.ActiveSheet
            if not sheet:
                return "Excel is open but there is no active worksheet."

            # Read cells in the specified column until an empty cell is found
            row = 1
            total = 0.0
            number_of_cells = 0
            
            while row <= 1000:  # safety limit
                cell_val = sheet.Range(f"{col}{row}").Value
                if cell_val is None:
                    # Let's check if the next is also empty to decide to break
                    if sheet.Range(f"{col}{row+1}").Value is None:
                        break
                elif isinstance(cell_val, (int, float)):
                    total += cell_val
                    number_of_cells += 1
                row += 1

            return f"✓ Calculated sum for Column {col} (checked {row} rows): **{total}** (Summed {number_of_cells} numeric cells)."
        except Exception as e:
            logger.error("Excel COM summation failed: {}", e)
            return f"Failed to automate active Excel instance: {e}. Make sure an Excel sheet is currently open."

    @skill_tool(
        name="excel_write_cell",
        description="Writes a specific value or formula into a cell of the active Excel worksheet.",
        parameters={
            "type": "object",
            "properties": {
                "cell_address": {"type": "string", "description": "Cell coordinate (e.g. 'A1', 'C4')"},
                "value": {"type": "string", "description": "Value or formula (e.g. '120.5', '=SUM(B1:B10)')"}
            },
            "required": ["cell_address", "value"]
        }
    )
    def excel_write_cell(self, cell_address: str, value: str) -> str:
        if not win32com_available:
            return "Excel automation requires win32com."

        addr = cell_address.upper().strip()
        try:
            xl = win32com.client.GetObject(Class="Excel.Application")
            xl.Visible = True
            sheet = xl.ActiveSheet
            if not sheet:
                return "Excel is open but no active sheet was found."

            # Determine if value is numeric or formula
            val_to_write = value
            if value.startswith("="):
                pass
            else:
                try:
                    val_to_write = float(value) if "." in value else int(value)
                except ValueError:
                    pass

            sheet.Range(addr).Value = val_to_write
            return f"✓ Successfully wrote '{value}' into cell {addr}."
        except Exception as e:
            return f"Excel cell write failed: {e}. Ensure Excel is open."

    @skill_tool(
        name="word_modify_text",
        description="Appends a text paragraph to the active Microsoft Word document and optionally bolds it.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The paragraph text to add"},
                "bold": {"type": "boolean", "description": "Whether to format the new paragraph as bold. Default is false."}
            },
            "required": ["text"]
        }
    )
    def word_modify_text(self, text: str, bold: bool = False) -> str:
        if not win32com_available:
            return "Word automation requires win32com."

        try:
            # Bind to running Word app
            word = win32com.client.GetObject(Class="Word.Application")
            word.Visible = True
            doc = word.ActiveDocument
            if not doc:
                return "Word is open but there is no active document."

            # Add paragraph
            p = doc.Paragraphs.Add()
            p.Range.Text = text + "\n"
            if bold:
                p.Range.Font.Bold = True
                
            return f"✓ Appended paragraph to active document (Bold: {bold})."
        except Exception as e:
            logger.error("Word COM manipulation failed: {}", e)
            return f"Failed to automate active Word instance: {e}. Make sure a Word file is currently open."

    # ── VS Code Assistant ───────────────────────────────────────────────────

    @skill_tool(
        name="vscode_open_project",
        description="Launches VS Code and opens a specific folder or project directory.",
        parameters={
            "type": "object",
            "properties": {
                "folder_path": {"type": "string", "description": "The project path or shortcut name (e.g. 'Documents/JARVIS')"}
            },
            "required": ["folder_path"]
        }
    )
    def vscode_open_project(self, folder_path: str) -> str:
        from pathlib import Path
        user_home = Path.home()
        
        # Resolve shortcut
        path = folder_path.strip()
        if path.lower().startswith("documents"):
            resolved = user_home / "Documents" / path[9:].lstrip("\\/")
        elif path.lower().startswith("desktop"):
            resolved = user_home / "Desktop" / path[7:].lstrip("\\/")
        elif path.startswith("~"):
            resolved = user_home / path[1:].lstrip("\\/")
        else:
            resolved = Path(path)
            if not resolved.is_absolute():
                resolved = user_home / resolved

        if not resolved.exists():
            return f"Directory '{resolved}' does not exist."

        try:
            # Execute "code <path>"
            subprocess.Popen(["code", str(resolved)], shell=True)
            return f"✓ Opened project folder '{resolved}' in VS Code."
        except Exception as e:
            return f"Failed to open VS Code: {e}. Ensure VS Code is in your PATH."

    @skill_tool(
        name="vscode_trigger_debug",
        description="Focusses the VS Code window and triggers debugger run (F5 keystroke).",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def vscode_trigger_debug(self) -> str:
        try:
            # 1. Focus VS Code
            windows = pyautogui.getWindowsWithTitle("Visual Studio Code")
            if not windows:
                # Try partial match
                windows = [w for w in pyautogui.getAllWindows() if "code" in w.title.lower()]

            if not windows:
                return "VS Code window not found."

            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.5)

            # 2. Press F5
            pyautogui.press("f5")
            return "✓ Focussed VS Code and sent F5 (Start Debugging)."
        except Exception as e:
            return f"Failed to trigger VS Code debug: {e}"

    # ── Browser Tab Controls ────────────────────────────────────────────────

    @skill_tool(
        name="browser_control_tabs",
        description="Sends key shortcuts to the active browser to close tabs, open a new tab, or switch to a specific tab index.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["new", "close", "switch"], "description": "Tab modification action"},
                "tab_index": {"type": "integer", "description": "1-based tab index to switch to (e.g. 3 for tab 3)"}
            },
            "required": ["action"]
        }
    )
    def browser_control_tabs(self, action: str, tab_index: Optional[int] = None) -> str:
        try:
            # Ensure browser or web window is active
            active_win = pyautogui.getActiveWindow()
            if not active_win or not any(x in active_win.title.lower() for x in ("chrome", "edge", "firefox", "opera", "browser")):
                logger.warning("Active window '{}' does not seem to be a browser", active_win.title if active_win else "None")

            act = action.lower().strip()
            if act == "new":
                pyautogui.hotkey("ctrl", "t")
                return "✓ Sent Ctrl+T (New Tab) to active application."
            elif act == "close":
                pyautogui.hotkey("ctrl", "w")
                return "✓ Sent Ctrl+W (Close Tab) to active application."
            elif act == "switch" and tab_index is not None:
                # Ctrl+1 to Ctrl+8 switch to specific tabs. Ctrl+9 switches to the last tab.
                t_idx = min(9, max(1, tab_index))
                pyautogui.hotkey("ctrl", str(t_idx))
                return f"✓ Sent Ctrl+{t_idx} (Switch to Tab {t_idx}) to active application."
                
            return "Unsupported browser tab control command."
        except Exception as e:
            return f"Failed browser tab control: {e}"
