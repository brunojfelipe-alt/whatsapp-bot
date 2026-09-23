"""Reexport para compatibilidade (`scripts/setup_instance.py` importa daqui).

A implementação vive em `app.channels.evolution`.
"""
from __future__ import annotations

from app.channels.evolution import EvolutionClient

__all__ = ["EvolutionClient"]
