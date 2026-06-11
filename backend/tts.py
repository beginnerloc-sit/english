"""Text-to-speech via OpenAI's audio API, with an on-disk cache.

The browser's built-in speechSynthesis is monotone; OpenAI voices are far more
natural, which matters a lot for a listening-focused beginner. We cache each
clip by (model, voice, speed, text) so repeated words/lines (review cards, replay
buttons) are instant and free after the first synthesis.

Model/voice ids change — they're config-driven; verify against OpenAI docs.
"""
from __future__ import annotations

import hashlib

from config import (
    DATA_DIR,
    HAS_OPENAI,
    OPENAI_API_KEY,
    OPENAI_TTS_MODEL,
    OPENAI_TTS_VOICE,
)

CACHE_DIR = DATA_DIR / "tts_cache"


def synthesize(text: str, speed: float = 0.95, voice: str | None = None) -> bytes:
    """Return MP3 bytes for `text`. Raises RuntimeError without an API key."""
    if not HAS_OPENAI:
        raise RuntimeError("OPENAI_API_KEY not configured; TTS unavailable.")

    text = (text or "").strip()
    if not text:
        return b""
    voice = voice or OPENAI_TTS_VOICE
    speed = max(0.25, min(4.0, float(speed)))

    key = hashlib.md5(
        f"{OPENAI_TTS_MODEL}|{voice}|{speed}|{text}".encode("utf-8")
    ).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.mp3"
    if path.exists():
        return path.read_bytes()

    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    kwargs = dict(
        model=OPENAI_TTS_MODEL,
        voice=voice,
        input=text,
        response_format="mp3",
        speed=speed,
    )
    try:
        resp = client.audio.speech.create(**kwargs)
    except TypeError:
        # Some models don't accept `speed`; retry without it.
        kwargs.pop("speed", None)
        resp = client.audio.speech.create(**kwargs)

    audio = resp.content if hasattr(resp, "content") else resp.read()
    path.write_bytes(audio)
    return audio
