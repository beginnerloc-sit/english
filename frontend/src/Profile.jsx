import React, { useEffect, useState } from "react";
import { api } from "./api.js";

// Profile: progress overview + quick links to lessons / words / grammar.
export default function Profile({ onRename, onLogout, onOpenLessons, onOpenWords, onOpenGrammar, onOpenConversations }) {
  const [p, setP] = useState(null);
  const [name, setName] = useState("");
  const [editing, setEditing] = useState(false);
  const [board, setBoard] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.getProfile().then((d) => { setP(d); setName(d.name || ""); }).catch((e) => setErr(e.message));
    api.getLeaderboard().then(setBoard).catch(() => {});
  }, []);

  const saveName = async () => {
    const n = name.trim();
    if (!n) return;
    await api.setAccount(n).catch(() => {});
    onRename?.(n);
    setEditing(false);
  };

  if (err)
    return (
      <div className="card-center">
        <div className="celebrate">😕</div>
        <p className="muted">{err}</p>
        <button className="ghost" onClick={() => location.reload()}>Thử lại</button>
      </div>
    );
  if (!p)
    return <div className="card-center"><div className="spinner" /></div>;

  return (
    <div className="view profile-view">
      <div className="view-head">
        <div className="avatar">🧑‍🎓</div>
        <div style={{ flex: 1 }}>
          {editing ? (
            <div className="theme-custom" style={{ marginTop: 0 }}>
              <input
                value={name}
                autoFocus
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && saveName()}
              />
              <button className="primary" style={{ width: "auto" }} onClick={saveName}>Lưu</button>
            </div>
          ) : (
            <>
              <h2>
                {p.name || "Bạn"}{" "}
                <button className="icon-btn mini" onClick={() => setEditing(true)} title="sửa tên">✎</button>
              </h2>
              <p className="muted">@{p.username} · 🔥 chuỗi {p.streak} ngày</p>
            </>
          )}
        </div>
      </div>

      <div className="stat-grid three">
        <div className="stat-tile accent" onClick={onOpenLessons}>
          <div className="v">{p.lessons_completed}/{p.lessons_total}</div>
          <div className="l">Bài học</div>
        </div>
        <div className="stat-tile accent" onClick={onOpenWords}>
          <div className="v">{p.known_count}</div>
          <div className="l">Từ vựng</div>
        </div>
        <div className="stat-tile accent" onClick={onOpenGrammar}>
          <div className="v">{p.grammar_learned}</div>
          <div className="l">Ngữ pháp</div>
        </div>
      </div>
      <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
        Chạm vào ô để xem lại bài học, từ vựng hoặc ngữ pháp đã học.
      </p>

      <button className="row-link" onClick={onOpenConversations}>
        <span className="rl-ico">💬</span>
        <span className="rl-main">Hội thoại đã luyện</span>
        <span className="rl-count">{p.conversations ?? 0}</span>
        <span className="rl-arrow">›</span>
      </button>

      {board.length > 0 && (
        <div className="leaderboard">
          <div className="lb-title">🏆 Bảng xếp hạng · Bài học</div>
          {board.map((r) => (
            <div key={r.rank} className={`lb-row ${r.is_me ? "me" : ""}`}>
              <span className="lb-rank">{["🥇", "🥈", "🥉"][r.rank - 1] || r.rank}</span>
              <span className="lb-name">{r.name}{r.is_me ? " (bạn)" : ""}</span>
              <span className="lb-count">{r.lessons}</span>
            </div>
          ))}
        </div>
      )}

      <div className="actions logout-row">
        <button className="ghost" onClick={onLogout}>Đăng xuất</button>
      </div>
    </div>
  );
}
