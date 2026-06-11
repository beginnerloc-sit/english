import React, { useEffect, useState } from "react";
import { api, auth, setUnauthorizedHandler } from "./api.js";
import Session from "./Session.jsx";
import Profile from "./Profile.jsx";
import Library from "./Library.jsx";
import Words from "./Words.jsx";
import Grammar from "./Grammar.jsx";
import Conversations from "./Conversations.jsx";
import BottomNav from "./BottomNav.jsx";
import Auth from "./Auth.jsx";

export default function App() {
  const [view, setView] = useState("home"); // home | lessons | profile | session
  const [account, setAccountState] = useState(undefined); // undefined=loading, null=logged out
  const [home, setHome] = useState(null); // {next lesson, progress}
  const [lessonId, setLessonId] = useState(null); // chosen lesson for session (null = next)

  const refreshHome = () => {
    Promise.all([
      api.getLessons().catch(() => null),
      api.getProfile().catch(() => null),
    ]).then(([lessons, profile]) => setHome({ lessons, profile }));
  };

  useEffect(() => {
    setUnauthorizedHandler(() => setAccountState(null));
    if (!auth.get()) return setAccountState(null);
    api
      .me()
      .then((a) => {
        setAccountState(a.name || a.username);
        refreshHome();
      })
      .catch(() => setAccountState(null));
  }, []);

  useEffect(() => {
    if (account && view !== "session") refreshHome();
  }, [view, account]);

  const startLesson = (id = null) => {
    setLessonId(id);
    setView("session");
  };
  const inSession = view === "session";
  const startToggle = () => (inSession ? setView("home") : startLesson(null));

  const logout = async () => {
    await api.logout().catch(() => {});
    auth.clear();
    setAccountState(null);
    setView("home");
  };

  if (account === undefined)
    return (
      <div className="app">
        <div className="center-screen"><div className="card-center"><div className="spinner" /></div></div>
      </div>
    );
  if (!account)
    return <Auth onAuthed={(name) => { setAccountState(name); refreshHome(); }} />;

  return (
    <div className="app">
      <header className="header">
        <div className="brand" onClick={() => setView("home")} style={{ cursor: "pointer" }}>
          <img src="/get_richz.png" alt="" className="brand-logo" />
          GetRichz
        </div>
        {home?.profile && (
          <span className="streak-mini">🔥 {home.profile.streak} · {home.profile.known_count} từ</span>
        )}
      </header>

      <div className="app-body">
        {view === "home" && (
          <Home
            name={account}
            home={home}
            onStartNext={() => startLesson(null)}
            onBrowse={() => setView("lessons")}
            onWords={() => setView("words")}
          />
        )}
        {view === "lessons" && <Library onPick={(id) => startLesson(id)} />}
        {view === "words" && (
          <Words studentName={account} onBack={() => setView("profile")} />
        )}
        {view === "grammar" && <Grammar />}
        {view === "conversations" && <Conversations />}
        {view === "profile" && (
          <Profile
            onRename={setAccountState}
            onLogout={logout}
            onOpenLessons={() => setView("lessons")}
            onOpenWords={() => setView("words")}
            onOpenGrammar={() => setView("grammar")}
            onOpenConversations={() => setView("conversations")}
          />
        )}
        {view === "session" && (
          <Session
            lessonId={lessonId}
            studentName={account}
            onProgress={() => {}}
            onExit={() => setView("home")}
          />
        )}
      </div>

      <BottomNav view={view} inSession={inSession} onNavigate={setView} onStartToggle={startToggle} />
    </div>
  );
}

function Home({ name, home, onStartNext, onBrowse, onWords }) {
  const list = home?.lessons?.lessons || [];
  const p = home?.profile;
  const next = list.find((l) => l.is_next) || list.find((l) => !l.completed) || list[0];
  const doneCount = list.filter((l) => l.completed).length;
  const total = list.length;
  const allDone = total > 0 && doneCount === total;
  const pct = total ? Math.round((doneCount / total) * 100) : 0;

  return (
    <div className="view home">
      <div className="home-greet">
        <h2>Chào {name} 👋</h2>
        <p className="muted">
          {p ? `🔥 chuỗi ${p.streak} ngày` : "Bắt đầu hành trình của bạn"}
        </p>
      </div>

      {next ? (
        <div className="continue-card" onClick={onStartNext}>
          <div className="cc-eyebrow">{allDone ? "Ôn tập" : "Tiếp tục học"}</div>
          <div className="cc-title">Bài {next.seq} · {next.theme}</div>
          <div className="cc-meta">
            {next.level ? `${next.level} · ` : ""}
            {next.grammar ? `${next.grammar} · ` : ""}{next.word_count} từ mới
          </div>
          <div className="cc-cta">▶ {allDone ? "Ôn lại bài này" : "Bắt đầu"}</div>
          <div className="cc-bar"><div className="cc-fill" style={{ width: `${pct}%` }} /></div>
          <div className="cc-progress">{doneCount}/{total} bài học · {pct}%</div>
        </div>
      ) : (
        <div className="card">
          <p className="muted">Chưa có bài học nào. Hãy tạo từ terminal:</p>
          <span className="code-hint">python generate_lessons.py 30</span>
        </div>
      )}

      <div className="home-stats">
        <div className="hstat"><div className="hv">{doneCount}</div><div className="hl">Bài đã xong</div></div>
        <div className="hstat"><div className="hv">{p?.known_count ?? 0}</div><div className="hl">Từ đã biết</div></div>
        <div className="hstat"><div className="hv">{p?.grammar_learned ?? 0}</div><div className="hl">Ngữ pháp</div></div>
      </div>

      <div className="home-tiles">
        <button className="home-tile" onClick={onBrowse}>
          <span className="ht-ico">📚</span>
          <span className="ht-main">Bài học</span>
          <span className="ht-sub">Chọn hoặc ôn lại</span>
        </button>
        <button className="home-tile" onClick={onWords}>
          <span className="ht-ico">📖</span>
          <span className="ht-main">Từ vựng</span>
          <span className="ht-sub">Thẻ ghi nhớ & luyện</span>
        </button>
      </div>
    </div>
  );
}
