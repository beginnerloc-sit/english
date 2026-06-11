"""Loads the authored grammar spine (data/grammar.json).

Explanations are AUTHORED, never generated. Lessons advance through these points
in `order`; the lesson generator uses `structure_hint`/`examples` to shape the
dialogue, and the app shows `explanation`/`vi_note`/`examples`/`frames`.
"""
from __future__ import annotations

import json

from config import DATA_DIR

_PATH = DATA_DIR / "grammar.json"


def _load() -> list[dict]:
    try:
        with _PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return sorted(data.get("points", []), key=lambda p: p.get("order", 0))
    except Exception as exc:  # missing/malformed -> grammar feature degrades off
        print(f"[grammar] could not load {_PATH}: {exc}")
        return []


GRAMMAR_POINTS = _load()
GRAMMAR_BY_ID = {p["id"]: p for p in GRAMMAR_POINTS}


def public(point: dict | None) -> dict:
    """Trim a grammar point to what the client/lesson needs."""
    if not point:
        return {}
    return {
        "id": point.get("id"),
        "title": point.get("title"),
        "level": point.get("level"),
        "structure_hint": point.get("structure_hint"),
        "explanation": point.get("explanation"),
        "vi_note": point.get("vi_note"),
        "examples": point.get("examples", []),
        "frames": point.get("frames", []),
    }
