"""
Deictic Spatial Reference Parser for JARVIS Live Mode 2.0.

Translates natural spatial & relative language references into exact Win32 UIA controls:
- Relative references: "this", "that", "highlighted", "focused", "selected"
- Numerical index references: "first button", "second edit", "third link"
- Display references: "left monitor", "right display", "Monitor 2", "laptop screen"
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from backend.services.perception.uia_scene_graph import SceneGraph, SceneElement
from backend.services.perception.spatial_engine import SpatialEngine


class SpatialRefParser:
    """
    Deictic Spatial Reference Parser resolving natural language UI targets.
    """

    def __init__(self) -> None:
        self.spatial_engine = SpatialEngine()
        logger.info("SpatialRefParser initialized (Deictic Spatial Resolver Ready).")

    def resolve_target(self, text_query: str, scene: SceneGraph) -> Optional[SceneElement]:
        """
        Resolves natural language query (e.g. 'click the second textbox', 'select this button')
        against the active UIA SceneGraph element tree.
        """
        query = text_query.lower().strip()
        elements = scene.elements or []

        if not elements:
            logger.warning("No elements in scene graph to resolve target '{}'", text_query)
            return None

        # 1. Focused / Focused Element Match ("this", "focused", "current")
        if any(k in query for k in ["this", "focused", "current", "active"]):
            if scene.focused_element:
                logger.info("Resolved target '{}' -> Focused Element: {}", text_query, scene.focused_element.name)
                return scene.focused_element

        # 2. Control Type Noun Extraction (button, textbox, edit, checkbox, link, dropdown)
        target_type = None
        if any(k in query for k in ["textbox", "edit", "input", "field"]):
            target_type = "Edit"
        elif any(k in query for k in ["button", "btn", "submit"]):
            target_type = "Button"
        elif any(k in query for k in ["checkbox", "check"]):
            target_type = "CheckBox"
        elif any(k in query for k in ["dropdown", "combobox", "select"]):
            target_type = "ComboBox"

        matching_elements = elements
        if target_type:
            matching_elements = [e for e in elements if e.control_type == target_type]

        if not matching_elements:
            matching_elements = elements

        # 3. Numerical Index Extraction ("first", "second", "third", "2nd", "3rd")
        index = 0
        if "second" in query or "2nd" in query or "#2" in query:
            index = 1
        elif "third" in query or "3rd" in query or "#3" in query:
            index = 2
        elif "fourth" in query or "4th" in query or "#4" in query:
            index = 3
        elif "last" in query:
            index = len(matching_elements) - 1

        if 0 <= index < len(matching_elements):
            resolved = matching_elements[index]
            logger.info("Resolved target '{}' -> Index {} Element: {} ({})", text_query, index + 1, resolved.name, resolved.control_type)
            return resolved

        # 4. Text Label Matching Fallback
        for e in matching_elements:
            if e.name and any(word in e.name.lower() for word in query.split()):
                logger.info("Resolved target '{}' -> Label Match: {}", text_query, e.name)
                return e

        return matching_elements[0] if matching_elements else None

    def resolve_monitor_target(self, query: str) -> Optional[int]:
        """
        Resolves monitor target from query (e.g. 'move to left display', 'Monitor 2').
        Returns monitor index (1-based).
        """
        q = query.lower()
        if "monitor 2" in q or "second display" in q or "right monitor" in q:
            return 2
        elif "monitor 1" in q or "laptop display" in q or "primary screen" in q or "left monitor" in q:
            return 1
        return None
