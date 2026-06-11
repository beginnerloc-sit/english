# LinguaLoop — Personal English Learning Web App

A single-user English learning web app for a **beginner building toward IELTS**, designed around **15 minutes a day**. It combines comprehensible-input lessons, spaced-repetition vocabulary, and AI speaking practice via real-time voice. Vietnamese (L1) support is used as a fading scaffold.

This is a **personal tool**, not a commercial product: no auth, no multi-user, no licensing constraints on content. Optimize for learning effectiveness and simplicity, not scale.

---

## 1. Goals & Constraints

- **One learner, one device profile.** No login/accounts. Single SQLite DB.
- **15-minute daily session** with a fixed structure and fresh content each day.
- **Beginner-first.** The learner starts near A0/A1 and climbs toward B1, where real IELTS prep begins. Do **not** add IELTS exam-strategy features at this stage; the app builds the foundation IELTS later depends on.
- **Personalized content.** Lessons are generated about the learner's actual interests (football / Premier League, gym & fitness, esports, tech gadgets, fashion). Personally compelling input is the #1 motivation lever.
- **Habit-safe.** The goal is never to skip a day. Make sessions easy to start (low activation energy) and satisfying to finish (visible progress, streak).

---

## 2. Core Learning-Design Principles (read before building)

These principles drive the requirements below. Don't "simplify" them away.

1. **Fixed structure, fresh content.** The session skeleton is identical every day so it becomes automatic (no decision fatigue). Only the theme and content change daily.
2. **Comprehensible input (i+1).** Learners acquire language by understanding content slightly above their level. All generated text must be locked to *known words + a few new target words* (see NGSL system below).
3. **Spaced repetition.** Vocabulary retention depends on reviewing words at increasing intervals. An SM-2-style scheduler drives which words resurface.
4. **Retrieval over recognition.** Make the learner *produce* (recall, say, complete) rather than passively re-read.
5. **Gradual release of support (speaking).** Never drop a beginner into open conversation. Move up a scaffold ladder (Section 7).
6. **Recast, don't correct.** When the learner makes an error in speech, the AI models the correct form naturally ("Oh, you *went* yesterday? Nice—where?"), never "that's wrong." Explicit feedback only in the end-of-session summary.
7. **Protect the affective filter.** No buzzers, no scores shown mid-activity. Anxiety is the main beginner blocker.

---

## 3. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite |
| Backend | FastAPI (Python) |
| Speaking | OpenAI Realtime Voice API (WebRTC) |
| Lesson generation | OpenAI text model (server-side) |
| Lemmatization / profiler | spaCy (`en_core_web_sm`) |
| Storage | SQLite (via SQLAlchemy) |
| Audio (optional authentic listening) | VOA Learning English (public domain), Tatoeba EN–VI pairs |

> **Model IDs and exact Realtime API params change frequently. Verify current model names, endpoints, and session parameters against the official OpenAI docs at build time rather than hardcoding from memory.**

---

## 4. Architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  React + Vite (browser)     │        │  FastAPI (server)            │
│                             │        │                              │
│  - Daily session UI (6 steps)│ HTTP  │  - /lesson/today  (generate) │
│  - Vocab review cards        │◄──────►│  - /vocab/review  (SRS)      │
│  - Audio playback            │        │  - /session/realtime-token   │
│  - Realtime voice (WebRTC) ──┼────────┼─► mints ephemeral token      │
│  - Progress dashboard        │        │  - /progress                 │
└─────────────────────────────┘        │  - profiler + generation     │
            │                          │  - SQLite                    │
            │  WebRTC (audio)          └──────────────────────────────┘
            ▼
   OpenAI Realtime API
```

**Security rule:** the real OpenAI API key lives **only** on the FastAPI server. The browser connects to the Realtime API using a short-lived **ephemeral token** minted by the backend. Never ship the API key to the frontend.

---

## 5. The Daily 15-Minute Loop

The session is six steps. Build them in order; each maps to a principle above.

| # | Step | ~Time | What happens |
|---|------|-------|--------------|
| 1 | **Review** | 2 min | SRS surfaces "due" words from prior days. Active recall (show prompt, learner recalls meaning/says it). Starts with a familiar win. |
| 2 | **Input** | 3 min | A short (4–8 line) generated dialogue on today's theme, with audio + text and toggleable Vietnamese translation. Introduces the 6–8 new target words *in context*. |
| 3 | **Notice** | 3 min | Pull today's target words out of the dialogue. See them, hear them, match meaning. Recognition-level. |
| 4 | **Speak** | 4 min | Real-time voice practice using today's words via the scaffold ladder (Section 7). Biggest block. |
| 5 | **Produce** | 2 min | Learner makes 1–2 of their *own* sentences using today's words, about their own life. Spoken or typed. |
| 6 | **Reward** | 1 min | Show words mastered today, update streak, one gentle recast of an error noticed in step 4/5. Plant tomorrow's hook. |

The loop is **Review → Input → Notice → Speak → Produce → Reward**. A complete acquisition cycle every day.

---

## 6. NGSL Vocabulary System (the backbone)

The **New General Service List (NGSL)** is a frequency-ranked list of ~2,809 lemmas covering ~92% of general English. The ranking is used two ways: as a **learning sequence** and as a **difficulty ruler**.

Download CSV from `newgeneralservicelist.org`. Also use **NGSL-Spoken** (~721 high-frequency spoken words) as the *starting* subset, since the learner wants to converse.

**Vocab table** — each word has a status: `locked` → `learning` → `known`, plus SM-2 fields (interval, ease factor, due date, repetitions).

**Three jobs:**

1. **Sequencing.** New words are introduced strictly in frequency order (next `locked` words become today's targets). Highest-frequency first = fastest coverage gain.
2. **Generation gate.** When generating a lesson, the LLM may use **only `known` words + today's target words**. This is how content stays comprehensible.
3. **Profiler (level checker).** Given any text, compute the % of its words that fall in the learner's `known` set. If <95% known → too hard. Used to (a) validate generated dialogues (regenerate if they drift above level) and (b) filter external content (e.g. only show VOA articles that profile in-range).

**⚠ Implementation gotcha — lemmatization.** The NGSL is lemmatized ("go" = go/goes/went/going). The profiler must lemmatize *both* the NGSL and any input text (use spaCy) before matching, or inflected forms won't match and the level-check breaks.

**Progress meter.** Because each word has a coverage contribution, surface a motivating number: "You know the top N words → you understand ~X% of everyday English."

---

## 7. Speaking Module — Scaffold Ladder & Realtime Voice

### Scaffold ladder
Most of a speaking block sits on the learner's current rung, with short stretches into the next:

1. **Echo** — AI says a short phrase; learner repeats. (Pronunciation + confidence, zero production pressure.)
2. **Choose the answer** — AI asks, offers 2–3 spoken options; learner picks one and says it.
3. **Fill the frame** — AI gives a frame ("I like ___"); learner completes it.
4. **Guided exchange** — AI asks predictable questions in a known scenario; hint button available.
5. **Bounded role-play** — free speech inside a familiar, limited-vocabulary scenario.
6. **Open conversation** — only unlocks around B1.

Track the learner's current rung; advance gradually based on success.

### Realtime voice session config
When opening a Realtime session, send an instructions block that enforces beginner-safe behavior. Use this as the system instructions (tune wording to current API schema):

```
You are a patient English speaking partner for a BEGINNER whose first language is Vietnamese.
RULES:
- Speak slowly and clearly. Short sentences. ONE idea per turn.
- Use ONLY simple, high-frequency words. No idioms, no slang, no complex grammar.
- Today the learner is practicing these target words: {TARGET_WORDS}. Use them naturally.
- Stay in the current scaffold mode: {MODE}. (echo | choose | fill_frame | guided | roleplay)
- NEVER say the learner is wrong. If they make a mistake, recast it: repeat their
  sentence back correctly and warmly, then continue.
- Be encouraging and brief. Give the learner lots of room to speak.
- If the learner is silent or stuck, offer a simple hint or an example answer.
- You may use a Vietnamese word ONLY to rescue a total breakdown, then return to English.
```

### Turn-taking (critical)
Beginners pause a lot mid-sentence while searching for words. **Do not cut them off.** Either lengthen the end-of-turn silence threshold substantially, or provide a **push-to-talk** control so the learner signals when they're done. Slower is fine; interrupting is fatal to the experience.

### Post-session feedback
Capture errors during the block. At the **Reward** step, show 1–2 gentle recasts. Never interrupt mid-conversation with corrections.

---

## 8. Lesson Generation (the engine)

A single server-side call produces the day's content. Inputs: the learner's `known` word set, today's target words, a chosen theme (rotate through the learner's interests), and the target CEFR-ish level.

**Output (strict JSON):**
```json
{
  "theme": "string",
  "dialogue": [{ "speaker": "A|B", "en": "string", "vi": "string" }],
  "target_words": [{ "word": "string", "en_def": "string", "vi": "string", "example": "string" }],
  "speaking_prompts": ["string"],
  "produce_prompt": "string"
}
```

**Generation prompt (server-side):**
```
Create a beginner English mini-lesson.
THEME: {THEME}   (e.g. "talking about last weekend's football match")
ALLOWED VOCABULARY: only these known words {KNOWN_WORDS} plus today's NEW target words {TARGET_WORDS}.
Do not use any other vocabulary. Keep grammar simple (present/past simple, basic questions).
Produce:
1. A natural 4–8 line dialogue between A and B that uses every target word at least once,
   each line with an English line and its Vietnamese translation.
2. For each target word: a simple English definition, Vietnamese gloss, and one example sentence.
3. 3 speaking prompts that practice the target words (suitable for the scaffold ladder).
4. One "produce" prompt asking the learner to say 1–2 sentences about their OWN life using the words.
Return ONLY valid JSON in the schema provided. No prose, no markdown.
```

**Validation:** after generation, run the profiler over `dialogue[].en`. If coverage against `known + target` is below threshold, regenerate (max 2 retries) before serving.

---

## 9. Data Model (SQLite)

```
words            (id, rank, headword, status, source['ngsl'|'ngsl_spoken'],
                  added_on)                              -- the NGSL vocabulary
srs_state        (word_id FK, ease, interval_days, repetitions, due_date, last_review)
lessons          (id, date, theme, dialogue_json, targets_json, created_at)
session_log      (id, lesson_id FK, completed_steps, errors_json, created_at)
progress         (id, date, known_count, coverage_pct, streak)
```

---

## 10. API Endpoints (FastAPI)

```
GET  /lesson/today              -> today's lesson (generate if not yet created)
POST /lesson/regenerate         -> force a new lesson (new theme)
GET  /vocab/review              -> words due for SRS review today
POST /vocab/review              -> submit recall result -> updates SM-2 state
POST /vocab/promote             -> mark target words as 'known' after a session
POST /profiler/score            -> {text} -> {coverage_pct, unknown_words[]}
POST /session/realtime-token    -> mint ephemeral OpenAI Realtime token (+ instructions)
GET  /progress                  -> streak, known_count, coverage history
```

---

## 11. Build Phases (MVP first — do not build everything at once)

**Phase 1 — Foundation**
- FastAPI + SQLite skeleton. Ingest NGSL + NGSL-Spoken into `words`.
- Profiler endpoint with spaCy lemmatization (`/profiler/score`).
- React + Vite shell.

**Phase 2 — One full lesson, end to end**
- Lesson generation + JSON validation + profiler check.
- Render steps 1–3 (Review with a seeded deck, Input dialogue with VI toggle + TTS, Notice).
- SM-2 scheduler + `/vocab/review`.

**Phase 3 — Speaking**
- Ephemeral-token endpoint + WebRTC connection to Realtime API.
- Scaffold ladder rungs 1–3 (echo, choose, fill-frame) in one theme.
- Push-to-talk + recasting instructions.

**Phase 4 — Close the loop**
- Produce step, Reward step (recaps, streak, recasts).
- Progress dashboard + coverage meter.
- Theme rotation across the learner's interests.

Ship Phase 2 as the first usable version. Everything after is additive.

---

## 12. Setup

**Prereqs:** Node 18+, Python 3.11+, an OpenAI API key.

**Environment (`.env`, server only):**
```
OPENAI_API_KEY=sk-...
OPENAI_TEXT_MODEL=<current text model id>
OPENAI_REALTIME_MODEL=<current realtime model id>
```

**Data files:** download NGSL and NGSL-Spoken CSVs from `newgeneralservicelist.org` into `/backend/data/`.

**Backend:**
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy openai spacy
python -m spacy download en_core_web_sm
python ingest_ngsl.py        # load CSVs into SQLite
uvicorn main:app --reload
```

**Frontend:**
```
cd frontend
npm install
npm run dev
```

---

## 13. Non-Goals (for now)

- No accounts, no multi-user, no payments.
- No IELTS exam-strategy modules (premature below B1).
- No reading/listening *test* engine — that's a commodity; the differentiators here are generated comprehensible input + AI speaking.
- No reproduction of copyrighted graded readers; generate original content instead.