"""Card loading. Cards are plain dicts (the JSON files under rules/cards/); the engine never mutates them."""
from __future__ import annotations

import json
from pathlib import Path

_REQUIRED = ("id", "version", "status", "check", "source", "scope", "effective_from")


def load_cards(cards_dir) -> list[dict]:
    """Load every ``*.json`` card in ``cards_dir`` (sorted by file name). Raises ValueError on a malformed card."""
    out: list[dict] = []
    for p in sorted(Path(cards_dir).glob("*.json")):
        with open(p, "r", encoding="utf-8") as fh:
            card = json.load(fh)
        missing = [k for k in _REQUIRED if k not in card]
        if missing:
            raise ValueError(f"{p.name}: missing keys {missing}")
        out.append(card)
    return out
