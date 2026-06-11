"""SQLAlchemy models + session helpers.

Multi-user: `words` is the shared NGSL catalog; every learner has their own
vocabulary state (`user_words`), SRS rows, lessons, progress, productions and
settings, all scoped by user_id. Auth is username/password with bearer tokens.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}, future=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    name = Column(String, default="")
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Word(Base):
    """Shared NGSL catalog (no per-user state here)."""

    __tablename__ = "words"

    id = Column(Integer, primary_key=True)
    rank = Column(Integer, index=True)
    headword = Column(String, unique=True, index=True)
    source = Column(String)
    forms = Column(Text, default="")
    # Meaning stored ONCE on the shared catalog (no per-user, no runtime LLM).
    en_def = Column(Text, default="")
    vi = Column(Text, default="")
    example = Column(Text, default="")


class UserWord(Base):
    """Per-learner vocabulary state: locked -> learning -> known."""

    __tablename__ = "user_words"
    __table_args__ = (UniqueConstraint("user_id", "word_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    word_id = Column(Integer, ForeignKey("words.id"), index=True)
    status = Column(String, default="locked", index=True)
    added_on = Column(Date, default=date.today)
    # Meaning captured when the word was learned (for flashcards).
    en_def = Column(Text, default="")
    vi = Column(Text, default="")
    example = Column(Text, default="")


class SrsState(Base):
    __tablename__ = "srs_state"
    __table_args__ = (UniqueConstraint("user_id", "word_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    word_id = Column(Integer, ForeignKey("words.id"), index=True)
    ease = Column(Float, default=2.5)
    interval_days = Column(Integer, default=0)
    repetitions = Column(Integer, default=0)
    due_date = Column(Date, index=True)
    last_review = Column(Date, nullable=True)


class Lesson(Base):
    """A lesson in the SHARED curriculum bank (same for every account)."""

    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)
    seq = Column(Integer, index=True)  # 1..N curriculum order ('order' is reserved)
    theme = Column(String)
    dialogue_json = Column(Text)
    targets_json = Column(Text)
    speaking_prompts_json = Column(Text, default="[]")
    speaking_script_json = Column(Text, default="[]")
    produce_prompt = Column(Text, default="")
    grammar_id = Column(String)
    grammar_json = Column(Text, default="{}")
    coverage_pct = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class LessonProgress(Base):
    """Which shared lessons a given user has completed."""

    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), index=True)
    completed_at = Column(DateTime, default=datetime.utcnow)


class SessionLog(Base):
    __tablename__ = "session_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    completed_steps = Column(String, default="")
    errors_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    date = Column(Date, index=True)
    known_count = Column(Integer, default=0)
    coverage_pct = Column(Float, default=0.0)
    streak = Column(Integer, default=0)


class Setting(Base):
    __tablename__ = "settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    key = Column(String, primary_key=True)
    value = Column(String)


class UserGrammar(Base):
    """Per-learner grammar progress (which points have been taught)."""

    __tablename__ = "user_grammar"
    __table_args__ = (UniqueConstraint("user_id", "grammar_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    grammar_id = Column(String, index=True)
    status = Column(String, default="learning")  # learning|known
    added_on = Column(Date, default=date.today)


class Conversation(Base):
    """A saved speaking-practice transcript, for later review."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)
    theme = Column(String, default="")
    turns_json = Column(Text, default="[]")  # [{role, en, vi}]
    created_at = Column(DateTime, default=datetime.utcnow)


class Production(Base):
    __tablename__ = "productions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    text = Column(Text)
    coverage_pct = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Add columns introduced after a table first existed (SQLite), preserving
    data instead of forcing a re-ingest. New tables are handled by create_all."""
    with engine.begin() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(lessons)")]
        if "grammar_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE lessons ADD COLUMN grammar_id VARCHAR")
        if "grammar_json" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE lessons ADD COLUMN grammar_json TEXT DEFAULT '{}'"
            )
        if "seq" not in cols:
            conn.exec_driver_sql("ALTER TABLE lessons ADD COLUMN seq INTEGER")

        uw = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(user_words)")]
        for col in ("en_def", "vi", "example"):
            if uw and col not in uw:
                conn.exec_driver_sql(
                    f"ALTER TABLE user_words ADD COLUMN {col} TEXT DEFAULT ''"
                )

        wc = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(words)")]
        for col in ("en_def", "vi", "example"):
            if wc and col not in wc:
                conn.exec_driver_sql(
                    f"ALTER TABLE words ADD COLUMN {col} TEXT DEFAULT ''"
                )


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
