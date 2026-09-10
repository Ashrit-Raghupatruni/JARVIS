"""
JARVIS AI OS - Message Router Facade.
Re-exports RequestCategory and classify_request from backend.agents.router for unified routing.
"""

from backend.agents.router import RequestCategory, classify_request

__all__ = ["RequestCategory", "classify_request"]

