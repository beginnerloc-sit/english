"""LinguaLoop FastAPI app — multi-user (auth) with per-learner data."""
from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

import srs
from auth import hash_password, new_token, verify_password
from config import COVERAGE_THRESHOLD, HAS_OPENAI, INTERESTS, TARGETS_PER_LESSON, BOOTSTRAP_KNOWN_COUNT
from db import (
    AuthToken,
    Conversation,
    Lesson,
    LessonProgress,
    Production,
    Progress,
    SessionLog,
    Setting,
    SrsState,
    User,
    UserGrammar,
    UserWord,
    Word,
    get_session,
    init_db,
)
import grammar as grammar_kb
from profiler import known_set, reset_cache, score
from realtime import mint_token

app = FastAPI(title="GetRichz", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    reset_cache()


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def current_user(
    authorization: str = Header(None), db: Session = Depends(get_session)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    row = db.get(AuthToken, token)
    user = db.get(User, row.user_id) if row else None
    if user is None:
        raise HTTPException(401, "Invalid or expired session")
    return user


def _issue_token(db: Session, user_id: int) -> str:
    token = new_token()
    db.add(AuthToken(token=token, user_id=user_id))
    db.commit()
    return token


def _seed_user_vocab(db: Session, user_id: int) -> None:
    """Give a new account its starting vocabulary: top N known, rest locked."""
    words = db.query(Word).all()
    for w in words:
        db.add(
            UserWord(
                user_id=user_id,
                word_id=w.id,
                status="known" if (w.rank or 0) <= BOOTSTRAP_KNOWN_COUNT else "locked",
            )
        )
    db.commit()


class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_session)):
    uname = req.username.strip().lower()
    if not uname or not req.password:
        raise HTTPException(400, "Username and password are required")
    if len(req.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    if db.query(User).filter(User.username == uname).first():
        raise HTTPException(409, "That username is taken")
    user = User(
        username=uname,
        name=(req.name.strip() or req.username.strip()),
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _seed_user_vocab(db, user.id)
    token = _issue_token(db, user.id)
    return {"token": token, "username": user.username, "name": user.name}


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.username == req.username.strip().lower()).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Wrong username or password")
    token = _issue_token(db, user.id)
    return {"token": token, "username": user.username, "name": user.name}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "name": user.name}


@app.post("/auth/logout")
def logout(authorization: str = Header(None), db: Session = Depends(get_session)):
    if authorization and authorization.startswith("Bearer "):
        row = db.get(AuthToken, authorization.split(" ", 1)[1].strip())
        if row:
            db.delete(row)
            db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Settings helpers (per user)
# --------------------------------------------------------------------------- #
def _get_setting(db: Session, user_id: int, key: str, default=None):
    row = db.get(Setting, (user_id, key))
    return row.value if row else default


def _set_setting(db: Session, user_id: int, key: str, value: str) -> None:
    row = db.get(Setting, (user_id, key))
    if row:
        row.value = value
    else:
        db.add(Setting(user_id=user_id, key=key, value=value))
    db.commit()


# --------------------------------------------------------------------------- #
# Lessons (shared bank + per-user progress)
# --------------------------------------------------------------------------- #
def _completed_ids(db: Session, user_id: int) -> set[int]:
    return {
        lp.lesson_id
        for lp in db.query(LessonProgress.lesson_id)
        .filter(LessonProgress.user_id == user_id)
        .all()
    }


def _serialize_lesson(lesson: Lesson, completed: bool = False) -> dict:
    return {
        "id": lesson.id,
        "seq": lesson.seq,
        "theme": lesson.theme,
        "dialogue": json.loads(lesson.dialogue_json),
        "target_words": json.loads(lesson.targets_json),
        "speaking_prompts": json.loads(lesson.speaking_prompts_json or "[]"),
        "speaking_script": json.loads(lesson.speaking_script_json or "[]"),
        "grammar": json.loads(lesson.grammar_json or "{}"),
        "coverage_pct": lesson.coverage_pct,
        "completed": completed,
    }


@app.get("/lessons")
def list_lessons(user: User = Depends(current_user), db: Session = Depends(get_session)):
    """The whole shared lesson bank, with this user's completion status."""
    done = _completed_ids(db, user.id)
    lessons = db.query(Lesson).order_by(Lesson.seq.asc()).all()
    next_seq = None
    for ls in lessons:
        if ls.id not in done:
            next_seq = ls.seq
            break
    return {
        "next_seq": next_seq,
        "lessons": [
            {
                "id": ls.id,
                "seq": ls.seq,
                "theme": ls.theme,
                "grammar": json.loads(ls.grammar_json or "{}").get("title"),
                "level": json.loads(ls.grammar_json or "{}").get("level") or "",
                "word_count": len(json.loads(ls.targets_json or "[]")),
                "completed": ls.id in done,
                "is_next": ls.seq == next_seq,
            }
            for ls in lessons
        ],
    }


@app.get("/lesson/today")
def lesson_today(user: User = Depends(current_user), db: Session = Depends(get_session)):
    """The next lesson the user hasn't completed (or the first one)."""
    done = _completed_ids(db, user.id)
    nxt = (
        db.query(Lesson)
        .filter(~Lesson.id.in_(done) if done else True)
        .order_by(Lesson.seq.asc())
        .first()
    )
    if nxt is None:
        # Either bank empty, or everything done -> serve the last lesson for review.
        nxt = db.query(Lesson).order_by(Lesson.seq.desc()).first()
    if nxt is None:
        raise HTTPException(
            503,
            "No lessons yet. Run `python generate_lessons.py <count>` to build the "
            "shared lesson bank.",
        )
    return _serialize_lesson(nxt, completed=nxt.id in done)


@app.get("/lesson/{lesson_id}")
def get_lesson(
    lesson_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "lesson not found")
    return _serialize_lesson(lesson, completed=lesson_id in _completed_ids(db, user.id))


@app.post("/lesson/{lesson_id}/complete")
def complete_lesson(
    lesson_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    """Mark a shared lesson complete for this user: promote its words to 'known'
    (+ SRS), record its grammar point, and log progress/streak."""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "lesson not found")

    # Words -> known + SRS, capturing meaning for flashcards.
    target_list = json.loads(lesson.targets_json or "[]")
    meanings = {
        (t.get("word") or "").lower(): t for t in target_list if t.get("word")
    }
    if meanings:
        for w in db.query(Word).filter(Word.headword.in_(list(meanings))).all():
            uw = (
                db.query(UserWord)
                .filter(UserWord.user_id == user.id, UserWord.word_id == w.id)
                .first()
            )
            if uw is None:
                uw = UserWord(user_id=user.id, word_id=w.id)
                db.add(uw)
            uw.status = "known"
            # Store the meaning on the shared catalog (once) — no per-user copies.
            m = meanings.get(w.headword, {})
            w.en_def = w.en_def or m.get("en_def", "")
            w.vi = w.vi or m.get("vi", "")
            w.example = w.example or m.get("example", "")
            srs.enroll(db, user.id, w)

    # Grammar point learned
    if lesson.grammar_id:
        exists = (
            db.query(UserGrammar)
            .filter(
                UserGrammar.user_id == user.id,
                UserGrammar.grammar_id == lesson.grammar_id,
            )
            .first()
        )
        if not exists:
            db.add(UserGrammar(user_id=user.id, grammar_id=lesson.grammar_id))

    # Lesson progress (idempotent)
    if not (
        db.query(LessonProgress)
        .filter(
            LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson_id
        )
        .first()
    ):
        db.add(LessonProgress(user_id=user.id, lesson_id=lesson_id))

    db.commit()
    _record_progress(db, user)
    return {"ok": True, "lesson_id": lesson_id}


# --------------------------------------------------------------------------- #
# Vocab / SRS
# --------------------------------------------------------------------------- #
@app.get("/vocab/review")
def vocab_review(user: User = Depends(current_user), db: Session = Depends(get_session)):
    rows = srs.due_words(db, user.id, limit=20)
    return [
        {
            "word_id": w.id,
            "headword": w.headword,
            "rank": w.rank,
            "due_date": s.due_date.isoformat() if s.due_date else None,
            "en_def": w.en_def or "",
            "vi": w.vi or "",
            "example": w.example or "",
        }
        for (w, s) in rows
    ]


class ReviewResult(BaseModel):
    word_id: int
    quality: int


@app.post("/vocab/review")
def vocab_review_submit(
    result: ReviewResult,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    word = db.get(Word, result.word_id)
    if word is None:
        raise HTTPException(404, "word not found")
    state = srs.update(db, user.id, word, result.quality)
    db.commit()
    return {
        "word_id": word.id,
        "headword": word.headword,
        "ease": round(state.ease, 2),
        "interval_days": state.interval_days,
        "repetitions": state.repetitions,
        "due_date": state.due_date.isoformat(),
    }


class PromoteRequest(BaseModel):
    word_ids: list[int] | None = None
    headwords: list[str] | None = None


@app.post("/vocab/promote")
def vocab_promote(
    req: PromoteRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    q = db.query(Word)
    if req.word_ids:
        words = q.filter(Word.id.in_(req.word_ids)).all()
    elif req.headwords:
        words = q.filter(Word.headword.in_([h.lower() for h in req.headwords])).all()
    else:
        raise HTTPException(400, "provide word_ids or headwords")

    promoted = []
    for w in words:
        uw = (
            db.query(UserWord)
            .filter(UserWord.user_id == user.id, UserWord.word_id == w.id)
            .first()
        )
        if uw is None:
            uw = UserWord(user_id=user.id, word_id=w.id)
            db.add(uw)
        uw.status = "known"
        srs.enroll(db, user.id, w)
        promoted.append(w.headword)
    db.commit()
    _record_progress(db, user)
    return {"promoted": promoted, "count": len(promoted)}


# --------------------------------------------------------------------------- #
# Profiler
# --------------------------------------------------------------------------- #
class ProfileRequest(BaseModel):
    text: str


@app.post("/profiler/score")
def profiler_score(
    req: ProfileRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    result = score(req.text, known_set(db, user.id))
    result["in_range"] = result["coverage_pct"] >= COVERAGE_THRESHOLD
    result["threshold"] = COVERAGE_THRESHOLD
    return result


# --------------------------------------------------------------------------- #
# Account / settings
# --------------------------------------------------------------------------- #
class AccountRequest(BaseModel):
    name: str


@app.get("/account")
def get_account(user: User = Depends(current_user)):
    return {"name": user.name or "", "username": user.username}


@app.post("/account")
def set_account(
    req: AccountRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    user.name = req.name.strip()
    db.commit()
    return {"name": user.name}


@app.get("/settings")
def get_settings(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return {
        "active_theme": _get_setting(db, user.id, "active_theme", "") or "",
        "themes": INTERESTS,
    }


class SettingsRequest(BaseModel):
    active_theme: str = ""


@app.post("/settings")
def update_settings(
    req: SettingsRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    _set_setting(db, user.id, "active_theme", req.active_theme.strip())
    return {"active_theme": req.active_theme.strip()}


# --------------------------------------------------------------------------- #
# Produce
# --------------------------------------------------------------------------- #
class ProduceRequest(BaseModel):
    lesson_id: int | None = None
    text: str


@app.post("/produce")
def save_production(
    req: ProduceRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    result = score(req.text, known_set(db, user.id))
    prod = Production(
        user_id=user.id,
        lesson_id=req.lesson_id,
        text=req.text.strip(),
        coverage_pct=result["coverage_pct"],
    )
    db.add(prod)
    db.commit()
    return {"id": prod.id, **result}


# --------------------------------------------------------------------------- #
# Realtime voice
# --------------------------------------------------------------------------- #
class RealtimeRequest(BaseModel):
    target_words: list[str] = []
    mode: str = "echo"
    script: list[dict] = []
    student_name: str = ""
    target_info: list[dict] = []  # [{word, vi, example}] for the teacher
    grammar: dict = {}  # today's grammar point


@app.post("/session/instructions")
def session_instructions(req: RealtimeRequest, user: User = Depends(current_user)):
    from realtime import build_instructions

    name = req.student_name or user.name
    return {
        "instructions": build_instructions(
            req.target_words, req.mode, req.script, name, req.target_info, req.grammar
        )
    }


@app.post("/session/realtime-token")
def realtime_token(req: RealtimeRequest, user: User = Depends(current_user)):
    if not HAS_OPENAI:
        raise HTTPException(
            503,
            "OPENAI_API_KEY not configured. Set it in backend/.env to enable "
            "the speaking module.",
        )
    try:
        name = req.student_name or user.name
        return mint_token(
            req.target_words, req.mode, req.script, name, req.target_info, req.grammar
        )
    except Exception as exc:
        raise HTTPException(502, f"failed to mint realtime token: {exc}")


# --------------------------------------------------------------------------- #
# Progress
# --------------------------------------------------------------------------- #
def _coverage_estimate(known_count: int) -> float:
    if known_count <= 0:
        return 0.0
    return round(min(92.0, 92.0 * (known_count / 2809.0) ** 0.5), 1)


def _known_count(db: Session, user_id: int) -> int:
    return (
        db.query(UserWord)
        .filter(UserWord.user_id == user_id, UserWord.status == "known")
        .count()
    )


def _record_progress(db: Session, user: User) -> Progress:
    today = date.today()
    known_count = _known_count(db, user.id)
    coverage = _coverage_estimate(known_count)

    row = (
        db.query(Progress)
        .filter(Progress.user_id == user.id, Progress.date == today)
        .first()
    )
    yesterday = (
        db.query(Progress)
        .filter(Progress.user_id == user.id, Progress.date == today - timedelta(days=1))
        .first()
    )
    streak = (yesterday.streak + 1) if yesterday else 1

    if row is None:
        row = Progress(
            user_id=user.id,
            date=today,
            known_count=known_count,
            coverage_pct=coverage,
            streak=streak,
        )
        db.add(row)
    else:
        row.known_count = known_count
        row.coverage_pct = coverage
    db.commit()
    db.refresh(row)
    return row


@app.get("/progress")
def progress(user: User = Depends(current_user), db: Session = Depends(get_session)):
    history = (
        db.query(Progress)
        .filter(Progress.user_id == user.id)
        .order_by(Progress.date.asc())
        .all()
    )
    known_count = _known_count(db, user.id)
    latest = history[-1] if history else None
    return {
        "streak": latest.streak if latest else 0,
        "known_count": known_count,
        "coverage_pct": _coverage_estimate(known_count),
        "history": [
            {
                "date": p.date.isoformat(),
                "known_count": p.known_count,
                "coverage_pct": p.coverage_pct,
                "streak": p.streak,
            }
            for p in history
        ],
    }


@app.get("/profile")
def profile(user: User = Depends(current_user), db: Session = Depends(get_session)):
    known_count = _known_count(db, user.id)
    lessons_completed = (
        db.query(LessonProgress).filter(LessonProgress.user_id == user.id).count()
    )
    lessons_total = db.query(Lesson).count()
    grammar_learned = (
        db.query(UserGrammar).filter(UserGrammar.user_id == user.id).count()
    )
    conversations = (
        db.query(Conversation).filter(Conversation.user_id == user.id).count()
    )
    repractice = len(srs.due_words(db, user.id, limit=1000))
    history = (
        db.query(Progress)
        .filter(Progress.user_id == user.id)
        .order_by(Progress.date.asc())
        .all()
    )
    latest = history[-1] if history else None
    return {
        "name": user.name,
        "username": user.username,
        "streak": latest.streak if latest else 0,
        "known_count": known_count,
        "lessons_completed": lessons_completed,
        "lessons_total": lessons_total,
        "grammar_learned": grammar_learned,
        "conversations": conversations,
        "repractice": repractice,
        "coverage_pct": _coverage_estimate(known_count),
    }


class ExplainRequest(BaseModel):
    headword: str


@app.post("/word/explain")
def explain_word(
    req: ExplainRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    """Return {en_def, vi, example} for a word, generating + saving any that are
    missing so every word ends up with an example."""
    hw = (req.headword or "").strip().lower()
    if not hw:
        raise HTTPException(400, "headword required")
    word = db.query(Word).filter(Word.headword == hw).first()
    en_def = (word.en_def if word else "") or ""
    vi = (word.vi if word else "") or ""
    example = (word.example if word else "") or ""

    if not (en_def and vi and example) and HAS_OPENAI:
        from config import OPENAI_API_KEY, OPENAI_TRANSLATE_MODEL
        from openai import OpenAI

        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=OPENAI_TRANSLATE_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You explain English words for a Vietnamese "
                        "beginner. Keep it very simple. Output strict JSON.",
                    },
                    {
                        "role": "user",
                        "content": f'Word: "{hw}". Return JSON '
                        '{"en_def":"a very simple English definition",'
                        '"vi":"the Vietnamese meaning",'
                        '"example":"one short, simple example sentence using the word"}.',
                    },
                ],
                response_format={"type": "json_object"},
            )
            d = json.loads(resp.choices[0].message.content)
            en_def = en_def or d.get("en_def", "")
            vi = vi or d.get("vi", "")
            example = example or d.get("example", "")
            if word:  # persist on the shared catalog -> generate once, ever
                word.en_def, word.vi, word.example = en_def, vi, example
                db.commit()
        except Exception:
            pass

    return {"headword": hw, "en_def": en_def, "vi": vi, "example": example}


# --------------------------------------------------------------------------- #
# Speaking conversations (saved transcripts for review)
# --------------------------------------------------------------------------- #
class ConversationRequest(BaseModel):
    lesson_id: int | None = None
    theme: str = ""
    turns: list[dict] = []  # [{role, en, vi}]


@app.post("/conversation")
def save_conversation(
    req: ConversationRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    turns = [t for t in req.turns if (t.get("en") or "").strip()]
    if not turns:
        return {"ok": False, "saved": 0}
    conv = Conversation(
        user_id=user.id,
        lesson_id=req.lesson_id,
        theme=req.theme or "",
        turns_json=json.dumps(turns),
    )
    db.add(conv)
    db.commit()
    return {"ok": True, "id": conv.id}


@app.get("/conversations")
def list_conversations(
    user: User = Depends(current_user), db: Session = Depends(get_session)
):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "theme": c.theme,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "turn_count": len(json.loads(c.turns_json or "[]")),
        }
        for c in rows
    ]


@app.get("/conversation/{conv_id}")
def get_conversation(
    conv_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    c = db.get(Conversation, conv_id)
    if c is None or c.user_id != user.id:
        raise HTTPException(404, "not found")
    return {
        "id": c.id,
        "theme": c.theme,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "turns": json.loads(c.turns_json or "[]"),
    }


@app.get("/grammar")
def grammar_review(user: User = Depends(current_user), db: Session = Depends(get_session)):
    """All grammar points with this user's learned status — for revisiting."""
    learned = {
        g.grammar_id
        for g in db.query(UserGrammar.grammar_id)
        .filter(UserGrammar.user_id == user.id)
        .all()
    }
    return [
        {**grammar_kb.public(p), "learned": p["id"] in learned}
        for p in grammar_kb.GRAMMAR_POINTS
    ]


@app.get("/words")
def words_review(user: User = Depends(current_user), db: Session = Depends(get_session)):
    """The user's known words with meanings (from the shared catalog)."""
    rows = (
        db.query(Word)
        .join(UserWord, UserWord.word_id == Word.id)
        .filter(UserWord.user_id == user.id, UserWord.status == "known")
        .order_by(Word.rank.asc())
        .all()
    )
    return [
        {
            "headword": w.headword,
            "rank": w.rank,
            "en_def": w.en_def or "",
            "vi": w.vi or "",
            "example": w.example or "",
        }
        for w in rows
    ]


# --------------------------------------------------------------------------- #
# Session log
# --------------------------------------------------------------------------- #
class SessionLogRequest(BaseModel):
    lesson_id: int
    completed_steps: list[int] = []
    errors: list[str] = []


@app.post("/session/log")
def session_log(
    req: SessionLogRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    log = SessionLog(
        user_id=user.id,
        lesson_id=req.lesson_id,
        completed_steps=",".join(str(s) for s in req.completed_steps),
        errors_json=json.dumps(req.errors),
    )
    db.add(log)
    db.commit()
    _record_progress(db, user)
    return {"ok": True, "session_id": log.id}


# --------------------------------------------------------------------------- #
# Text-to-speech (public — no learner data involved)
# --------------------------------------------------------------------------- #
class TTSRequest(BaseModel):
    text: str
    speed: float = 0.95
    voice: str | None = None


@app.post("/tts")
def tts(req: TTSRequest):
    if not HAS_OPENAI:
        raise HTTPException(503, "TTS requires OPENAI_API_KEY")
    from tts import synthesize

    try:
        audio = synthesize(req.text, speed=req.speed, voice=req.voice)
    except Exception as exc:
        raise HTTPException(502, f"tts failed: {exc}")
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --------------------------------------------------------------------------- #
# Translate (live bilingual subtitles for the speaking stage)
# --------------------------------------------------------------------------- #
class TranslateRequest(BaseModel):
    text: str


@app.post("/translate")
def translate(req: TranslateRequest, user: User = Depends(current_user)):
    if not HAS_OPENAI:
        raise HTTPException(503, "Translation requires OPENAI_API_KEY")
    text = (req.text or "").strip()
    if not text:
        return {"en": "", "vi": ""}

    from config import OPENAI_API_KEY, OPENAI_TRANSLATE_MODEL
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        resp = client.chat.completions.create(
            model=OPENAI_TRANSLATE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You produce bilingual subtitles for a beginner "
                    "English lesson. The input line may mix English and Vietnamese.",
                },
                {
                    "role": "user",
                    "content": 'Return ONLY JSON {"en":"...","vi":"..."} where en is '
                    "this line in natural, simple English and vi is the same line in "
                    f"natural Vietnamese.\nLINE: {text}",
                },
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return {"en": data.get("en", text), "vi": data.get("vi", "")}
    except Exception as exc:
        raise HTTPException(502, f"translate failed: {exc}")


@app.get("/health")
def health():
    return {"status": "ok", "openai": HAS_OPENAI}
