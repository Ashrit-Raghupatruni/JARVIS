"""
Prash — Custom Local AI Engine for JARVIS.

A fully self-contained transformer-based language model with its own
tokenizer, training pipeline, and inference engine. No external AI
APIs required — built entirely with PyTorch.
"""

from backend.prash.engine import PrashEngine

__all__ = ["PrashEngine"]
__version__ = "0.1.0"
