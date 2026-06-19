"""
File System Mastery Skill for JARVIS.
Handles file search, copy, move, rename, safe deletion via Recycle Bin,
document templating, auto-sorting directories, and duplicate file checks.
"""

import os
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from send2trash import send2trash

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger


class FileSkill(BaseSkill):
    """Provides modular tools for natural language file operations and system management."""

    def __init__(self, automation_service=None, memory_service=None) -> None:
        self.automation = automation_service
        self.memory = memory_service
        self._user_home = Path.home()

    def _resolve_path(self, path_str: str) -> Path:
        """Resolves shortcuts like Desktop, Documents, Downloads, or user folders."""
        path_str = path_str.strip()
        
        # Replace common directories shortcuts
        lower_str = path_str.lower()
        if lower_str.startswith("desktop"):
            path = self._user_home / "Desktop" / path_str[7:].lstrip("\\/")
        elif lower_str.startswith("documents"):
            path = self._user_home / "Documents" / path_str[9:].lstrip("\\/")
        elif lower_str.startswith("downloads"):
            path = self._user_home / "Downloads" / path_str[9:].lstrip("\\/")
        elif path_str.startswith("~"):
            path = self._user_home / path_str[1:].lstrip("\\/")
        else:
            path = Path(path_str)
            
        # Ensure it's absolute
        if not path.is_absolute():
            path = self._user_home / path
            
        return path

    @skill_tool(
        name="smart_file_search",
        description="Fuzzy searches for files by name, extension, modified date, and text content in directories.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term matching the filename or content."},
                "base_directory": {"type": "string", "description": "Start folder: 'Desktop', 'Documents', 'Downloads', or path. Default is user home."},
                "file_type": {"type": "string", "description": "Filter by type: 'pdf', 'txt', 'docx', 'xlsx', 'jpg', 'png', etc."},
                "days_limit": {"type": "integer", "description": "Limit search to files modified within this many days (e.g. 30 for last month)."}
            },
            "required": ["query"]
        }
    )
    def smart_file_search(
        self, query: str, base_directory: Optional[str] = None, file_type: Optional[str] = None, days_limit: Optional[int] = None
    ) -> str:
        base_dir = self._resolve_path(base_directory) if base_directory else self._user_home
        if not base_dir.exists():
            return f"Directory '{base_dir}' does not exist."

        logger.info("Starting file search for '{}' in '{}'", query, base_dir)
        results = []
        limit_date = datetime.now() - timedelta(days=days_limit) if days_limit else None
        query_lower = query.lower()

        # We will scan up to a max limit of 200 files to keep performance reasonable
        count = 0
        for root, dirs, files in os.walk(base_dir):
            # Prune hidden or system directories to be safe/fast
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ("appdata", "node_modules", "env", "venv")]
            
            for file in files:
                count += 1
                if count > 3000:  # Safety ceiling
                    break
                    
                file_path = Path(root) / file
                
                # Filter by extension
                if file_type and not file.lower().endswith(f".{file_type.lower().lstrip('.')}"):
                    continue
                    
                # Filter by date
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if limit_date and mtime < limit_date:
                        continue
                except Exception:
                    continue

                # Match by filename
                match = False
                if query_lower in file.lower():
                    match = True
                
                # Match by content (for text files up to 2MB)
                elif file.lower().endswith((".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv")):
                    try:
                        if file_path.stat().st_size < 2 * 1024 * 1024:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if query_lower in content.lower():
                                    match = True
                    except Exception:
                        pass
                
                if match:
                    results.append((file_path, mtime))

            if count > 3000:
                break

        if not results:
            return f"No files matching '{query}' were found in '{base_dir}'."

        # Sort by mtime descending (most recent first) and cap display at 15
        results.sort(key=lambda x: x[1], reverse=True)
        summary = [f"Found {len(results)} matching files:"]
        for r_path, r_mtime in results[:15]:
            rel = os.path.relpath(r_path, base_dir)
            size_kb = r_path.stat().st_size / 1024
            summary.append(f"- {rel} ({size_kb:.1f} KB, Modified: {r_mtime.strftime('%Y-%m-%d %H:%M')})")
            
        if len(results) > 15:
            summary.append(f"... and {len(results) - 15} more files.")

        return "\n".join(summary)

    @skill_tool(
        name="copy_file",
        description="Copy a file from source path to destination path.",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path or shortcut (e.g. 'Desktop/test.txt')"},
                "destination": {"type": "string", "description": "Destination folder or filepath"}
            },
            "required": ["source", "destination"]
        }
    )
    def copy_file(self, source: str, destination: str) -> str:
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        
        if not src.exists():
            return f"Source file '{src}' does not exist."
            
        if dst.is_dir():
            dst = dst / src.name
            
        try:
            # Ensure target parent directories exist
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return f"Successfully copied '{src}' to '{dst}'."
        except Exception as e:
            return f"Failed to copy file: {e}"

    @skill_tool(
        name="move_file",
        description="Move a file from source path to destination path.",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source file path"},
                "destination": {"type": "string", "description": "Destination folder or file path"}
            },
            "required": ["source", "destination"]
        }
    )
    def move_file(self, source: str, destination: str) -> str:
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)
        
        if not src.exists():
            return f"Source file '{src}' does not exist."
            
        if dst.is_dir():
            dst = dst / src.name
            
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"Successfully moved '{src}' to '{dst}'."
        except Exception as e:
            return f"Failed to move file: {e}"

    @skill_tool(
        name="rename_file",
        description="Rename a file at a specific path.",
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Absolute path or shortcut of file to rename"},
                "new_name": {"type": "string", "description": "The new filename only (e.g. 'new_resume.docx')"}
            },
            "required": ["filepath", "new_name"]
        }
    )
    def rename_file(self, filepath: str, new_name: str) -> str:
        path = self._resolve_path(filepath)
        if not path.exists():
            return f"File '{path}' does not exist."
            
        target = path.parent / new_name
        try:
            os.rename(path, target)
            return f"Successfully renamed '{path.name}' to '{new_name}'."
        except Exception as e:
            return f"Failed to rename file: {e}"

    @skill_tool(
        name="safe_delete",
        description="Safely delete a file or directory by moving it to the system Recycle Bin (Trash).",
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to file or folder to delete"}
            },
            "required": ["filepath"]
        }
    )
    def safe_delete(self, filepath: str) -> str:
        path = self._resolve_path(filepath)
        if not path.exists():
            return f"File/folder '{path}' does not exist."
            
        try:
            send2trash(str(path))
            return f"✓ Safely moved '{path}' to the Recycle Bin."
        except Exception as e:
            logger.error("Failed to trash file: {}", e)
            return f"Failed to delete file safely: {e}"

    @skill_tool(
        name="append_to_file",
        description="Appends text content to a text file.",
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Filepath to append to"},
                "content": {"type": "string", "description": "Text to append"}
            },
            "required": ["filepath", "content"]
        }
    )
    def append_to_file(self, filepath: str, content: str) -> str:
        path = self._resolve_path(filepath)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            return f"Successfully appended content to '{path}'."
        except Exception as e:
            return f"Failed to write to file: {e}"

    @skill_tool(
        name="create_file_from_template",
        description="Creates a text or markdown file using a pre-defined skeleton layout and variable replacements.",
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Output file path"},
                "template_type": {"type": "string", "description": "Template name: 'meeting_notes', 'todo_list', 'email_draft'"},
                "title": {"type": "string", "description": "Title variable to inject into template"},
                "description": {"type": "string", "description": "Description variable to inject"}
            },
            "required": ["filepath", "template_type"]
        }
    )
    def create_file_from_template(self, filepath: str, template_type: str, title: Optional[str] = None, description: Optional[str] = None) -> str:
        templates = {
            "meeting_notes": (
                "# 📝 Meeting Notes: {title}\n"
                "**Date**: {date}\n\n"
                "## 💬 Agenda / Discussion\n"
                "{description}\n\n"
                "## 📋 Action Items\n"
                "- [ ] Action item 1\n"
                "- [ ] Action item 2\n"
            ),
            "todo_list": (
                "# 🎯 Todo List: {title}\n"
                "**Created**: {date}\n\n"
                "## ⏳ High Priority\n"
                "- [ ] Task A: {description}\n\n"
                "## 📅 Backlog\n"
                "- [ ] Task B\n"
            ),
            "email_draft": (
                "Subject: {title}\n"
                "Date: {date}\n"
                "-----------------------------------------\n"
                "Dear Sir/Madam,\n\n"
                "{description}\n\n"
                "Best regards,\n"
                "JARVIS Assistant\n"
            )
        }
        
        t_type = template_type.lower().strip()
        if t_type not in templates:
            return f"Unsupported template type. Choose from: {list(templates.keys())}"
            
        tpl = templates[t_type]
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        rendered = tpl.format(
            title=title or "Untitled",
            date=date_str,
            description=description or "No description provided."
        )
        
        path = self._resolve_path(filepath)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(rendered)
            return f"✓ Created template file '{t_type}' at '{path}'."
        except Exception as e:
            return f"Failed to create template file: {e}"

    @skill_tool(
        name="auto_sort_downloads",
        description="Scans the user's Downloads folder and organizes files into categorized subfolders by file extension.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def auto_sort_downloads(self) -> str:
        dl_dir = self._user_home / "Downloads"
        if not dl_dir.exists():
            return "Downloads directory not found."

        # Extension category maps
        categories = {
            "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".txt", ".csv", ".rtf"],
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp"],
            "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
            "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Executables": [".exe", ".msi", ".bat", ".cmd"],
        }

        moved_count = 0
        details = []

        try:
            for item in dl_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    target_folder = None
                    
                    for folder, extensions in categories.items():
                        if ext in extensions:
                            target_folder = folder
                            break
                            
                    if not target_folder:
                        target_folder = "Others"

                    dest_dir = dl_dir / target_folder
                    dest_dir.mkdir(exist_ok=True)
                    
                    dest_file = dest_dir / item.name
                    # Handle existing filename collision
                    if dest_file.exists():
                        dest_file = dest_dir / f"{item.stem}_{int(datetime.now().timestamp())}{ext}"
                        
                    shutil.move(str(item), str(dest_file))
                    moved_count += 1
                    details.append(f"Moved '{item.name}' -> '{target_folder}/'")
            
            if moved_count == 0:
                return "Downloads folder is already organized; no files needed sorting."
                
            return f"✓ Organized {moved_count} files in Downloads:\n" + "\n".join(details[:10]) + (f"\n...and {moved_count - 10} more" if moved_count > 10 else "")
        except Exception as e:
            logger.error("Downloads sorting failed: {}", e)
            return f"Failed sorting downloads: {e}"

    @skill_tool(
        name="detect_duplicates",
        description="Checks a directory for duplicate files by comparing MD5 hashes of file contents.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Path or shortcut to check (e.g. 'Downloads')"}
            },
            "required": ["directory"]
        }
    )
    def detect_duplicates(self, directory: str) -> str:
        folder = self._resolve_path(directory)
        if not folder.exists() or not folder.is_dir():
            return f"Directory '{folder}' does not exist or is not a folder."
            
        hashes = {}
        duplicates = []
        
        try:
            # We only scan files in the parent directory to avoid locking down or infinite looping
            for path in folder.iterdir():
                if path.is_file() and not path.name.startswith("."):
                    # Check size first to avoid reading huge files needlessly
                    sz = path.stat().st_size
                    if sz > 50 * 1024 * 1024: # Skip files > 50MB
                        continue
                        
                    try:
                        hasher = hashlib.md5()
                        with open(path, "rb") as f:
                            # Read in chunks
                            buf = f.read(65536)
                            while len(buf) > 0:
                                hasher.update(buf)
                                buf = f.read(65536)
                        md5 = hasher.hexdigest()
                        
                        if md5 in hashes:
                            duplicates.append((path, hashes[md5]))
                        else:
                            hashes[md5] = path
                    except Exception:
                        continue
                        
            if not duplicates:
                return f"No duplicate files detected in '{folder.name}'."
                
            summary = [f"Found {len(duplicates)} duplicate pairs in '{folder.name}':"]
            for dup_path, orig_path in duplicates:
                summary.append(f"- Duplicate: '{dup_path.name}'\n  Original:  '{orig_path.name}'")
            return "\n".join(summary)
        except Exception as e:
            return f"Duplicate detection failed: {e}"
