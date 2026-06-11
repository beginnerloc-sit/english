import React, { useEffect, useState } from "react";
import { api } from "./api.js";

const fmtDate = (iso) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso.slice(0, 10);
  }
};

// Review saved speaking transcripts.
export default function Conversations() {
  const [list, setList] = useState(null);
  const [active, setActive] = useState(null); // {id, theme, turns, created_at}

  useEffect(() => {
    api.getConversations().then(setList).catch(() => setList([]));
  }, []);

  if (active) {
    return (
      <div className="view">
        <div className="session-bar">
          <span className="session-theme">{active.theme || "Hội thoại"}</span>
          <button className="ghost mini" onClick={() => setActive(null)}>‹ Quay lại</button>
        </div>
        <div className="convo" style={{ flex: "none", height: "auto", maxHeight: "none" }}>
          {active.turns.map((t, i) => (
            <div key={i} className={`turn ${t.role}`}>
              <span className="turn-who">{t.role === "teacher" ? "Giáo viên" : "Bạn"}</span>
              <div className="turn-bubble">
                <p className="turn-en">{t.en}</p>
                {t.vi && <p className="turn-vi">{t.vi}</p>}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!list) return <div className="card-center"><div className="spinner" /></div>;

  return (
    <div className="view">
      <div className="view-head">
        <div className="avatar">💬</div>
        <div>
          <h2>Hội thoại đã luyện</h2>
          <p className="muted">{list.length} buổi · chạm để xem lại</p>
        </div>
      </div>

      {list.length === 0 ? (
        <p className="muted">Hoàn thành một buổi Luyện nói để lưu hội thoại tại đây.</p>
      ) : (
        <div className="lesson-list">
          {list.map((c) => (
            <button
              key={c.id}
              className="lesson-row"
              onClick={() => api.getConversation(c.id).then(setActive).catch(() => {})}
            >
              <span className="lesson-seq">💬</span>
              <span className="lesson-main">
                <span className="lesson-theme">{c.theme || "Hội thoại"}</span>
                <span className="lesson-grammar">{fmtDate(c.created_at)}</span>
              </span>
              <span className="lesson-words">{c.turn_count} lượt</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
