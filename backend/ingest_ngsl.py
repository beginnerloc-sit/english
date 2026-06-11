"""Ingest NGSL / NGSL-Spoken CSVs into the `words` table.

CSV format (one row per lemma, no header):
    headword,inflected_form,inflected_form,...
e.g.  go,goes,went,going,gone

FREQUENCY RANK: the NGSL-Spoken "lemmatized for teaching" CSV ships in
ALPHABETICAL order with no frequency column, but the README's sequencing and
difficulty ruler need frequency order. So rank is assigned from
data/freq_core.txt (a curated frequency-ordered core); any CSV word not in that
list is ranked afterwards in CSV order. If a full NGSL file with its own rank
column is added later, that genuine ranking can replace this.

NGSL-Spoken is loaded first (the conversational starting subset, README section
6); the full NGSL is appended if present without duplicating headwords. The
most-frequent BOOTSTRAP_KNOWN_COUNT words are seeded as `known` so the very
first lessons have enough vocabulary to be generated.
"""
from __future__ import annotations

import csv
from pathlib import Path

from config import BASE_DIR, BOOTSTRAP_KNOWN_COUNT, DATA_DIR
from db import SessionLocal, Word, init_db

# Candidate filenames -> source tag. Searched in DATA_DIR and the project root.
CSV_SOURCES = [
    ("NGSL-Spoken_1.2_lemmatized_for_teaching.csv", "ngsl_spoken"),
    ("NGSL-Spoken.csv", "ngsl_spoken"),
    ("NGSL_1.2_lemmatized_for_teaching.csv", "ngsl"),
    ("NGSL.csv", "ngsl"),
]

SEARCH_DIRS = [DATA_DIR, BASE_DIR, BASE_DIR.parent]


def _find_csv(filename: str) -> Path | None:
    for d in SEARCH_DIRS:
        p = d / filename
        if p.exists():
            return p
    return None


def _load_freq_order() -> dict[str, int]:
    """headword -> frequency position (0-based) from data/freq_core.txt."""
    path = _find_csv("freq_core.txt") or (DATA_DIR / "freq_core.txt")
    order: dict[str, int] = {}
    if not path.exists():
        return order
    with path.open(encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w and not w.startswith("#") and w not in order:
                order[w] = len(order)
    return order


def _read_rows(path: Path) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for raw in csv.reader(f):
            cells = [c.strip().lower() for c in raw if c.strip()]
            if not cells:
                continue
            headword, forms = cells[0], cells
            # Skip an accidental header row like "headword,forms".
            if headword in {"headword", "word", "lemma"}:
                continue
            rows.append((headword, forms))
    return rows


def ingest() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(Word).count() > 0:
            print("words table already populated; clearing and re-ingesting.")
            db.query(Word).delete()
            db.commit()

        freq = _load_freq_order()
        collected: list[tuple[str, list[str], str, int]] = []  # head, forms, source, csv_pos
        seen: set[str] = set()
        csv_pos = 0
        for filename, source in CSV_SOURCES:
            path = _find_csv(filename)
            if not path:
                continue
            print(f"ingesting {path.name} ({source})")
            for headword, forms in _read_rows(path):
                if headword in seen:
                    continue
                seen.add(headword)
                collected.append((headword, forms, source, csv_pos))
                csv_pos += 1

        # Sort: freq-core words first (by freq position), then the rest in CSV
        # order. This is the learning sequence + difficulty ruler.
        big = len(freq)
        collected.sort(key=lambda r: (freq.get(r[0], big + r[3])))

        for rank, (headword, forms, source, _pos) in enumerate(collected, start=1):
            db.add(
                Word(
                    rank=rank,
                    headword=headword,
                    source=source,
                    forms="\n".join(dict.fromkeys(forms)),  # de-dupe, keep order
                )
            )
        db.commit()

        total = db.query(Word).count()
        if total == 0:
            print(
                "No NGSL CSV files found. Place them in backend/data/ "
                "(download from newgeneralservicelist.org)."
            )
        else:
            print(
                f"ingested {total} words into the catalog. Each new account is "
                f"seeded with the top {BOOTSTRAP_KNOWN_COUNT} as 'known' at registration."
            )
    finally:
        db.close()


if __name__ == "__main__":
    ingest()
