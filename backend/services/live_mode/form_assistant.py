"""
JARVIS AI OS - Smart Form Parsing & Data Auto-Filling Engine.

Detects textboxes, dropdowns, checkboxes, date pickers, OTP fields,
maps data from memory profiles, and performs pre-submission data validation.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.services.perception.uia_scene_graph import SceneElement


class FormAssistant:
    """
    Smart Form Analysis, Profile Mapping, and Data Transformation Service.
    """

    def __init__(self) -> None:
        self.default_profile = {
            "name": "Ashrit Raghupatruni",
            "first_name": "Ashrit",
            "last_name": "Raghupatruni",
            "email": "ashrit@example.com",
            "phone": "+1 555-0199",
            "address": "123 Innovation Way, Suite 400",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "country": "United States"
        }

    def detect_form_fields(self, elements: List[SceneElement]) -> List[Dict[str, Any]]:
        """Identify form input fields and match them to profile keys."""
        form_fields = []
        for elem in elements:
            ctrl_type = elem.control_type.lower()
            name_lower = elem.name.lower()

            if ctrl_type in ("edit", "combobox", "checkbox", "radiobutton", "document"):
                field_key = self._guess_field_key(name_lower)
                form_fields.append({
                    "id": elem.id,
                    "label": elem.name,
                    "control_type": elem.control_type,
                    "suggested_key": field_key,
                    "current_value": elem.value or "",
                    "bounds": elem.bounds
                })

        return form_fields

    def _guess_field_key(self, label: str) -> Optional[str]:
        label = label.lower()
        if "first name" in label or "given name" in label:
            return "first_name"
        elif "last name" in label or "surname" in label or "family name" in label:
            return "last_name"
        elif "full name" in label or "name" in label:
            return "name"
        elif "email" in label or "e-mail" in label:
            return "email"
        elif "phone" in label or "mobile" in label or "contact" in label or "tel" in label:
            return "phone"
        elif "address" in label or "street" in label:
            return "address"
        elif "city" in label or "town" in label:
            return "city"
        elif "state" in label or "province" in label:
            return "state"
        elif "zip" in label or "postal" in label or "pincode" in label:
            return "zip"
        elif "country" in label:
            return "country"
        return None

    def transform_and_validate(self, text_val: str, field_type: str = "general") -> Tuple[str, bool, Optional[str]]:
        """
        Intelligently format and validate text before insertion into active UI controls.
        Returns: (transformed_text, is_valid, validation_error)
        """
        val = text_val.strip()
        if not val:
            return ("", True, None)

        if field_type == "email" or "@" in val:
            email_pattern = r"^[^@]+@[^@]+\.[^@]+$"
            if not re.match(email_pattern, val):
                return (val.lower(), False, "Invalid email format")
            return (val.lower(), True, None)

        elif field_type == "phone":
            digits = re.sub(r"[^\d+]", "", val)
            return (digits, True, None)

        elif field_type == "uppercase":
            return (val.upper(), True, None)

        elif field_type == "capitalize":
            return (val.title(), True, None)

        return (val, True, None)

    def auto_fill_map(self, form_fields: List[Dict[str, Any]], custom_profile: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Generate automatic mapping pairs between active form fields and profile data."""
        profile = custom_profile or self.default_profile
        actions = []

        for field in form_fields:
            key = field.get("suggested_key")
            if key and key in profile:
                val = profile[key]
                transformed_val, is_valid, err = self.transform_and_validate(val, field_type=key)
                actions.append({
                    "field_id": field["id"],
                    "label": field["label"],
                    "value": transformed_val,
                    "is_valid": is_valid,
                    "validation_error": err
                })

        return actions
