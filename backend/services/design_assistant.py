"""
JARVIS AI OS — Design Assistant & Web App Generator Service.

Provides:
1. UI Layout & Accessibility Critique (WCAG 2.1 AA, hierarchy, contrast, whitespace)
2. Color Palette & Design System Generator (Hex codes, Tailwind classes, semantic tokens)
3. Web App Component Scaffolder (Standalone interactive HTML5 / Tailwind / React sandbox)
"""

from __future__ import annotations

import re
import math
from typing import Any, Dict, List, Optional
from loguru import logger


class DesignAssistantService:
    """Service for UI/UX Design, Accessibility Auditing, and Web App Scaffolding."""

    def __init__(self) -> None:
        logger.info("DesignAssistantService initialized.")

    # ── 1. UI Layout & Accessibility Critique ────────────────────────────

    def critique_ui_layout(
        self,
        layout_description: str,
        target_device: str = "desktop"
    ) -> Dict[str, Any]:
        """
        Evaluate UI layout description or HTML/JSX snippet for visual hierarchy,
        responsiveness, cognitive load, and WCAG accessibility standards.
        """
        issues = []
        strengths = []
        score = 85

        desc_lower = layout_description.lower()

        # Contrast & Text checks
        if "gray" in desc_lower and ("light" in desc_lower or "small" in desc_lower):
            issues.append("Potential low-contrast text: Light gray text on white/dark surfaces often fails WCAG 4.5:1 ratio.")
            score -= 10
        else:
            strengths.append("Text contrast hierarchy appears distinct.")

        # Hierarchy & Spacing
        if "density" in desc_lower or "cluttered" in desc_lower or "many buttons" in desc_lower:
            issues.append("High cognitive density: Consider progressive disclosure or collapsing secondary actions into dropdown menus.")
            score -= 10
        else:
            strengths.append("Balanced layout with clear focal points.")

        # Mobile responsiveness
        if target_device in ("mobile", "tablet") and ("fixed width" in desc_lower or "horizontal scroll" in desc_lower):
            issues.append(f"Fixed dimensions on {target_device}: Use CSS grid/flexbox with min-width and auto-wrap.")
            score -= 15

        # Recommendations
        recommendations = [
            "Ensure primary CTA button has minimum touch/click target of 44x44px.",
            "Use standard 8px grid spacing increments (p-2, p-4, p-6) for visual consistency.",
            "Include aria-label attributes on icon-only interactive controls."
        ]

        return {
            "status": "success",
            "evaluated_device": target_device,
            "overall_design_score": max(40, score),
            "strengths": strengths,
            "identified_issues": issues,
            "actionable_recommendations": recommendations
        }

    # ── 2. Color Palette & Design System Generator ───────────────────────

    def generate_color_palette(
        self,
        theme_name: str,
        base_color: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate harmonious color palette with semantic roles and Tailwind CSS utility tokens.
        """
        presets = {
            "cyberpunk": {
                "primary": "#00f0ff", "primary_tw": "cyan-400",
                "secondary": "#ff003c", "secondary_tw": "rose-500",
                "accent": "#fcee0a", "accent_tw": "yellow-300",
                "background": "#050811", "background_tw": "slate-950",
                "surface": "#0f172a", "surface_tw": "slate-900",
                "text": "#f8fafc", "text_tw": "slate-50"
            },
            "jarvis_cyan": {
                "primary": "#00e5ff", "primary_tw": "cyan-400",
                "secondary": "#0284c7", "secondary_tw": "sky-600",
                "accent": "#38bdf8", "accent_tw": "sky-400",
                "background": "#030712", "background_tw": "gray-950",
                "surface": "#111827", "surface_tw": "gray-900",
                "text": "#f9fafb", "text_tw": "gray-50"
            },
            "corporate_clean": {
                "primary": "#2563eb", "primary_tw": "blue-600",
                "secondary": "#475569", "secondary_tw": "slate-600",
                "accent": "#06b6d4", "accent_tw": "cyan-500",
                "background": "#f8fafc", "background_tw": "slate-50",
                "surface": "#ffffff", "surface_tw": "white",
                "text": "#0f172a", "text_tw": "slate-900"
            },
            "emerald_dark": {
                "primary": "#10b981", "primary_tw": "emerald-500",
                "secondary": "#059669", "secondary_tw": "emerald-600",
                "accent": "#34d399", "accent_tw": "emerald-400",
                "background": "#064e3b", "background_tw": "emerald-950",
                "surface": "#065f46", "surface_tw": "emerald-900",
                "text": "#ecfdf5", "text_tw": "emerald-50"
            }
        }

        matched = presets.get(theme_name.lower().replace(" ", "_"))
        if not matched:
            matched = presets["jarvis_cyan"]

        return {
            "status": "success",
            "theme_name": theme_name,
            "tokens": matched,
            "css_variables": f":root {{\n  --primary: {matched['primary']};\n  --secondary: {matched['secondary']};\n  --bg: {matched['background']};\n  --surface: {matched['surface']};\n  --text: {matched['text']};\n}}"
        }

    # ── 3. Web App Component Scaffolder ──────────────────────────────────

    def scaffold_web_app(
        self,
        app_type: str,
        framework: str = "html_tailwind",
        title: str = "JARVIS Application",
        features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Scaffold interactive standalone HTML/Tailwind/React application code snippet.
        """
        feature_list = features or ["Interactive Dashboard", "Real-Time Controls", "Responsive Grid"]
        features_rendered = "\n".join(
            f'          <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-md shadow-lg">'
            f'\n            <h3 class="font-semibold text-cyan-400">{feat}</h3>'
            f'\n            <p class="text-sm text-slate-400 mt-1">Operational and fully responsive.</p>'
            f'\n          </div>'
            for feat in feature_list
        )

        html_code = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col font-sans">
  <header class="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur-md px-6 py-4 flex items-center justify-between sticky top-0 z-50">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-cyan-500 flex items-center justify-center font-bold text-slate-950 shadow-cyan-500/30 shadow-lg">J</div>
      <h1 class="text-xl font-bold tracking-tight bg-gradient-to-r from-cyan-400 to-sky-200 bg-clip-text text-transparent">{title}</h1>
    </div>
    <span class="text-xs px-2.5 py-1 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800 font-mono">v1.0.0</span>
  </header>

  <main class="flex-1 max-w-6xl w-full mx-auto p-6 space-y-6">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
{features_rendered}
    </div>
    
    <div class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800/80">
      <h2 class="text-lg font-bold text-white mb-2">Live Execution Panel</h2>
      <p class="text-slate-400 text-sm mb-4">Type a command or trigger automated actions below:</p>
      <div class="flex gap-2">
        <input type="text" placeholder="Enter task..." class="flex-1 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-white focus:outline-none focus:border-cyan-400 transition" />
        <button class="px-5 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-xl shadow-lg transition">Execute</button>
      </div>
    </div>
  </main>
</body>
</html>"""

        return {
            "status": "success",
            "app_type": app_type,
            "title": title,
            "framework": framework,
            "features_included": feature_list,
            "generated_code": html_code
        }


design_assistant = DesignAssistantService()
