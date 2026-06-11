"""Lesson generation engine (README section 8).

A single server-side call produces the day's content as strict JSON:
    { theme, dialogue[], target_words[], speaking_prompts[], produce_prompt }

Content is ALWAYS produced by the OpenAI text model. There is no offline /
placeholder generator: if the LLM is unavailable or fails, generation raises
LessonGenerationError and the caller surfaces the failure. We never fabricate
lesson content.
"""
from __future__ import annotations

import json

from config import (
    COVERAGE_THRESHOLD,
    HAS_OPENAI,
    OPENAI_API_KEY,
    OPENAI_TEMPERATURE,
    OPENAI_TEXT_MODEL,
)
from profiler import score


class LessonGenerationError(RuntimeError):
    """Raised when a real lesson cannot be produced by the LLM."""


SCHEMA_HINT = {
    "theme": "string",
    "dialogue": [{"speaker": "A|B", "en": "string", "vi": "string"}],
    "target_words": [
        {"word": "string", "en_def": "string", "vi": "string", "example": "string"}
    ],
    "speaking_prompts": ["string"],
    "speaking_script": [
        {"id": "c1", "goal": "short checklist label", "say": "what the tutor does", "word": "target word or null"}
    ],
    "produce_prompt": "string",
}


def _grammar_block(grammar: dict | None) -> str:
    if not grammar:
        return ""
    examples = grammar.get("examples", [])
    return f"""

GRAMMAR FOCUS (build the dialogue so it naturally and repeatedly uses THIS pattern):
{grammar.get('title')}: {grammar.get('structure_hint')}
Pattern examples: {examples}
Several dialogue lines should clearly use this grammar pattern, kept simple and
beginner-friendly."""


def _build_prompt(
    theme: str, known: list[str], candidates: list[str], grammar: dict | None = None
) -> str:
    return f"""You are writing a short English lesson for a BEGINNER (CEFR A1) whose
first language is Vietnamese. Quality matters: the result must read like a REAL,
natural conversation, not a list of forced sentences.

THEME (the whole lesson must genuinely be about this): {theme}{_grammar_block(grammar)}

WORDS THE LEARNER ALREADY KNOWS (use these freely): {sorted(known)}

CANDIDATE NEW WORDS — choose EXACTLY 6 of these that best fit the theme and make
the conversation natural. Do not use new words outside this list:
{candidates}

Write ONE coherent conversation between two friends, A and B, about the theme:
- 6-8 short lines that FLOW logically — every line is a natural reply to the line
  before it. Do NOT jump between unrelated topics.
- It must be specifically and obviously about "{theme}", with concrete details,
  and sound like two real people talking.
- Simple grammar only (present/past simple, basic questions, short sentences).
- Use ONLY the known words above plus the 6 new words you chose. Common proper
  nouns / well-known names are allowed.
- Each chosen new word must appear at least once, used naturally (not shoehorned).
- Give a natural Vietnamese translation for every line.

Then provide, for each of the 6 new words you used: a simple English definition,
a Vietnamese gloss, and one example sentence. Also give 3 short speaking prompts
that practice these words (for a beginner), and one "produce" prompt asking the
learner to say 1-2 sentences about their OWN life on this theme.

Also produce a "speaking_script": an ORDERED list of 4-6 CONVERSATIONAL
checkpoints for a lively guided chat about the theme. Each checkpoint =
{{id: short id like "c1", goal: a very short checklist label (max 6 words),
say: ONE sentence telling the tutor what to DO at this step — ask the student a
question, get them to share their OWN answer, or react — word: the target word
practiced here or null}}.
This must be a real CONVERSATION, NOT repetition. Do NOT use "repeat after me" or
"say this phrase" steps. Instead the tutor asks questions and the student answers
in their own words. Progress from easy (a simple yes/no or this-or-that question)
to a short free exchange where the student talks about themselves.
IMPORTANT: spread today's NEW words across the checkpoints so that EVERY new word
gets used by the student at least once — set each checkpoint's "word" field to the
new word it practices. Each question should naturally pull the student to use that
word in their answer.

Return ONLY valid JSON in this schema: {json.dumps(SCHEMA_HINT)}.
target_words must list ONLY the 6 new words you actually used. No prose, no markdown."""


def _chosen_targets(lesson: dict) -> list[str]:
    return [
        (tw.get("word") or "").strip().lower()
        for tw in lesson.get("target_words", [])
        if (tw.get("word") or "").strip()
    ]


def _dialogue_coverage(lesson: dict, known: set[str]) -> float:
    text = " ".join(line.get("en", "") for line in lesson.get("dialogue", []))
    return score(text, known, set(_chosen_targets(lesson)))["coverage_pct"]


def _generate_openai(
    theme: str, known: list[str], candidates: list[str], grammar: dict | None = None
) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = _build_prompt(theme, known, candidates, grammar)
    kwargs = dict(
        model=OPENAI_TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are an expert beginner-ESL lesson writer. "
                "Output strictly valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    # Newer reasoning models (gpt-5.x) only accept the default temperature, so we
    # omit it unless OPENAI_TEMPERATURE is explicitly set.
    if OPENAI_TEMPERATURE is not None:
        kwargs["temperature"] = OPENAI_TEMPERATURE
    resp = client.chat.completions.create(**kwargs)
    return json.loads(resp.choices[0].message.content)


def _validate_shape(lesson: dict) -> None:
    """Reject malformed LLM output rather than serving a broken lesson."""
    if not isinstance(lesson.get("dialogue"), list) or not lesson["dialogue"]:
        raise LessonGenerationError("LLM returned no dialogue.")
    if not isinstance(lesson.get("target_words"), list) or not lesson["target_words"]:
        raise LessonGenerationError("LLM returned no target words.")
    for line in lesson["dialogue"]:
        if not isinstance(line, dict) or "en" not in line:
            raise LessonGenerationError("LLM dialogue line missing 'en'.")


def generate_lesson(
    theme: str, known: list[str], candidates: list[str], grammar: dict | None = None
) -> dict:
    """Generate, validate against the profiler, and return a lesson dict.

    The model chooses its 6 new words from `candidates` (the frequency frontier)
    so the content is both theme-relevant and roughly in learning sequence.

    Raises LessonGenerationError if no API key is configured or the LLM cannot
    produce a usable lesson. Adds `coverage_pct`, `targets` (the chosen new-word
    headwords), and `_source='openai'`.
    """
    if not HAS_OPENAI:
        raise LessonGenerationError(
            "OPENAI_API_KEY is not configured. Lesson content requires the "
            "OpenAI LLM; refusing to fabricate content."
        )

    known_set = set(known)
    best: dict | None = None
    best_cov = -1.0
    last_error: Exception | None = None

    for _ in range(3):  # initial + up to 2 retries (README section 8)
        try:
            lesson = _generate_openai(theme, known, candidates, grammar)
            _validate_shape(lesson)
        except Exception as exc:  # network / parse / shape failure
            last_error = exc
            continue
        cov = _dialogue_coverage(lesson, known_set)
        if cov > best_cov:
            best, best_cov = lesson, cov
        if cov >= COVERAGE_THRESHOLD:
            break

    if best is None:
        raise LessonGenerationError(
            f"LLM failed to produce a valid lesson: {last_error}"
        )

    best.setdefault("theme", theme)
    best.setdefault("speaking_prompts", [])
    best.setdefault("speaking_script", [])
    best.setdefault("produce_prompt", "")
    best["coverage_pct"] = best_cov
    best["targets"] = _chosen_targets(best)
    best["_source"] = "openai"
    return best
