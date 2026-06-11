"""SM-2 spaced-repetition scheduler, scoped per user.

Quality scale (from the Review step): 0 blackout … 3 hard … 5 perfect.
quality >= 3 is a pass.
"""
from __future__ import annotations

from datetime import date, timedelta

from db import SrsState, Word


def _get_state(db, user_id: int, word: Word) -> SrsState | None:
    return (
        db.query(SrsState)
        .filter(SrsState.user_id == user_id, SrsState.word_id == word.id)
        .first()
    )


def _ensure_state(db, user_id: int, word: Word) -> SrsState:
    state = _get_state(db, user_id, word)
    if state is None:
        state = SrsState(
            user_id=user_id,
            word_id=word.id,
            ease=2.5,
            interval_days=0,
            repetitions=0,
            due_date=date.today(),
        )
        db.add(state)
        db.flush()
    return state


def update(db, user_id: int, word: Word, quality: int, today: date | None = None) -> SrsState:
    today = today or date.today()
    quality = max(0, min(5, int(quality)))
    state = _ensure_state(db, user_id, word)

    if quality < 3:
        state.repetitions = 0
        state.interval_days = 1
    else:
        if state.repetitions == 0:
            state.interval_days = 1
        elif state.repetitions == 1:
            state.interval_days = 6
        else:
            state.interval_days = round(state.interval_days * state.ease)
        state.repetitions += 1

    state.ease = max(
        1.3,
        state.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
    )
    state.last_review = today
    state.due_date = today + timedelta(days=state.interval_days)
    db.flush()
    return state


def due_words(db, user_id: int, today: date | None = None, limit: int = 20):
    """Return [(Word, SrsState)] due today or earlier, soonest first."""
    today = today or date.today()
    return (
        db.query(Word, SrsState)
        .join(SrsState, SrsState.word_id == Word.id)
        .filter(SrsState.user_id == user_id, SrsState.due_date <= today)
        .order_by(SrsState.due_date.asc())
        .limit(limit)
        .all()
    )


def enroll(db, user_id: int, word: Word, today: date | None = None) -> SrsState:
    today = today or date.today()
    state = _ensure_state(db, user_id, word)
    if state.due_date is None:
        state.due_date = today
    db.flush()
    return state
