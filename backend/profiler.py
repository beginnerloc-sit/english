"""Text profiler: what % of a text falls inside the learner's known vocabulary.

Lemmatization strategy (README gotcha: the NGSL is lemmatized, so inflected
forms must be normalized before matching, or the level-check breaks):

1. The ingested CSV already lists every inflected form per lemma, so we build a
   FORM -> HEADWORD map. This alone resolves go/goes/went/going -> "go" for any
   word in the list, with no NLP dependency.
2. spaCy is used *if installed* to lemmatize tokens that aren't in the form map
   (e.g. words outside NGSL), improving the unknown-word accounting.
3. A tiny suffix-stripping fallback handles the no-spaCy case.

A token counts as "covered" when its lemma is in the supplied known/allowed set.
"""
from __future__ import annotations

import re
from functools import lru_cache

from db import SessionLocal, UserWord, Word

_WORD_RE = re.compile(r"[a-zA-Z']+")

# Lazily-loaded spaCy pipeline (None if unavailable).
_NLP = "unloaded"


def _nlp():
    global _NLP
    if _NLP == "unloaded":
        try:
            import spacy  # type: ignore

            _NLP = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        except Exception:
            _NLP = None
    return _NLP


@lru_cache(maxsize=1)
def _form_to_headword() -> dict[str, str]:
    """Map every inflected form (and headword) to its NGSL headword."""
    db = SessionLocal()
    try:
        mapping: dict[str, str] = {}
        for w in db.query(Word).all():
            forms = [w.headword] + (w.forms.split("\n") if w.forms else [])
            for f in forms:
                f = f.strip().lower()
                if f:
                    mapping.setdefault(f, w.headword)
        return mapping
    finally:
        db.close()


def reset_cache() -> None:
    """Call after re-ingesting so the form map is rebuilt."""
    _form_to_headword.cache_clear()


def _simple_lemma(token: str) -> str:
    """Cheap suffix stripper used only when spaCy is absent and the token is
    not in the NGSL form map."""
    for suf in ("ing", "ied", "ies", "ed", "es", "s"):
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            stem = token[: -len(suf)]
            if suf == "ied":
                stem += "y"
            return stem
    return token


def lemmatize(token: str, form_map: dict[str, str] | None = None) -> str:
    token = token.lower().strip("'")
    fm = form_map if form_map is not None else _form_to_headword()
    if token in fm:
        return fm[token]
    nlp = _nlp()
    if nlp is not None:
        doc = nlp(token)
        if doc and doc[0].lemma_:
            lem = doc[0].lemma_.lower()
            return fm.get(lem, lem)
    return _simple_lemma(token)


def tokenize(text: str) -> list[str]:
    return [t for t in (_WORD_RE.findall(text or "")) if any(c.isalpha() for c in t)]


def score(text: str, known: set[str], extra_allowed: set[str] | None = None) -> dict:
    """Return coverage stats for `text` against `known` (+ optional extra_allowed,
    e.g. today's target words).

    Returns {coverage_pct, total_words, known_words, unknown_words[]}.
    """
    allowed = set(known)
    if extra_allowed:
        allowed |= {a.lower() for a in extra_allowed}

    fm = _form_to_headword()
    tokens = tokenize(text)
    if not tokens:
        return {
            "coverage_pct": 100.0,
            "total_words": 0,
            "known_words": 0,
            "unknown_words": [],
        }

    unknown: list[str] = []
    covered = 0
    for tok in tokens:
        lemma = lemmatize(tok, fm)
        if lemma in allowed or tok.lower() in allowed:
            covered += 1
        else:
            unknown.append(tok.lower())

    return {
        "coverage_pct": round(100.0 * covered / len(tokens), 2),
        "total_words": len(tokens),
        "known_words": covered,
        "unknown_words": sorted(set(unknown)),
    }


def known_set(db, user_id: int) -> set[str]:
    """All headwords this user has marked 'known'."""
    rows = (
        db.query(Word.headword)
        .join(UserWord, UserWord.word_id == Word.id)
        .filter(UserWord.user_id == user_id, UserWord.status == "known")
        .all()
    )
    return {r[0] for r in rows}
