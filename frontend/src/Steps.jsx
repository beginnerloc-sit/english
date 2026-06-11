import React, { useEffect, useRef, useState } from "react";
import { api, speak, stopAudio, pauseAudio } from "./api.js";
import { connectRealtime } from "./realtimeClient.js";

// Clean speaker icon (inherits text color) — replaces the inconsistent <SpeakerIcon /> emoji.
function SpeakerIcon({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ display: "block" }}
    >
      <path d="M11 5 6 9H2v6h4l5 4V5z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

function MicGlyph({ size = 26 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ display: "block" }}
    >
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0M12 19v3" />
    </svg>
  );
}

// --------------------------------------------------------------------------- //
// Step 1 — Review (SRS active recall). Start with a familiar win.
// --------------------------------------------------------------------------- //
export function Review({ onDone }) {
  const [due, setDue] = useState(null);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    api.vocabDue().then(setDue).catch(() => setDue([]));
  }, []);

  if (due === null)
    return (
      <div className="card-center">
        <div className="spinner" />
        <p className="muted">Đang tải thẻ ôn tập…</p>
      </div>
    );

  if (due.length === 0)
    return (
      <div className="card-center">
        <div className="celebrate">🌱</div>
        <h2>Khởi đầu mới</h2>
        <p className="muted">Hôm nay không có từ nào cần ôn.</p>
        <div className="actions">
          <button className="primary" onClick={onDone}>
            Bắt đầu bài học
          </button>
        </div>
      </div>
    );

  const word = due[idx];
  const rate = async (quality) => {
    await api.submitReview(word.word_id, quality).catch(() => {});
    setRevealed(false);
    if (idx + 1 >= due.length) onDone();
    else setIdx(idx + 1);
  };

  return (
    <div className="card-center">
      <div>
        <div className="eyebrow">Ôn tập · {idx + 1}/{due.length}</div>
        <h2 className="big-word">{word.headword}</h2>
      </div>
      <button className="ghost mini" onClick={() => speak(word.headword)}>
        <SpeakerIcon /> Nghe
      </button>
      {!revealed ? (
        <div className="actions">
          <p className="muted">Bạn còn nhớ nghĩa của từ này không?</p>
          <button className="primary" onClick={() => setRevealed(true)}>
            Hiện nghĩa
          </button>
        </div>
      ) : (
        <>
          <div className="review-meaning">
            {word.vi && <p className="rm-vi">{word.vi}</p>}
            {word.en_def && <p className="rm-def">{word.en_def}</p>}
            {word.example && <p className="rm-ex">“{word.example}”</p>}
            {!word.vi && !word.en_def && !word.example && (
              <p className="muted">Chưa có nghĩa lưu sẵn cho từ này.</p>
            )}
          </div>
          <p className="muted">Bạn nhớ tốt đến mức nào?</p>
          <div className="rating-row">
            <button onClick={() => rate(1)}>Lại<span className="k">&lt;1 ngày</span></button>
            <button onClick={() => rate(3)}>Khó<span className="k">sớm</span></button>
            <button onClick={() => rate(4)}>Tốt<span className="k">vài ngày</span></button>
            <button onClick={() => rate(5)}>Dễ<span className="k">vài tuần</span></button>
          </div>
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Step 2 — Input. Read-aloud / shadowing: the student reads each dialogue line
// out loud; the next line only appears once speech recognition matches the text.
// --------------------------------------------------------------------------- //
const VOICE_A = "echo";
const VOICE_B = "nova";
const lineVoice = (speaker) => (speaker === "A" ? VOICE_A : VOICE_B);

const _norm = (s) =>
  (s || "")
    .toLowerCase()
    .replace(/[^a-z0-9'\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

// Lenient match: most target words present (near-all for very short lines).
function readingMatches(target, said) {
  const t = _norm(target).split(" ").filter(Boolean);
  const s = new Set(_norm(said).split(" ").filter(Boolean));
  if (!t.length) return true;
  const hit = t.filter((w) => s.has(w)).length;
  const ratio = hit / t.length;
  return ratio >= (t.length <= 3 ? 0.99 : 0.6);
}

export function Input({ lesson, onDone }) {
  const dialogue = lesson.dialogue || [];
  const [showVi, setShowVi] = useState(false);
  const [idx, setIdx] = useState(0); // current line to read
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState("");
  const [result, setResult] = useState(null); // null | "checking" | "ok" | "retry"
  const [congrats, setCongrats] = useState(false);
  const streamRef = useRef(null);
  const mrRef = useRef(null);
  const chunksRef = useRef([]);
  const scrollRef = useRef(null);
  const congratsFired = useRef(false);
  const hasMic =
    typeof navigator !== "undefined" &&
    navigator.mediaDevices &&
    typeof window.MediaRecorder !== "undefined";
  const allDone = idx >= dialogue.length;
  const line = dialogue[idx];

  // Hear the current line automatically when it appears.
  useEffect(() => {
    if (line) speak(line.en, { voice: lineVoice(line.speaker) });
    setHeard("");
    setResult(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx]);

  // Auto-scroll the chat to the newest line / feedback.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [idx, heard, result]);

  // Show a completion popup once all lines are read.
  useEffect(() => {
    if (allDone && !congratsFired.current) {
      congratsFired.current = true;
      setCongrats(true);
    }
  }, [allDone]);

  const advance = () => setIdx((i) => i + 1);

  // Hold-to-talk via MediaRecorder: record while held, transcribe on release.
  const readDown = async () => {
    if (!hasMic) return;
    pauseAudio(); // stop the auto-played line so the mic only hears the student
    try {
      if (!streamRef.current) {
        streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
    } catch {
      setResult("retry");
      setHeard("(không truy cập được micro)");
      return;
    }
    const target = line;
    chunksRef.current = [];
    const mr = new MediaRecorder(streamRef.current);
    mr.ondataavailable = (e) => { if (e.data && e.data.size) chunksRef.current.push(e.data); };
    mr.onstop = async () => {
      setListening(false);
      const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
      if (!blob.size) { setResult(null); return; }
      setResult("checking");
      try {
        const { text } = await api.transcribe(blob);
        const said = (text || "").trim();
        setHeard(said);
        if (said && target && readingMatches(target.en, said)) {
          setResult("ok");
          setTimeout(advance, 700);
        } else {
          setResult("retry");
        }
      } catch {
        setResult("retry");
        setHeard("(lỗi nhận dạng, thử lại)");
      }
    };
    mrRef.current = mr;
    setResult(null);
    setHeard("");
    mr.start();
    setListening(true);
  };
  const readUp = () => {
    try {
      if (mrRef.current && mrRef.current.state !== "inactive") mrRef.current.stop();
    } catch {}
  };

  // Release the mic stream on unmount.
  useEffect(
    () => () => {
      try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch {}
    },
    []
  );

  return (
    <div className="read-step">
      <div className="row-between read-head">
        <div className="eyebrow" style={{ margin: 0 }}>
          Hội thoại · {Math.min(idx + 1, dialogue.length)}/{dialogue.length}
        </div>
        <label className="toggle">
          <input type="checkbox" checked={showVi} onChange={(e) => setShowVi(e.target.checked)} />
          <span className="track" />
          Tiếng Việt
        </label>
      </div>

      {/* Scrollable chat: read lines + the current line to read */}
      <div className="read-scroll" ref={scrollRef}>
        <div className="dialogue">
          {dialogue.slice(0, idx).map((l, i) => (
            <div key={i} className={`bubble ${l.speaker === "A" ? "a" : "b"} read-done`}>
              <div className="line-en">
                <span>✓ {l.en}</span>
                <button className="icon-btn" onClick={() => speak(l.en, { voice: lineVoice(l.speaker) })}>
                  <SpeakerIcon />
                </button>
              </div>
              {showVi && <div className="line-vi">{l.vi}</div>}
            </div>
          ))}
          {!allDone && line && (
            <div className={`bubble ${line.speaker === "A" ? "a" : "b"} current`}>
              <div className="line-en">
                <span>{line.en}</span>
                <button className="icon-btn" onClick={() => speak(line.en, { voice: lineVoice(line.speaker) })}>
                  <SpeakerIcon />
                </button>
              </div>
              {showVi && <div className="line-vi">{line.vi}</div>}
            </div>
          )}
        </div>
      </div>

      {/* Pinned bottom controls */}
      {!allDone && line && hasMic && (
        <div className="read-controls">
          {result === "checking" ? (
            <p className="read-feedback">Đang kiểm tra…</p>
          ) : (
            heard && (
              <p className={`read-feedback ${result}`}>
                {result === "ok" ? "✓ Tuyệt vời! " : "Bạn đọc: "}“{heard}”
                {result === "retry" && " — thử lại nhé"}
              </p>
            )
          )}
          <button
            className={`mic-fab ${listening ? "on" : ""}`}
            onMouseDown={readDown}
            onMouseUp={readUp}
            onMouseLeave={() => listening && readUp()}
            onTouchStart={(e) => { e.preventDefault(); readDown(); }}
            onTouchEnd={(e) => { e.preventDefault(); readUp(); }}
            aria-label="Giữ để đọc"
          >
            <MicGlyph size={28} />
          </button>
          <span className="read-hint">
            {listening ? "Đang nghe — thả khi xong" : "Giữ để đọc"}
            {" · "}
            <button className="link-skip" onClick={advance}>Bỏ qua ›</button>
          </span>
        </div>
      )}

      {!allDone && line && !hasMic && (
        <div className="read-controls">
          <p className="muted">Trình duyệt không hỗ trợ ghi âm. Đọc to rồi nhấn tiếp.</p>
          <button className="primary" onClick={advance}>Tôi đã đọc ›</button>
        </div>
      )}

      {congrats && (
        <div className="modal-overlay" onClick={onDone}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="celebrate">🎉</div>
            <h2>Tuyệt vời!</h2>
            <p className="muted">
              Bạn đã đọc hết hội thoại. Cùng chuyển sang phần <strong>Từ mới</strong> nhé!
            </p>
            <div className="actions">
              <button className="primary" onClick={onDone}>Tiếp tục</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Step 3 — Notice (pull target words out; recognition level).
// --------------------------------------------------------------------------- //
export function Notice({ lesson, onDone }) {
  const cards = lesson.target_words;
  const grammar = lesson.grammar;
  const [idx, setIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [seen, setSeen] = useState(() => new Set());

  const w = cards[idx];
  const last = idx === cards.length - 1;

  const go = (n) => {
    setFlipped(false);
    setIdx(n);
  };
  const flip = () => {
    setFlipped((f) => !f);
    setSeen((s) => new Set(s).add(idx));
  };

  return (
    <div>
      {grammar && grammar.title && (
        <div className="grammar-card">
          <div className="grammar-head">
            <span className="grammar-tag">Ngữ pháp{grammar.level ? ` · ${grammar.level}` : ""}</span>
            <button className="icon-btn mini" onClick={() => speak(grammar.title)}><SpeakerIcon /></button>
          </div>
          <strong className="grammar-title">{grammar.title}</strong>
          {grammar.structure_hint && (
            <div className="grammar-struct">{grammar.structure_hint}</div>
          )}
          {grammar.explanation && <p className="grammar-exp">{grammar.explanation}</p>}
          {grammar.vi_note && <p className="grammar-vi">{grammar.vi_note}</p>}
          {grammar.examples?.length > 0 && (
            <ul className="grammar-ex">
              {grammar.examples.map((e, i) => (
                <li key={i}>
                  <span>{e}</span>
                  <button className="icon-btn mini" onClick={() => speak(e)}><SpeakerIcon /></button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="eyebrow">Từ mới · {idx + 1}/{cards.length}</div>
      <h3>Từ mới hôm nay</h3>

      <div className="flashcard" onClick={flip}>
        <div className={`flashcard-inner ${flipped ? "flipped" : ""}`}>
          <div className="face front">
            <button
              className="icon-btn card-audio"
              onClick={(e) => {
                e.stopPropagation();
                speak(w.word);
              }}
            >
              <SpeakerIcon />
            </button>
            <strong className="card-word">{w.word}</strong>
            <span className="flip-hint">chạm để lật</span>
          </div>
          <div className="face back">
            {w.en_def && <p className="def">{w.en_def}</p>}
            {w.vi && <p className="vi">{w.vi}</p>}
            {w.example && <p className="example">“{w.example}”</p>}
          </div>
        </div>
      </div>

      <div className="dots">
        {cards.map((c, i) => (
          <span
            key={c.word}
            className={`dot ${i === idx ? "active" : ""} ${seen.has(i) ? "seen" : ""}`}
            onClick={() => go(i)}
          />
        ))}
      </div>

      <div className="card-nav">
        <button className="ghost" onClick={() => go(idx - 1)} disabled={idx === 0}>
          ‹ Trước
        </button>
        {last ? (
          <button className="primary" style={{ width: "auto", flex: 1 }} onClick={onDone}>
            Xong
          </button>
        ) : (
          <button className="primary" style={{ width: "auto", flex: 1 }} onClick={() => go(idx + 1)}>
            Tiếp ›
          </button>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Step 4 — Speak. Backbone: a per-lesson SCRIPT of checkpoints. The AI guides
// the learner through them and marks each done (via a tool call in live mode, or
// keyword/manual in the guided fallback). The checklist shows live progress.
// --------------------------------------------------------------------------- //
function buildScript(lesson) {
  let base;
  if (lesson.speaking_script?.length) base = lesson.speaking_script;
  else if (lesson.speaking_prompts?.length)
    base = lesson.speaking_prompts.map((p, i) => ({ id: `p${i}`, goal: p, say: p }));
  else
    base = (lesson.target_words || []).map((w, i) => ({
      id: `w${i}`,
      goal: `Use “${w.word}” in a sentence`,
      say: `Get the learner to use the word "${w.word}".`,
      word: w.word,
    }));

  // Lead with a grammar checkpoint so the teacher teaches today's pattern first.
  const g = lesson.grammar;
  if (g && g.title) {
    return [
      {
        id: "grammar",
        goal: `Grammar: ${g.title}`,
        say:
          `Teach the pattern "${g.structure_hint || g.title}" simply in Vietnamese ` +
          `with one clear example, then get the student to say one short sentence ` +
          `using it.`,
      },
      ...base,
    ];
  }
  return base;
}

// Teacher emotion -> cartoon face + little mood badge.
const FACES = { idle: "🧑‍🏫", talking: "😄", listening: "🤗", think: "🤔", cheer: "🤩" };
const BADGES = { idle: "💬", talking: "🗣️", listening: "👂", think: "💭", cheer: "🎉" };

// The student is asking for help / signalling confusion — in English or Vietnamese.
// In these cases we must NOT advance; the teacher should explain and support.
const HELP_EN =
  /\b(help|i\s*(don'?t|do not|dont)\s*(understand|know|get)|what(?:'s| is| does)?|huh|pardon|sorry\??|again|repeat|slow(?:er|ly)?|confus|mean(?:ing)?|translat|explain|how do (?:i|you) say)\b/i;
const HELP_VI =
  /(không hiểu|ko hiểu|hông hiểu|hong hiểu|chưa hiểu|giúp|là gì|nghĩa (?:là|gì)|lặp lại|nói lại|nhắc lại|chậm|khó quá|khó hiểu|dịch|hiểu không|không biết|sao cơ|gì cơ|nói gì)/i;
const isHelpRequest = (t) => HELP_EN.test(t) || HELP_VI.test(t);

function Character({ face, badge, speaking, label, side }) {
  return (
    <div className={`char ${side} ${speaking ? "talking" : ""}`}>
      <div className="char-face">
        {face}
        {badge && <span className="char-badge">{badge}</span>}
      </div>
      <div className="char-label">{label}</div>
    </div>
  );
}

function Turn({ role, who, en, vi }) {
  return (
    <div className={`turn ${role}`}>
      <span className="turn-who">{who}</span>
      <div className="turn-bubble">
        <p className="turn-en">{en}</p>
        {vi ? <p className="turn-vi">{vi}</p> : null}
      </div>
    </div>
  );
}

export function Speak({ lesson, studentName, onError, onDone }) {
  const targets = lesson.target_words.map((w) => w.word);
  const script = buildScript(lesson);
  const [status, setStatus] = useState("idle"); // idle|connecting|live|fallback
  const [talking, setTalking] = useState(false);
  const [heard, setHeard] = useState("");
  const [done, setDone] = useState(() => new Set());
  const [mood, setMood] = useState("idle");
  const [turns, setTurns] = useState([]); // [{id, role, en, vi}]
  const [congrats, setCongrats] = useState(false); // free-conversation popup
  const sessionRef = useRef(null);
  const audioRef = useRef(null);
  const recRef = useRef(null);
  const doneRef = useRef(new Set()); // authoritative, synchronous
  const turnSeq = useRef(0);
  const logRef = useRef(null); // transcript scroll container
  const congratsFired = useRef(false);

  const allDone = done.size >= script.length;
  const cur = script.findIndex((c) => !done.has(c.id));

  // When the last checkpoint clears, celebrate + unlock free conversation.
  useEffect(() => {
    if (allDone && !congratsFired.current) {
      congratsFired.current = true;
      setCongrats(true);
    }
  }, [allDone]);

  const currentId = () => {
    const c = script.find((x) => !doneRef.current.has(x.id));
    return c ? c.id : null;
  };

  const markDone = (id) => {
    if (!id || doneRef.current.has(id)) return;
    doneRef.current = new Set(doneRef.current).add(id);
    setDone(new Set(doneRef.current));
    setMood("cheer");
  };

  // Append a turn to the transcript; English shows immediately, Vietnamese (and a
  // cleaned English line) fill in when the translation returns.
  const addTurn = (role, text) => {
    const t = (text || "").trim();
    if (!t) return;
    const id = ++turnSeq.current;
    setTurns((prev) => [...prev, { id, role, en: t, vi: "" }]);
    api
      .translate(t)
      .then((r) =>
        setTurns((prev) =>
          prev.map((x) =>
            x.id === id ? { ...x, en: r.en || x.en, vi: r.vi || "" } : x
          )
        )
      )
      .catch(() => {});
  };


  const startRealtime = async () => {
    setStatus("connecting");
    try {
      const tok = await api.realtimeToken(
        targets,
        "guided",
        script,
        studentName || "",
        lesson.target_words, // {word, vi, example} — so the teacher knows meanings
        lesson.grammar || {} // today's grammar pattern
      );
      const secret = tok.client_secret?.value || tok.client_secret;
      const session = await connectRealtime({
        clientSecret: secret,
        model: tok.model,
        onRemoteTrack: (stream) => {
          if (audioRef.current) audioRef.current.srcObject = stream;
        },
        onEvent: (ev) => {
          // Teacher started speaking.
          if (ev.type === "response.created") setMood("talking");
          if (ev.type === "response.done") setMood("idle");

          // Teacher's spoken line -> subtitle (+ emotion from its tone).
          if (
            (ev.type === "response.audio_transcript.done" ||
              ev.type === "response.output_audio_transcript.done" ||
              ev.type === "response.output_text.done") &&
            (ev.transcript || ev.text)
          ) {
            const t = ev.transcript || ev.text;
            addTurn("teacher", t);
            if (/\b(ha|haha|great|love|wow|nice|perfect|yay)\b/i.test(t))
              setMood("cheer");
          }

          // The model decides a checkpoint is complete -> tick the checklist.
          if (
            ev.type === "response.function_call_arguments.done" &&
            ev.name === "mark_checkpoint"
          ) {
            let id;
            try {
              id = JSON.parse(ev.arguments || "{}").id;
            } catch {}
            if (id) markDone(id);
            if (ev.call_id) {
              sessionRef.current?.send({
                type: "conversation.item.create",
                item: { type: "function_call_output", call_id: ev.call_id, output: "ok" },
              });
            }
          }

          // Student's turn recognized -> just log it. The server auto-replies
          // (create_response is on) using the full session instructions.
          if (ev.type === "conversation.item.input_audio_transcription.completed") {
            const t = ev.transcript || "";
            setHeard(t);
            addTurn("student", t);
            onError?.(t);
          }
        },
      });
      sessionRef.current = session;
      setStatus("live");
      session.send({ type: "response.create" }); // teacher greets first
    } catch {
      setStatus("fallback");
    }
  };

  useEffect(() => () => sessionRef.current?.close(), []);

  // Keep the transcript scrolled to the newest line.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [turns]);

  const pttDown = () => {
    setTalking(true);
    if (status === "live") {
      setMood("listening");
      sessionRef.current?.setMicEnabled(true);
    } else startRecognition();
  };
  const pttUp = () => {
    setTalking(false);
    if (status === "live") {
      setMood("think");
      sessionRef.current?.setMicEnabled(false);
    } else stopRecognition();
  };

  const startRecognition = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setHeard("(speech recognition not available in this browser)");
      return;
    }
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.onresult = (e) => {
      const text = e.results[0][0].transcript;
      setHeard(text);
      addTurn("student", text);
      onError?.(text);
      const c = script[cur];
      if (c && c.word && text.toLowerCase().includes(String(c.word).toLowerCase()))
        markDone(c.id);
    };
    rec.start();
    recRef.current = rec;
  };
  const stopRecognition = () => recRef.current?.stop();

  const started = status === "live" || status === "fallback";

  // Save the transcript for later review, then finish.
  const handleFinish = () => {
    if (turns.length && lesson.id) {
      api
        .saveConversation(
          lesson.id,
          lesson.theme,
          turns.map((t) => ({ role: t.role, en: t.en, vi: t.vi }))
        )
        .catch(() => {});
    }
    onDone();
  };

  // Round push-to-talk mic.
  const micButton = (
    <div className="ptt-mic-wrap">
      <button
        className={`mic-fab ${talking ? "on" : ""}`}
        onMouseDown={pttDown}
        onMouseUp={pttUp}
        onMouseLeave={() => talking && pttUp()}
        onTouchStart={(e) => { e.preventDefault(); pttDown(); }}
        onTouchEnd={(e) => { e.preventDefault(); pttUp(); }}
        aria-label="Giữ để nói"
      >
        <MicGlyph size={28} />
      </button>
      <span className="read-hint">{talking ? "Đang nghe — thả khi xong" : "Giữ để nói"}</span>
    </div>
  );

  return (
    <div className="speak-step">
      <div className="read-head row-between">
        <div className="eyebrow" style={{ margin: 0 }}>
          Luyện nói · {done.size}/{script.length} xong
        </div>
        {started && (
          <button
            className={`mini ${allDone ? "primary" : "ghost"}`}
            style={{ width: "auto" }}
            onClick={handleFinish}
            disabled={!allDone}
            title={allDone ? "Hoàn thành" : "Hoàn thành các điểm trước"}
          >
            Hoàn thành ✓
          </button>
        )}
      </div>

      {status === "idle" && (
        <>
          <ul className="checklist speak-scroll">
            {script.map((c, i) => (
              <li key={c.id} className="check-item">
                <span className="check-box">{i + 1}</span>
                <span className="check-goal">{c.goal}</span>
              </li>
            ))}
          </ul>
          <div className="speak-bottom">
            <button className="primary" onClick={startRealtime}>
              🎙 Bắt đầu luyện nói
            </button>
          </div>
        </>
      )}

      {status === "connecting" && (
        <div className="card-center" style={{ flex: 1 }}>
          <div className="spinner" />
          <p className="muted">Đang kết nối giáo viên…</p>
        </div>
      )}

      {status === "live" && (
        <>
          <div className="stage compact">
            <Character
              side="teacher"
              face={FACES[mood] || FACES.idle}
              badge={BADGES[mood] || BADGES.idle}
              speaking={mood === "talking" || mood === "cheer"}
              label="Giáo viên"
            />
            <Character side="student" face="🧑‍🎓" speaking={talking} label={studentName || "Bạn"} />
          </div>

          <div className="convo" ref={logRef}>
            {turns.length === 0 ? (
              <p className="convo-empty">Giáo viên đang bắt đầu… giữ nút bên dưới để nói.</p>
            ) : (
              turns.map((tn) => (
                <Turn
                  key={tn.id}
                  role={tn.role}
                  who={tn.role === "teacher" ? "Giáo viên" : studentName || "Bạn"}
                  en={tn.en}
                  vi={tn.vi}
                />
              ))
            )}
          </div>

          <div className="speak-bottom">
            <div className="progress-row">
              <span className="progress-now">
                {cur >= 0 ? script[cur]?.goal : "💬 Trò chuyện tự do"}
              </span>
              <div className="dots">
                {script.map((c, i) => (
                  <span key={c.id} className={`dot ${done.has(c.id) ? "seen" : ""} ${i === cur ? "active" : ""}`} />
                ))}
              </div>
            </div>
            {micButton}
          </div>
        </>
      )}

      {status === "fallback" && (
        <>
          <ul className="checklist speak-scroll">
            {script.map((c, i) => {
              const isDone = done.has(c.id);
              const isCur = i === cur && !isDone;
              return (
                <li key={c.id} className={`check-item ${isDone ? "done" : ""} ${isCur ? "cur" : ""}`}>
                  <span className="check-box">{isDone ? "✓" : i + 1}</span>
                  <span className="check-goal">{c.goal}</span>
                  <button className="icon-btn mini" onClick={() => speak(c.say || c.goal)} title="nghe">
                    <SpeakerIcon />
                  </button>
                  {!isDone && (
                    <button className="icon-btn mini" onClick={() => markDone(c.id)} title="đánh dấu xong">
                      ✓
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="speak-bottom">
            {micButton}
          </div>
        </>
      )}

      <audio ref={audioRef} autoPlay />

      {congrats && (
        <div className="modal-overlay" onClick={() => setCongrats(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="celebrate">🎉</div>
            <h2>Tuyệt vời!</h2>
            <p className="muted">
              Bạn đã hoàn thành tất cả các điểm của bài nói. Giờ là{" "}
              <strong>trò chuyện tự do</strong> — cứ nói chuyện thoải mái với giáo
              viên. Nhấn <strong>Hoàn thành</strong> khi bạn muốn kết thúc.
            </p>
            <div className="actions">
              <button className="primary" onClick={() => setCongrats(false)}>
                Tiếp tục trò chuyện
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Reward (mastered words, streak, gentle recast, tomorrow's hook).
// --------------------------------------------------------------------------- //
export function Reward({ lesson, errors, onProgress }) {
  const [progress, setProgress] = useState(null);
  const targets = lesson.target_words.map((w) => w.word);

  useEffect(() => {
    (async () => {
      // Mark this shared lesson complete: promotes words + grammar + streak.
      await api.completeLesson(lesson.id).catch(() => {});
      const p = await api.progress().catch(() => null);
      setProgress(p);
      onProgress?.(p);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const recast = errors[0];

  return (
    <div className="card-center">
      <div className="celebrate">🎉</div>
      <h2>Hôm nay xong rồi!</h2>

      <div>
        <p className="muted" style={{ marginBottom: 8 }}>Bạn đã học các từ này:</p>
        <div className="word-chips">
          {targets.map((w, i) => (
            <span key={w} className="chip active" style={{ animationDelay: `${i * 60}ms` }}>
              {w}
            </span>
          ))}
        </div>
      </div>

      {progress && (
        <div className="streak-card">
          <div className="stat">
            <div className="v">🔥 {progress.streak}</div>
            <div className="l">Chuỗi ngày</div>
          </div>
          <div className="stat">
            <div className="v">{progress.known_count}</div>
            <div className="l">Từ đã biết</div>
          </div>
        </div>
      )}

      {recast && (
        <div className="recast">
          💬 Bạn đã thử: “{recast}”. Cố gắng tốt lắm — mai nói lại chậm hơn nhé.
          Bạn đang tiến bộ thật sự!
        </div>
      )}

      <p className="muted">Hẹn gặp lại ngày mai nhé! 👋</p>
    </div>
  );
}
