import React, { useEffect, useState } from "react";
import { api } from "./api.js";

const ICONS = {
  "football and the Premier League": "⚽",
  "gym and fitness": "🏋️",
  "esports and video games": "🎮",
  "tech gadgets and phones": "📱",
  "fashion and streetwear": "👟",
  "food and cooking": "🍜",
  "travel and new places": "✈️",
  "music and concerts": "🎧",
  "movies and TV shows": "🎬",
  "cars and motorbikes": "🏍️",
  "daily routine and habits": "☀️",
  "shopping and saving money": "🛍️",
  "weather and the seasons": "🌦️",
  "health, sleep and energy": "😴",
  "pets and animals": "🐶",
  "social media and the internet": "💬",
  "weekend plans with friends": "🎉",
  "coffee, tea and drinks": "☕",
  "nature and the outdoors": "🌲",
  "your hometown and family": "🏡",
};

// Settings: choose the theme to study. Empty selection = auto-rotate through all
// interests (the README default). A custom theme is also allowed.
export default function Settings() {
  const [data, setData] = useState(null);
  const [active, setActive] = useState("");
  const [custom, setCustom] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api
      .getSettings()
      .then((d) => {
        setData(d);
        setActive(d.active_theme || "");
      })
      .catch((e) => setErr(e.message || "Failed to load"));
  }, []);

  const apply = async (theme) => {
    setActive(theme);
    await api.setTheme(theme).catch(() => {});
    setSaved(true);
    setTimeout(() => setSaved(false), 1600);
  };

  const choose = (theme) => apply(active === theme ? "" : theme);

  const applyCustom = () => {
    const t = custom.trim();
    if (t) {
      apply(t);
      setCustom("");
    }
  };

  if (err)
    return (
      <div className="card-center">
        <div className="celebrate">😕</div>
        <p className="muted">Couldn’t load settings: {err}</p>
        <button className="ghost" onClick={() => location.reload()}>Retry</button>
      </div>
    );

  if (!data)
    return (
      <div className="card-center">
        <div className="spinner" />
      </div>
    );

  const isCustomActive = active && !data.themes.includes(active);

  return (
    <div className="view">
      <div className="view-head">
        <div className="avatar">⚙️</div>
        <div>
          <h2>Settings</h2>
          <p className="muted">Choose what today’s lesson is about.</p>
        </div>
      </div>

      <h3>Theme to study</h3>
      <div className="theme-list">
        {isCustomActive && (
          <button className="theme-row active" onClick={() => apply("")}>
            <span className="theme-ico">✨</span>
            <span className="theme-name">{active}</span>
            <span className="theme-check">✓</span>
          </button>
        )}
        {data.themes.map((t) => (
          <button
            key={t}
            className={`theme-row ${active === t ? "active" : ""}`}
            onClick={() => choose(t)}
          >
            <span className="theme-ico">{ICONS[t] || "✨"}</span>
            <span className="theme-name">{t}</span>
            <span className="theme-check">{active === t ? "✓" : ""}</span>
          </button>
        ))}
      </div>

      <div className="theme-custom">
        <input
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && applyCustom()}
          placeholder="Or type your own theme…"
        />
        <button className="primary" style={{ width: "auto" }} onClick={applyCustom}>
          Use
        </button>
      </div>

      <p className="muted" style={{ marginTop: 14 }}>
        {active
          ? "New lessons will use this theme."
          : "No theme selected — lessons rotate through all your interests."}
        {saved && <span className="saved"> · Saved</span>}
      </p>
    </div>
  );
}
