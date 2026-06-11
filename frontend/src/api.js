// Thin API client. In dev, Vite proxies these paths to the FastAPI backend.
const BASE = import.meta.env.VITE_API_BASE || "";

const TOKEN_KEY = "ll_token";
export const auth = {
  get: () => localStorage.getItem(TOKEN_KEY) || "",
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

// Optional: called when a request 401s so the app can show the login screen.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function req(path, opts = {}) {
  const token = auth.get();
  const res = await fetch(BASE + path, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...opts,
  });
  if (!res.ok) {
    if (res.status === 401) {
      auth.clear();
      onUnauthorized?.();
    }
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => req("/health"),
  register: (username, password, name) =>
    req("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password, name }),
    }),
  login: (username, password) =>
    req("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => req("/auth/me"),
  logout: () => req("/auth/logout", { method: "POST" }),
  lessonToday: () => req("/lesson/today"),
  getLessons: () => req("/lessons"),
  getLesson: (id) => req(`/lesson/${id}`),
  completeLesson: (id) => req(`/lesson/${id}/complete`, { method: "POST" }),
  getGrammar: () => req("/grammar"),
  getLeaderboard: () => req("/leaderboard"),
  getWords: () => req("/words"),
  saveConversation: (lesson_id, theme, turns) =>
    req("/conversation", {
      method: "POST",
      body: JSON.stringify({ lesson_id, theme, turns }),
    }),
  getConversations: () => req("/conversations"),
  getConversation: (id) => req(`/conversation/${id}`),
  explainWord: (headword) =>
    req("/word/explain", { method: "POST", body: JSON.stringify({ headword }) }),
  vocabDue: () => req("/vocab/review"),
  submitReview: (word_id, quality) =>
    req("/vocab/review", {
      method: "POST",
      body: JSON.stringify({ word_id, quality }),
    }),
  promote: (headwords) =>
    req("/vocab/promote", {
      method: "POST",
      body: JSON.stringify({ headwords }),
    }),
  profile: (text) =>
    req("/profiler/score", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  realtimeToken: (
    target_words,
    mode,
    script = [],
    student_name = "",
    target_info = [],
    grammar = {}
  ) =>
    req("/session/realtime-token", {
      method: "POST",
      body: JSON.stringify({
        target_words,
        mode,
        script,
        student_name,
        target_info,
        grammar,
      }),
    }),
  instructions: (target_words, mode) =>
    req("/session/instructions", {
      method: "POST",
      body: JSON.stringify({ target_words, mode }),
    }),
  // Silent transcription-only realtime session (read-aloud mic).
  transcribeToken: () =>
    req("/session/realtime-token", {
      method: "POST",
      body: JSON.stringify({ transcribe_only: true }),
    }),
  progress: () => req("/progress"),
  getProfile: () => req("/profile"),
  getAccount: () => req("/account"),
  setAccount: (name) =>
    req("/account", { method: "POST", body: JSON.stringify({ name }) }),
  getSettings: () => req("/settings"),
  setTheme: (active_theme) =>
    req("/settings", {
      method: "POST",
      body: JSON.stringify({ active_theme }),
    }),
  translate: (text) =>
    req("/translate", { method: "POST", body: JSON.stringify({ text }) }),
  transcribe: async (blob, filename = "audio.webm") => {
    const fd = new FormData();
    fd.append("file", blob, filename);
    const token = auth.get();
    const res = await fetch(BASE + "/transcribe", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) throw new Error("transcribe failed");
    return res.json();
  },
  saveProduction: (lesson_id, text) =>
    req("/produce", {
      method: "POST",
      body: JSON.stringify({ lesson_id, text }),
    }),
  logSession: (lesson_id, completed_steps, errors) =>
    req("/session/log", {
      method: "POST",
      body: JSON.stringify({ lesson_id, completed_steps, errors }),
    }),
};

// Natural reading voice via the backend (OpenAI TTS), with the monotone browser
// voice as a fallback if the key/endpoint is unavailable. Audio is cached per
// text so replays are instant.
const _ttsCache = new Map();

// ONE reused <audio> element. Mobile blocks play() outside a user gesture, but a
// single element "unlocked" once by a gesture can be replayed programmatically —
// so later lines auto-play. (A brand-new Audio() each time stays blocked.)
let _audioEl = null;
function audioEl() {
  if (!_audioEl) _audioEl = new Audio();
  return _audioEl;
}

// Call inside a user gesture (e.g. first mic press) to allow later auto-play.
export function unlockAudio() {
  const a = audioEl();
  a.muted = true;
  a.play().then(() => { a.pause(); a.muted = false; }).catch(() => { a.muted = false; });
}

// Rough pitch split so the two speakers still differ on the fallback voice.
const _LOW_VOICES = new Set(["onyx", "echo", "fable"]);

function browserSpeak(text, rate, voice) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = rate;
  u.pitch = voice && _LOW_VOICES.has(voice) ? 0.7 : 1.15;
  window.speechSynthesis.speak(u);
}

export function stopAudio() {
  if (_audioEl) _audioEl.pause();
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

// Pause only the played clip (doesn't touch speechSynthesis / mic).
export function pauseAudio() {
  if (_audioEl) _audioEl.pause();
}

// Resolves when playback *finishes* so callers can chain lines sequentially.
export async function speak(text, { rate = 0.95, voice } = {}) {
  text = (text || "").trim();
  if (!text) return;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  try {
    const key = `${voice || ""}|${text}`;
    let url = _ttsCache.get(key);
    if (!url) {
      const res = await fetch(BASE + "/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speed: rate, voice }),
      });
      if (!res.ok) throw new Error("tts unavailable");
      url = URL.createObjectURL(await res.blob());
      _ttsCache.set(key, url);
    }
    const a = audioEl();
    a.src = url;
    a.muted = false;
    await new Promise((resolve) => {
      a.onended = resolve;
      a.onerror = resolve;
      a.play().catch(() => resolve());
    });
  } catch {
    browserSpeak(text, rate, voice); // graceful fallback
  }
}
