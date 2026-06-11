"""One-time: fill en_def / vi / example for catalog words that lack them.

Meanings are stored ONCE on the shared `words` catalog, so the app never needs a
runtime LLM call for vocabulary. Lesson words are filled automatically when the
bank is built; this covers the rest (e.g. the bootstrap words). Batches many words
per request to keep it cheap.

Run from YOUR terminal (venv active, OPENAI_API_KEY set):
    python enrich_vocab.py            # fill words missing meaning (all known-ish)
    python enrich_vocab.py 300        # only the top 300 by frequency
"""
from __future__ import annotations

import json
import sys

from config import HAS_OPENAI, OPENAI_API_KEY, OPENAI_TRANSLATE_MODEL
from db import SessionLocal, Word, init_db

BATCH = 25


def enrich(limit: int | None) -> None:
    if not HAS_OPENAI:
        print("OPENAI_API_KEY not set; cannot enrich.")
        sys.exit(1)
    from openai import OpenAI

    init_db()
    db = SessionLocal()
    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        q = db.query(Word).order_by(Word.rank.asc())
        if limit:
            q = q.limit(limit)
        todo = [w for w in q.all() if not (w.en_def and w.vi and w.example)]
        print(f"{len(todo)} words need meanings. Filling in batches of {BATCH}…")

        done = 0
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            heads = [w.headword for w in batch]
            try:
                resp = client.chat.completions.create(
                    model=OPENAI_TRANSLATE_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You explain English words for a Vietnamese "
                            "beginner. Keep each very simple. Output strict JSON.",
                        },
                        {
                            "role": "user",
                            "content": "For each word, give a simple English "
                            "definition, the Vietnamese meaning, and one short simple "
                            'example sentence. Return JSON: {"items":[{"word":"..",'
                            '"en_def":"..","vi":"..","example":".."}]}.\n'
                            f"Words: {heads}",
                        },
                    ],
                    response_format={"type": "json_object"},
                )
                items = json.loads(resp.choices[0].message.content).get("items", [])
                by_head = {(it.get("word") or "").strip().lower(): it for it in items}
                for w in batch:
                    it = by_head.get(w.headword)
                    if it:
                        w.en_def = w.en_def or it.get("en_def", "")
                        w.vi = w.vi or it.get("vi", "")
                        w.example = w.example or it.get("example", "")
                        done += 1
                db.commit()
                print(f"  …{min(i + BATCH, len(todo))}/{len(todo)}")
            except Exception as exc:
                print(f"  batch failed ({exc}); continuing.")

        print(f"Done. Filled {done} words.")
    finally:
        db.close()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    enrich(limit)
