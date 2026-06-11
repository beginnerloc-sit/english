"""Build (or extend) the SHARED lesson bank — the same lessons for every account.

Lessons are global and ordered (seq 1..N). Each lesson advances the grammar spine
(grammar point #seq) and the word frontier (the next high-frequency words), with the
running known-word set accumulated so later dialogues reuse earlier words. Every
account progresses through this same bank; per-user completion is tracked separately.

Run from YOUR terminal (venv active, OPENAI_API_KEY set):

    python generate_lessons.py [count]            # REBUILD: fresh bank of `count` (default 30)
    python generate_lessons.py --append [count]   # EXTEND: add `count` more (default 20)

REBUILD clears existing lessons AND everyone's lesson-completion progress (known
words / grammar already learned are kept). APPEND keeps everything and continues the
curriculum — it never repeats words already used by existing lessons.
"""
from __future__ import annotations

import json
import sys

from config import BOOTSTRAP_KNOWN_COUNT, INTERESTS, TARGETS_PER_LESSON
import grammar as grammar_kb
from db import Lesson, SessionLocal, Word, engine, init_db
from generation import LessonGenerationError, generate_lesson


def build(count: int, append: bool) -> None:
    if not append:
        # Fresh schema for the bank + progress.
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS lesson_progress")
            conn.exec_driver_sql("DROP TABLE IF EXISTS lessons")
    init_db()

    db = SessionLocal()
    try:
        all_words = db.query(Word).order_by(Word.rank.asc()).all()
        if not all_words:
            print("No words in catalog. Run `python ingest_ngsl.py` first.")
            sys.exit(1)
        word_by_head = {w.headword: w for w in all_words}

        # Start the known/used set from the bootstrap vocabulary.
        known = [w.headword for w in all_words[:BOOTSTRAP_KNOWN_COUNT]]
        used = set(known)
        start_seq = 1

        if append:
            existing = db.query(Lesson).order_by(Lesson.seq.asc()).all()
            for ls in existing:
                for t in json.loads(ls.targets_json or "[]"):
                    w = (t.get("word") or "").strip().lower()
                    if w and w not in used:
                        known.append(w)
                        used.add(w)
            start_seq = max([ls.seq or 0 for ls in existing], default=0) + 1
            print(
                f"Extending bank: {len(existing)} existing lessons, "
                f"{len(used)} words already used. Adding {count} more from seq {start_seq}…"
            )
        else:
            print(f"Building {count} shared lessons from scratch…")

        n_grammar = len(grammar_kb.GRAMMAR_POINTS)
        made = 0
        for i in range(start_seq, start_seq + count):
            grammar = grammar_kb.GRAMMAR_POINTS[i - 1] if i - 1 < n_grammar else None
            candidates = [w.headword for w in all_words if w.headword not in used][
                : max(40, TARGETS_PER_LESSON * 8)
            ]
            if not candidates:
                print("Ran out of new words; stopping.")
                break
            theme = INTERESTS[(i - 1) % len(INTERESTS)]
            try:
                data = generate_lesson(theme, sorted(known), candidates, grammar)
            except LessonGenerationError as exc:
                print(f"  [seq {i}] generation failed: {exc}")
                print("Stopping (check OPENAI_API_KEY / model id).")
                break

            targets = data.get("targets", [])
            db.add(
                Lesson(
                    seq=i,
                    theme=data.get("theme", theme),
                    dialogue_json=json.dumps(data.get("dialogue", [])),
                    targets_json=json.dumps(data.get("target_words", [])),
                    speaking_prompts_json=json.dumps(data.get("speaking_prompts", [])),
                    speaking_script_json=json.dumps(data.get("speaking_script", [])),
                    produce_prompt=data.get("produce_prompt", ""),
                    grammar_id=(grammar or {}).get("id"),
                    grammar_json=json.dumps(grammar_kb.public(grammar)),
                    coverage_pct=data.get("coverage_pct", 0.0),
                )
            )
            # Store each target word's meaning on the shared catalog (free here).
            for t in data.get("target_words", []):
                hw = (t.get("word") or "").strip().lower()
                wr = word_by_head.get(hw)
                if wr:
                    wr.en_def = wr.en_def or t.get("en_def", "")
                    wr.vi = wr.vi or t.get("vi", "")
                    wr.example = wr.example or t.get("example", "")
            db.commit()
            known += targets
            used |= set(targets)
            made += 1
            g = (grammar or {}).get("id", "—")
            print(
                f"  [seq {i}] {theme} | grammar: {g} | words: {targets} "
                f"| coverage: {data.get('coverage_pct', 0)}%"
            )

        total = db.query(Lesson).count()
        print(f"Done. Added {made}. Shared lesson bank now has {total} lessons.")
    finally:
        db.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    append = False
    if args and args[0] in ("--append", "-a"):
        append = True
        args = args[1:]
    count = int(args[0]) if args else (20 if append else 30)
    build(count, append)
