import React, { useState } from "react";
import { api, auth } from "./api.js";

// Registration + login. On success, stores the token and calls onAuthed(name).
export default function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login"); // login | register
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const isRegister = mode === "register";

  const submit = async () => {
    setErr(null);
    if (!username.trim() || !password) {
      setErr("Vui lòng nhập tên đăng nhập và mật khẩu.");
      return;
    }
    setBusy(true);
    try {
      const res = isRegister
        ? await api.register(username.trim(), password, name.trim())
        : await api.login(username.trim(), password);
      auth.set(res.token);
      onAuthed(res.name || res.username);
    } catch (e) {
      setErr(e.message || "Có lỗi xảy ra.");
      setBusy(false);
    }
  };

  return (
    <div className="app">
      <div className="center-screen">
        <div className="card auth-card">
          <div className="brand" style={{ justifyContent: "center", marginBottom: 6 }}>
            <img src="/get_richz.png" alt="" className="brand-logo lg" />
            GetRichz
          </div>
          <h2 style={{ textAlign: "center" }}>
            {isRegister ? "Tạo tài khoản" : "Chào mừng trở lại"}
          </h2>
          <p className="muted center-text" style={{ marginTop: -4 }}>
            {isRegister
              ? "Bắt đầu hành trình tiếng Anh của bạn."
              : "Đăng nhập để tiếp tục học."}
          </p>

          <div className="auth-fields">
            {isRegister && (
              <input
                className="name-input auth-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Tên của bạn (giáo viên sẽ gọi)"
              />
            )}
            <input
              className="name-input auth-input"
              value={username}
              autoCapitalize="none"
              autoCorrect="off"
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Tên đăng nhập"
            />
            <input
              className="name-input auth-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="Mật khẩu"
            />
          </div>

          {err && <p className="auth-err">{err}</p>}

          <div className="actions">
            <button className="primary" onClick={submit} disabled={busy}>
              {busy ? "…" : isRegister ? "Tạo tài khoản" : "Đăng nhập"}
            </button>
          </div>

          <p className="muted center-text" style={{ marginTop: 14 }}>
            {isRegister ? "Đã có tài khoản?" : "Bạn mới đến?"}{" "}
            <button
              className="link-btn"
              onClick={() => {
                setErr(null);
                setMode(isRegister ? "login" : "register");
              }}
            >
              {isRegister ? "Đăng nhập" : "Tạo tài khoản"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
