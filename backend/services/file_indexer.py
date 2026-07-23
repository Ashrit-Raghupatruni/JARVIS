"""
JARVIS AI Operating System - Local SQLite FTS5 File Indexer Service.

Provides high-speed natural language file search across local documents,
source code, and downloaded files using SQLite Full-Text Search (FTS5).
"""

import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


class FileIndexerService:
    """SQLite FTS5 Natural Language File Indexer Engine."""

    def __init__(self, db_path: str = "data/file_index.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_fts5_db()

    def _init_fts5_db(self) -> None:
        """Initialize SQLite FTS5 virtual table for file search."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            
            # Create FTS5 virtual table for text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS file_fts USING fts5(
                    filename,
                    filepath,
                    extension,
                    content_preview,
                    modified_timestamp UNINDEXED
                );
            """)
            conn.commit()
            conn.close()
            logger.info("✓ SQLite FTS5 File Indexer initialized at {}", self.db_path)
        except Exception as e:
            logger.error(f"FTS5 File Indexer setup failed: {e}")

    def index_directory(self, target_dir: str, max_files: int = 500) -> Dict[str, Any]:
        """Recursively scan and index file metadata into FTS5 table."""
        path = Path(target_dir)
        if not path.exists() or not path.is_dir():
            return {"error": f"Directory '{target_dir}' does not exist."}

        indexed_count = 0
        start_time = time.time()

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            for root, _, files in os.walk(path):
                if indexed_count >= max_files:
                    break
                for fname in files:
                    if fname.startswith(".") or fname.endswith((".exe", ".dll", ".pyd", ".zip", ".iso")):
                        continue
                    
                    fpath = Path(root) / fname
                    try:
                        stat = fpath.stat()
                        mtime = stat.st_mtime
                        ext = fpath.suffix.lower()

                        # Clear old record
                        cursor.execute("DELETE FROM file_fts WHERE filepath = ?", (str(fpath.resolve()),))
                        
                        # Read small text snippet if text file
                        snippet = ""
                        if ext in (".txt", ".md", ".py", ".json", ".js", ".ts", ".html", ".css", ".csv"):
                            try:
                                with open(fpath, "r", encoding="utf-8", errors="ignore") as tf:
                                    snippet = tf.read(500)
                            except Exception:
                                pass

                        cursor.execute("""
                            INSERT INTO file_fts (filename, filepath, extension, content_preview, modified_timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        """, (fname, str(fpath.resolve()), ext, snippet, mtime))

                        indexed_count += 1
                    except Exception:
                        continue

            conn.commit()
            conn.close()
            elapsed = time.time() - start_time
            logger.info(f"FTS5 File Indexer indexed {indexed_count} files in {elapsed:.2f}s")
            return {
                "status": "success",
                "indexed_files": indexed_count,
                "duration_seconds": round(elapsed, 2)
            }
        except Exception as e:
            logger.error(f"Error during file indexing: {e}")
            return {"error": str(e)}

    def search_files(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Perform sub-second natural language match using FTS5 match query."""
        if not self.db_path.exists():
            return []

        clean_query = query.replace("'", " ").replace('"', ' ').strip()
        if not clean_query:
            return []

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Format FTS match string
            words = [w for w in clean_query.split() if len(w) > 1]
            fts_match_query = " OR ".join(f"{w}*" for w in words) if words else clean_query

            cursor.execute("""
                SELECT filename, filepath, extension, content_preview, modified_timestamp
                FROM file_fts
                WHERE file_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (fts_match_query, limit))

            rows = cursor.fetchall()
            conn.close()

            results = []
            for r in rows:
                results.append({
                    "filename": r[0],
                    "filepath": r[1],
                    "extension": r[2],
                    "snippet": r[3],
                    "modified_timestamp": r[4]
                })

            return results
        except Exception as e:
            logger.error(f"FTS5 file search error: {e}")
            return []
