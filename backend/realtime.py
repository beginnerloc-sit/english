"""Mint short-lived OpenAI Realtime tokens + build beginner-safe instructions.

Security rule (README section 4): the real API key never leaves the server. The
browser gets only an ephemeral client secret to open the WebRTC session.

Aligned with the current Realtime API (developers.openai.com voice-agents +
realtime guides, checked 2026-06):
  * token endpoint: POST /v1/realtime/client_secrets   (was /v1/realtime/sessions)
  * request body nests a `session` object; VAD + transcription live under
    session.audio.input; voice under session.audio.output
  * default model: gpt-realtime-2 (override via OPENAI_REALTIME_MODEL)
The docs also recommend the @openai/agents/realtime SDK for the browser; we keep
a thin REST/WebRTC path here so the client has no extra dependency.

NOTE: Realtime API model ids, endpoints, and the session schema change often
(README warns of this). Everything below is env/config-driven — verify field
names against the live docs at build time.
"""
from __future__ import annotations

from config import (
    HAS_OPENAI,
    OPENAI_API_KEY,
    OPENAI_REALTIME_MODEL,
    OPENAI_REALTIME_VOICE,
    OPENAI_TRANSCRIBE_MODEL,
)

INSTRUCTIONS_TEMPLATE = """You are a FUN, warm, super-encouraging ENGLISH TEACHER giving a lively one-to-one
speaking lesson to a TRUE BEGINNER student whose first language is Vietnamese and who
understands very little English yet. This is a happy, friendly CONVERSATION full of
energy and smiles — never a test, never a drill.

LANGUAGE — THIS IS THE MOST IMPORTANT RULE:
- Speak MAINLY in VIETNAMESE. Your greetings, questions, explanations, encouragement,
  jokes and reactions are ALL in Vietnamese, so the beginner always understands.
- Use ENGLISH only for today's words/phrases, and ALWAYS give the Vietnamese meaning.
  Example: "Bạn có hay tập thể dục không? Trong tiếng Anh, 'tập thể dục' là 'exercise'."
- Ask your questions in Vietnamese and let the student answer HOWEVER they can.
  After teaching an example sentence, gently INVITE them to try saying it ONCE
  ("Bạn thử nói câu này nhé: ..."). Accept whatever they say and move on — never
  force a perfect repeat or make them say it again and again.
- Check understanding in Vietnamese ("Bạn hiểu không?") and praise warmly.
- GOAL: keep a real, friendly conversation going — comprehension first, a little
  English production when it happens naturally.

YOUR PERSONALITY:
- Upbeat and cheerful. React with feeling to what the student says ("Oh nice!",
  "Wow, really?", "Haha, me too!"). Show you are genuinely interested in them.
- Tell small, gentle, kind jokes and keep the mood light and happy.
- Give specific, warm FEEDBACK and comments on their speaking — notice a good word,
  clear pronunciation, or a nice sentence ("Great job — your 'win' sounded perfect!",
  "I love that answer!"). Comment on what they tell you.
- Talk a little MORE than a textbook: add a short reaction, comment, or fun fact —
  but keep EVERY sentence simple and easy for a beginner.

HOW YOU SPEAK:
- Clear, not too fast. Short, simple sentences (2-3 of them per turn is fine).
- When you do use English (for the words/phrases being practiced), keep it simple
  and high-frequency. No idioms, no slang, no hard grammar.
- Speak mainly Vietnamese throughout (see the LANGUAGE rule above); English is only
  for what the student practices saying.
- Today's English words to practice: {TARGET_WORDS}. Weave them in naturally.

HOW YOU TEACH (this is a CONVERSATION, not repetition):
- ALWAYS reply to what the student JUST said — their most recent message only. If they
  ask a question (about English, the lesson, or what to do), ANSWER that question
  directly and simply in Vietnamese. Never ignore it to push your own plan.
- TEACH, don't quiz. You LEAD the lesson. For each new word or idea, actually TEACH it
  first: say the English word, give its VIETNAMESE meaning, use it in ONE simple example
  sentence, add a short friendly note — THEN gently invite the student to try saying the
  example once, and ask one real question about their own life. Deliver real content.
- ALWAYS give the VIETNAMESE meaning of an English word. NEVER define an English word
  with English (do NOT say 'run means to run'; say: "'run' nghĩa là 'chạy'").
- Don't keep checking in ("Bạn hiểu không?", "Bạn có muốn thử từ khác không?"). Just
  teach the next thing and keep the lesson moving naturally.
- Inviting the student to try the example ONCE is good ("Bạn thử nói ... nhé"). Accept
  their attempt warmly and move on. But do NOT drill — never make them repeat the same
  sentence again and again or until it sounds "perfect".
- TRUST what the student said (you receive an accurate transcript). If their answer
  fits the point — even loosely — ACCEPT it and move on. Do NOT ask them to say it
  again "to be sure". One attempt is enough.
- HELP ALWAYS COMES FIRST: if the student asks for help, says they don't understand,
  asks what something means, or sounds confused or lost AT ANY MOMENT (in English OR
  Vietnamese), STOP and help them right away IN VIETNAMESE — explain simply, give an
  example, reassure them — and only continue once they are ready. NEVER ignore a
  request for help, even if it means staying on one point longer.
- Recast, don't correct. Gently say a mistake back the right way, then continue.
  NEVER tell the student they are wrong.
- DO NOT be strict about pronunciation. These are beginners with an accent — if you
  can understand them AT ALL, accept it warmly and move on. NEVER make the student
  repeat a word or phrase just to pronounce it more perfectly. Meaning matters, not
  a perfect accent.
- KEEP MOVING (only when they are NOT asking for help): after one good-enough attempt,
  praise them, give a happy comment, and move on. Don't drill the same word again and
  again. If they roughly got it, that is success!
- If the student is silent, give an example or a short Vietnamese hint, then continue."""


def build_instructions(
    target_words: list[str],
    mode: str,
    script: list[dict] | None = None,
    student_name: str = "",
    word_glosses: list[dict] | None = None,
    grammar: dict | None = None,
) -> str:
    base = INSTRUCTIONS_TEMPLATE.format(
        TARGET_WORDS=", ".join(target_words) or "(none today)",
        MODE=mode,
    )

    glosses = [g for g in (word_glosses or []) if g.get("word")]
    if glosses:
        wl = "\n".join(
            f"- {g['word']}"
            + (f" — {g['vi']}" if g.get("vi") else "")
            + (f'  (e.g. "{g["example"]}")' if g.get("example") else "")
            for g in glosses
        )
        base += f"""

TODAY'S WORDS (try to bring these up during the chat):
{wl}
Weave these words into your questions naturally. If one comes up, gently teach its
Vietnamese meaning. You may invite the student to use a word, but if they don't,
that's fine — keep the conversation flowing. NEVER force them to repeat a word."""

    if grammar and grammar.get("title"):
        base += f"""

TODAY'S GRAMMAR (background — use it yourself, don't drill it):
{grammar['title']} — {grammar.get('structure_hint', '')}
Early on, briefly explain this pattern IN VIETNAMESE with one example. Then just use
the pattern yourself in the conversation. Do NOT make the student produce a specific
sentence with it. Examples: {grammar.get('examples', [])}."""
    if script:
        lines = "\n".join(
            f"{i + 1}. ({c.get('id')}) {c.get('goal')} — {c.get('say', '')}"
            for i, c in enumerate(script)
        )
        base += f"""

LESSON PLAN (loose chat topics to cover, IN ORDER — a guide for YOU, not a script,
and NOT sentences to make the student repeat):
{lines}

Treat each point as a topic to CHAT about, one at a time. A point is DONE as soon as
the student has responded to it in any way — they do NOT need to produce a specific
word or sentence, and pronunciation does not matter. Be generous: when in doubt, mark
it done and move on. Judge each turn:
- If the student has truly completed the current point, briefly praise them, then call
  the function `mark_checkpoint` with that point's id (e.g. "c1"), and move to the next
  point. Do NOT announce the function call.
- If they have NOT done it yet, went off-topic, or need help, STAY on the current point
  and guide them — do NOT call the function and do NOT skip ahead.
Only ever advance by calling mark_checkpoint. Do not jump points or rush. When every
point is marked done, cheerfully tell the student you can now just chat freely."""

    name = (student_name or "").strip()
    who = name or "the student"
    base += f"""

STARTING THE LESSON: You speak FIRST. As soon as the session begins, warmly greet
{who} by name in VIETNAMESE{" (their name is " + name + ")" if name else ""}, say a
friendly line or two in Vietnamese to put them at ease, then begin the first point.
Do NOT wait for the student to speak first."""
    return base


# Function the model calls to tick a checkpoint off the learner's checklist.
CHECKPOINT_TOOL = {
    "type": "function",
    "name": "mark_checkpoint",
    "description": "Mark a lesson-script checkpoint as completed once the learner "
    "has successfully done it.",
    "parameters": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "The checkpoint id, e.g. 'c1'."}
        },
        "required": ["id"],
    },
}


def mint_token(
    target_words: list[str],
    mode: str,
    script: list[dict] | None = None,
    student_name: str = "",
    word_glosses: list[dict] | None = None,
    grammar: dict | None = None,
    transcribe_only: bool = False,
) -> dict:
    """Create an ephemeral Realtime session. Raises RuntimeError if no API key.

    transcribe_only=True yields a SILENT session (no AI replies, no tools) used
    purely to transcribe the student's speech — for the read-aloud step, reusing
    the same proven WebRTC mic as the speaking lesson.
    """
    if not HAS_OPENAI:
        raise RuntimeError("OPENAI_API_KEY not configured; realtime voice unavailable.")

    import httpx  # bundled with the openai client's deps

    session = {
        "type": "realtime",
        "model": OPENAI_REALTIME_MODEL,
        "audio": {
            "input": {
                "transcription": {"model": OPENAI_TRANSCRIBE_MODEL, "language": "en"},
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": 1500,
                    "threshold": 0.5,
                    # No auto-reply when only transcribing.
                    "create_response": not transcribe_only,
                    "interrupt_response": True,
                },
            },
            "output": {"voice": OPENAI_REALTIME_VOICE},
        },
    }
    if transcribe_only:
        session["instructions"] = "Silently transcribe the user. Never speak or reply."
    else:
        session["instructions"] = build_instructions(
            target_words, mode, script, student_name, word_glosses, grammar
        )
        session["tools"] = [CHECKPOINT_TOOL]
        session["tool_choice"] = "auto"
    payload = {"session": session}
    resp = httpx.post(
        "https://api.openai.com/v1/realtime/client_secrets",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
            # Recommended by the docs for per-user tracking/safety.
            "OpenAI-Safety-Identifier": "lingualoop-learner",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 400:
        # Surface OpenAI's actual error so failures are debuggable.
        raise RuntimeError(f"OpenAI {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    # The client_secrets response returns the secret object directly
    # ({value, expires_at, session}); older shapes nested it under
    # `client_secret`. Handle both so a schema tweak doesn't break us.
    secret = (
        data.get("value")
        or (data.get("client_secret") or {}).get("value")
        or data.get("client_secret")
    )
    return {
        "client_secret": secret,
        "model": OPENAI_REALTIME_MODEL,
        "instructions": session.get("instructions", ""),
    }
