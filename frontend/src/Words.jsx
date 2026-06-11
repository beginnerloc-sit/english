import React, { useEffect, useRef, useState } from "react";
import { api, speak } from "./api.js";
import { Speak } from "./Steps.jsx";

// "My Words": each word is its own flashcard — tap to flip and see the meaning,
// or 🎙 to practice it in a short chat with the teacher. No forced linear deck.
export default function Words({ studentName }) {
  const [words, setWords] = useState(null);
  const [practiceWord, setPracticeWord] = useState(null);
  const [open, setOpen] = useState(() => new Set()); // revealed headwords
  const [details, setDetails] = useState({}); // headword -> {en_def, vi, example}
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const fetched = useRef(new Set());
  const PER_PAGE = 10;

  useEffect(() => {
    api.getWords().then(setWords).catch(() => setWords([]));
  }, []);

  const flip = (w) => {
    setOpen((prev) => {
      const n = new Set(prev);
      n.has(w.headword) ? n.delete(w.headword) : n.add(w.headword);
      return n;
    });
    // Fill in any missing meaning/example (generated + saved server-side).
    if (!(w.vi && w.en_def && w.example) && !fetched.current.has(w.headword)) {
      fetched.current.add(w.headword);
      api
        .explainWord(w.headword)
        .then((r) => setDetails((c) => ({ ...c, [w.headword]: r })))
        .catch(() => {});
    }
  };

  if (words === null)
    return <div className="card-center"><div className="spinner" /></div>;

  // Focused teacher practice for one word.
  if (practiceWord) {
    const lesson = {
      id: null,
      seq: 0,
      theme: `the word "${practiceWord.headword}"`,
      target_words: [
        { word: practiceWord.headword, vi: practiceWord.vi || "", example: practiceWord.example || "" },
      ],
      speaking_script: [
        {
          id: "w1",
          goal: `Practice "${practiceWord.headword}"`,
          say: `Help the student understand and USE the word "${practiceWord.headword}" in their own sentences, then have a short chat using it.`,
          word: practiceWord.headword,
        },
      ],
      grammar: {},
    };
    return (
      <div className="view">
        <div className="session-bar">
          <span className="session-theme">Luyện · {practiceWord.headword}</span>
          <button className="ghost mini" onClick={() => setPracticeWord(null)}>✕ Quay lại</button>
        </div>
        <main className="card">
          <Speak lesson={lesson} studentName={studentName} onDone={() => setPracticeWord(null)} />
        </main>
      </div>
    );
  }

  return (
    <div className="view lessons-view">
      <div className="view-head">
        <div className="avatar">📖</div>
        <div>
          <h2>Từ vựng</h2>
          <p className="muted">{words.length} từ · chạm để xem nghĩa, 🎙 để luyện</p>
        </div>
      </div>

      {words.length === 0 ? (
        <p className="muted">Hoàn thành một bài học để bắt đầu thu thập từ.</p>
      ) : (
        <>
          <div className="search-bar">
            <span className="search-ico">🔍</span>
            <input
              className="search-input"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setPage(0); }}
              placeholder="Tìm từ…"
            />
            {query && (
              <button className="search-clear" onClick={() => { setQuery(""); setPage(0); }}>✕</button>
            )}
          </div>

          {(() => {
            const q = query.trim().toLowerCase();
            const filtered = q
              ? words.filter(
                  (w) =>
                    w.headword.toLowerCase().includes(q) ||
                    (details[w.headword]?.vi || w.vi || "").toLowerCase().includes(q)
                )
              : words;
            if (filtered.length === 0)
              return <p className="muted">Không tìm thấy từ nào.</p>;
            const pageCount = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
            const safe = Math.min(page, pageCount - 1);
            const slice = filtered.slice(safe * PER_PAGE, safe * PER_PAGE + PER_PAGE);
            return (
              <>
              <div className="vocab-list">
                {slice.map((w) => {
                  const isOpen = open.has(w.headword);
                  const d = details[w.headword] || {};
                  const vi = w.vi || d.vi || "";
                  const def = w.en_def || d.en_def || "";
                  const ex = w.example || d.example || "";
                  return (
                    <div key={w.headword} className={`vocab-card ${isOpen ? "open" : ""}`}>
                      <button className="vocab-flip" onClick={() => flip(w)}>
                        <span className="vocab-word">{w.headword}</span>
                        {isOpen ? (
                          <span className="vocab-meaning">
                            {vi && <span className="vocab-vi">{vi}</span>}
                            {def && <span className="vocab-def">{def}</span>}
                            {ex && <span className="vocab-ex">“{ex}”</span>}
                            {!vi && !def && !ex && (
                              <span className="vocab-def">Đang tải nghĩa…</span>
                            )}
                          </span>
                        ) : (
                          <span className="vocab-hint">chạm để xem nghĩa</span>
                        )}
                      </button>
                      <div className="vocab-actions">
                        <button className="icon-btn" title="nghe" onClick={() => speak(w.headword)}>
                          <SpkSmall />
                        </button>
                        <button
                          className="icon-btn vocab-mic"
                          title="luyện với giáo viên"
                          onClick={() => setPracticeWord(w)}
                        >
                          <MicIcon />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
              {pageCount > 1 && (
                <div className="pager">
                  <button className="ghost" onClick={() => setPage(safe - 1)} disabled={safe === 0}>
                    ‹ Trước
                  </button>
                  <span className="pager-info">Trang {safe + 1}/{pageCount}</span>
                  <button
                    className="ghost"
                    onClick={() => setPage(safe + 1)}
                    disabled={safe >= pageCount - 1}
                  >
                    Tiếp ›
                  </button>
                </div>
              )}
              </>
            );
          })()}
        </>
      )}
    </div>
  );
}

function MicIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0M12 19v3" />
    </svg>
  );
}
function SpkSmall() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
      <path d="M11 5 6 9H2v6h4l5 4V5z" /><path d="M15.5 8.5a5 5 0 0 1 0 7" />
    </svg>
  );
}
