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
- Speak MAINLY in VIETNAMESE. Vietnamese is your main language of communication:
  your greetings, instructions, questions, explanations, encouragement, jokes and
  reactions are ALL in Vietnamese, so the beginner always understands and feels at ease.
- Use ENGLISH only for the actual things the student is learning to say — today's
  words and short practice phrases/sentences. Introduce each English word or phrase,
  give its Vietnamese meaning, then ask the student (in Vietnamese) to try saying it
  in English. Example:
  "Hôm nay mình học từ 'team' — nghĩa là 'đội'. Bạn thử nói 'I like my team' nhé?"
- Always give the Vietnamese meaning of any English word you use.
- Check understanding in Vietnamese ("Bạn hiểu không?") and praise warmly in Vietnamese.
- The GOAL: explain and guide EVERYTHING in Vietnamese, but get the STUDENT to
  produce the English words and short sentences.

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
- Mostly ASK the student questions and get them to say their OWN answers in their own
  words. Have a real back-and-forth. Do NOT just make them repeat after you.
- HELP ALWAYS COMES FIRST: if the student asks for help, says they don't understand,
  asks what something means, or sounds confused or lost AT ANY MOMENT (in English OR
  Vietnamese), STOP and help them right away IN VIETNAMESE — explain simply, give an
  example, reassure them — and only continue once they are ready. NEVER ignore a
  request for help, even if it means staying on one point longer.
- Recast, don't correct. Gently say a mistake back the right way, then continue.
  NEVER tell the student they are wrong.
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

TODAY'S WORDS — THE MAIN GOAL OF THIS LESSON:
{wl}
Your job is to make the student HEAR and SAY each of these words in a real
sentence during your chat. If the student does not know a word, gently teach it
with its Vietnamese meaning and an example, then get them to use it themselves.
This lesson is about USING these words in a real conversation — it is NEVER about
repeating a single word over and over. Cover every word above before you finish."""

    if grammar and grammar.get("title"):
        base += f"""

TODAY'S GRAMMAR PATTERN — YOU MUST TEACH THIS: {grammar['title']} — {grammar.get('structure_hint', '')}
Early in the lesson, TEACH this pattern: explain it simply IN VIETNAMESE, give one
clear English example with its Vietnamese meaning, then get the student to make one
short English sentence using the pattern (help them if needed). Keep using the
pattern naturally through the rest of the chat. Examples: {grammar.get('examples', [])}."""
    if script:
        lines = "\n".join(
            f"{i + 1}. ({c.get('id')}) {c.get('goal')} — {c.get('say', '')}"
            for i, c in enumerate(script)
        )
        base += f"""

LESSON PLAN (your backbone — CONVERSATION points to cover, IN ORDER; a guide for you,
NOT a script to read aloud, and NOT things to make the student repeat):
{lines}

Work through these points STRICTLY IN ORDER, ONE at a time. Stay on the current point
until the student has genuinely DONE it (answered the question / used the target word /
tried the pattern). Judge each turn:
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
) -> dict:
    """Create an ephemeral Realtime session. Raises RuntimeError if no API key."""
    if not HAS_OPENAI:
        raise RuntimeError("OPENAI_API_KEY not configured; realtime voice unavailable.")

    import httpx  # bundled with the openai client's deps

    instructions = build_instructions(
        target_words, mode, script, student_name, word_glosses, grammar
    )
    payload = {
        "session": {
            "type": "realtime",
            "model": OPENAI_REALTIME_MODEL,
            "instructions": instructions,
            # The model decides when a checkpoint is complete and calls this.
            "tools": [CHECKPOINT_TOOL],
            "tool_choice": "auto",
            "audio": {
                "input": {
                    # Live transcription of the learner's speech — drives the
                    # subtitles and tells the client a turn finished.
                    "transcription": {"model": OPENAI_TRANSCRIBE_MODEL},
                    # Detect end-of-turn (beginners pause a lot, so be generous)
                    # and AUTO-reply once per turn, using the full session
                    # instructions (persona + lesson plan + tool). The client only
                    # triggers the opening greeting; everything else is automatic,
                    # so the teacher always responds and keeps full context.
                    "turn_detection": {
                        "type": "server_vad",
                        "silence_duration_ms": 1500,
                        "threshold": 0.5,
                        "create_response": True,
                        "interrupt_response": True,
                    },
                },
                "output": {"voice": OPENAI_REALTIME_VOICE},
            },
        }
    }
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
    resp.raise_for_status()
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
        "instructions": instructions,
    }
