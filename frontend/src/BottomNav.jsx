import React from "react";

const ITEM = (key, ico, label) => ({ key, ico, label });
const LEFT = [ITEM("home", "🏠", "Trang chủ"), ITEM("lessons", "📚", "Bài học")];
const RIGHT = [ITEM("words", "📖", "Từ vựng"), ITEM("profile", "👤", "Hồ sơ")];

// Bottom navigation: Home · Lessons · (Start FAB) · Words · Profile.
export default function BottomNav({ view, inSession, onNavigate, onStartToggle }) {
  const Item = ({ it }) => (
    <button
      className={`nav-item ${view === it.key ? "active" : ""}`}
      onClick={() => onNavigate(it.key)}
    >
      <span className="nav-ico">{it.ico}</span>
      <span className="nav-lbl">{it.label}</span>
    </button>
  );

  return (
    <nav className="bottom-nav">
      {LEFT.map((it) => <Item key={it.key} it={it} />)}

      <button
        className={`nav-fab ${inSession ? "in-session" : ""}`}
        onClick={onStartToggle}
        aria-label={inSession ? "Thoát bài học" : "Bắt đầu bài tiếp theo"}
      >
        <span className="fab-ico">{inSession ? "■" : "▶"}</span>
        <span className="fab-lbl">{inSession ? "Thoát" : "Học"}</span>
      </button>

      {RIGHT.map((it) => <Item key={it.key} it={it} />)}
    </nav>
  );
}
