import React, { useEffect, useState } from "react";
import { api } from "./api.js";

const LEVELS = ["A1", "A2", "B1", "B2"];
const PER_PAGE = 6;

// Lesson library: the shared bank. Filter by level, page through, pick any.
export default function Library({ onPick }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [level, setLevel] = useState("all");
  const [page, setPage] = useState(0);

  useEffect(() => {
    api.getLessons().then(setData).catch((e) => setErr(e.message));
  }, []);

  if (err)
    return (
      <div className="card-center">
        <div className="celebrate">📚</div>
        <p className="muted">{err}</p>
        <button className="ghost" onClick={() => location.reload()}>Thử lại</button>
      </div>
    );
  if (!data)
    return (
      <div className="card-center">
        <div className="spinner" />
      </div>
    );

  if (!data.lessons.length)
    return (
      <div className="view">
        <div className="view-head">
          <div className="avatar">📚</div>
          <div>
            <h2>Bài học</h2>
            <p className="muted">Chưa có bài học nào.</p>
          </div>
        </div>
        <p className="muted">Tạo kho bài học chung từ terminal:</p>
        <span className="code-hint">python generate_lessons.py 30</span>
      </div>
    );

  const doneCount = data.lessons.filter((l) => l.completed).length;
  // Only show level chips that actually exist in the bank.
  const presentLevels = LEVELS.filter((lv) => data.lessons.some((l) => l.level === lv));

  const filtered =
    level === "all"
      ? data.lessons
      : data.lessons.filter((l) => l.level === level);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const safePage = Math.min(page, pageCount - 1);
  const slice = filtered.slice(safePage * PER_PAGE, safePage * PER_PAGE + PER_PAGE);

  const setLv = (lv) => { setLevel(lv); setPage(0); };

  return (
    <div className="view lessons-view">
      <div className="view-head">
        <div className="avatar">📚</div>
        <div>
          <h2>Bài học</h2>
          <p className="muted">
            Đã xong {doneCount}/{data.lessons.length} · chạm để học hoặc ôn lại
          </p>
        </div>
      </div>

      <div className="level-chips">
        <button className={`chip ${level === "all" ? "active" : ""}`} onClick={() => setLv("all")}>
          Tất cả
        </button>
        {presentLevels.map((lv) => (
          <button key={lv} className={`chip ${level === lv ? "active" : ""}`} onClick={() => setLv(lv)}>
            {lv}
          </button>
        ))}
      </div>

      <div className="lesson-list">
        {slice.map((l) => (
          <button
            key={l.id}
            className={`lesson-row ${l.completed ? "done" : ""} ${l.is_next ? "next" : ""}`}
            onClick={() => onPick(l.id)}
          >
            <span className="lesson-seq">{l.completed ? "✓" : l.seq}</span>
            <span className="lesson-main">
              <span className="lesson-theme">{l.theme}</span>
              <span className="lesson-grammar">
                {l.level ? `${l.level} · ` : ""}{l.grammar || ""}
              </span>
            </span>
            {l.is_next && <span className="lesson-badge">Tiếp</span>}
            <span className="lesson-words">{l.word_count} từ</span>
          </button>
        ))}
      </div>

      {pageCount > 1 && (
        <div className="pager">
          <button className="ghost" onClick={() => setPage(safePage - 1)} disabled={safePage === 0}>
            ‹ Trước
          </button>
          <span className="pager-info">Trang {safePage + 1}/{pageCount}</span>
          <button
            className="ghost"
            onClick={() => setPage(safePage + 1)}
            disabled={safePage >= pageCount - 1}
          >
            Tiếp ›
          </button>
        </div>
      )}
    </div>
  );
}
