"""Central configuration, loaded from environment / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini").strip()
# Omitted by default (newer gpt-5.x models only accept the default temperature).
# Set OPENAI_TEMPERATURE in .env to override on models that support it.
_temp = os.getenv("OPENAI_TEMPERATURE", "").strip()
OPENAI_TEMPERATURE = float(_temp) if _temp else None
# Fast/cheap model for live subtitle translation (keep snappy during a session).
OPENAI_TRANSLATE_MODEL = os.getenv("OPENAI_TRANSLATE_MODEL", "gpt-4o-mini").strip()
# Realtime defaults follow the current OpenAI voice-agents docs (verify at build
# time — these change often). gpt-realtime-2 is the reasoning voice model.
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2").strip()
OPENAI_REALTIME_VOICE = os.getenv("OPENAI_REALTIME_VOICE", "alloy").strip()
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-realtime-whisper").strip()
# Reading voice (TTS) for dialogue/word playback — natural OpenAI voices.
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip()
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "nova").strip()
# Speech-to-text for the read-aloud step (record -> upload -> transcribe).
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "whisper-1").strip()

BOOTSTRAP_KNOWN_COUNT = int(os.getenv("BOOTSTRAP_KNOWN_COUNT", "100"))
TARGETS_PER_LESSON = int(os.getenv("TARGETS_PER_LESSON", "6"))
COVERAGE_THRESHOLD = float(os.getenv("COVERAGE_THRESHOLD", "95"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'lingualoop.db'}")

# The learner's interests — themes rotate through these (README section 1).
# A wide spread keeps daily input personally compelling (the #1 motivation lever).
INTERESTS = [
    "gym and fitness",
    "tech gadgets and phones",
    "fashion and streetwear",
    "food and cooking",
    "travel and new places",
    "music and concerts",
    "movies and TV shows",
    "cars and motorbikes",
    "daily routine and habits",
    "shopping and saving money",
    "weather and the seasons",
    "health, sleep and energy",
    "pets and animals",
    "social media and the internet",
    "weekend plans with friends",
    "coffee, tea and drinks",
    "nature and the outdoors",
    "your hometown and family",
]

HAS_OPENAI = bool(OPENAI_API_KEY)
