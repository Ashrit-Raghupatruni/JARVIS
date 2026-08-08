"""
JARVIS AI Operating System - Strategy Memory & Dynamic Confidence System.

Stores procedure-based strategies (how to open app, preferred selectors, window detection)
and maintains dynamic confidence scores:
- Win32 UI Automation: 95% baseline
- Browser Playwright: 92% baseline
- OCR Screen Detection: 70% baseline
- Pixel Clicking: 40% baseline

Always selects and executes the highest-confidence strategy first. Updates strategy confidence
weights dynamically based on historical success and recovery rates.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


class StrategyMemoryService:
    """Strategy Memory Service for procedure storage and dynamic confidence scoring."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or Path("data/strategy_memory.json")
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.strategies: Dict[str, List[Dict[str, Any]]] = self._load_strategies()
        logger.info("StrategyMemoryService initialized. File: {}", self.data_file)

    def _load_strategies(self) -> Dict[str, List[Dict[str, Any]]]:
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not load strategy memory JSON: {}", e)
        
        # Default baseline strategy rankings
        return {
            "ui_automation": [
                {"strategy": "win32_uia", "name": "Native Win32 Accessibility HWND Tree", "confidence": 0.95, "success_count": 48, "fail_count": 2},
                {"strategy": "browser_playwright", "name": "Playwright Browser Selector", "confidence": 0.92, "success_count": 35, "fail_count": 3},
                {"strategy": "ocr_screen", "name": "Tesseract/OpenCV Screen Bounds OCR", "confidence": 0.70, "success_count": 12, "fail_count": 5},
                {"strategy": "pixel_clicking", "name": "Hardcoded Pixel Coordinate Click", "confidence": 0.40, "success_count": 4, "fail_count": 6}
            ],
            "file_search": [
                {"strategy": "sqlite_fts5", "name": "SQLite FTS5 Natural Language Indexer", "confidence": 0.98, "success_count": 120, "fail_count": 0},
                {"strategy": "python_os_walk", "name": "Python os.walk Recursive Search", "confidence": 0.85, "success_count": 15, "fail_count": 2}
            ],
            "app_launch": [
                {"strategy": "shutil_which", "name": "PATH Executable Resolution", "confidence": 0.96, "success_count": 65, "fail_count": 1},
                {"strategy": "win32_start", "name": "Windows Shell Execute", "confidence": 0.90, "success_count": 40, "fail_count": 4}
            ]
        }

    def _save_strategies(self) -> None:
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.strategies, f, indent=2)
        except Exception as e:
            logger.error("Failed to save strategy memory JSON: {}", e)

    def get_ranked_strategies(self, category: str = "ui_automation") -> List[Dict[str, Any]]:
        """Return strategies ranked by dynamic confidence score (descending)."""
        strats = self.strategies.get(category, [])
        return sorted(strats, key=lambda x: x.get("confidence", 0.5), reverse=True)

    def get_preferred_strategy(self, category: str = "ui_automation") -> Dict[str, Any]:
        """Get highest confidence strategy for a given category."""
        ranked = self.get_ranked_strategies(category)
        if ranked:
            return ranked[0]
        return {"strategy": "win32_uia", "confidence": 0.95, "name": "Default Win32 UIA"}

    def update_strategy_outcome(self, category: str, strategy_id: str, reward: float) -> None:
        """Update confidence score dynamically based on reward/penalty outcomes.
        
        Reward mappings:
        - Successful task: +1
        - Excellent result: +2
        - Partial success: +0.5
        - User correction: -1
        - Task failure: -2
        - Repeated failure: -3
        """
        strats = self.strategies.get(category, [])
        for s in strats:
            if s.get("strategy") == strategy_id:
                # Adjust confidence based on reward
                change = reward * 0.05
                s["confidence"] = max(0.10, min(0.99, s.get("confidence", 0.5) + change))
                if reward > 0:
                    s["success_count"] = s.get("success_count", 0) + 1
                else:
                    s["fail_count"] = s.get("fail_count", 0) + 1
                break
        
        self.strategies[category] = strats
        self._save_strategies()
        logger.info("📈 Updated strategy confidence: {} -> {} (reward={}, confidence={:.2f})", category, strategy_id, reward, s.get("confidence", 0.0))

