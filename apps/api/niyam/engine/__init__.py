"""Niyam Tier A deterministic check engine (stdlib only; no network; no LLM).

    from niyam.engine import load_cards, run_checks
"""
from .cards import load_cards
from .runner import run_checks

__version__ = "0.1.0"
__all__ = ["load_cards", "run_checks", "__version__"]
