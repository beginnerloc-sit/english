import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { Review, Input, Notice, Speak, Reward } from "./Steps.jsx";

const STEPS = [
  { key: "review", label: "Ôn tập", time: "2p" },
  { key: "input", label: "Hội thoại", time: "3p" },
  { key: "notice", label: "Từ mới", time: "4p" },
  { key: "speak", label: "Luyện nói", time: "5p" },
  { key: "reward", label: "Hoàn thành", time: "1p" },
];

// Runs one lesson from the shared bank (a chosen lessonId, or the next one).
export default function Session({ lessonId, studentName, onProgress, onExit }) {
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState(null);
  const [step, setStep] = useState(0);
  const [speechErrors, setSpeechErrors] = useState([]);

  useEffect(() => {
    const load = lessonId ? api.getLesson(lessonId) : api.lessonToday();
    load.then(setLesson).catch((e) => setError(e.message));
  }, [lessonId]);

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const pct = Math.round(
    ((step + (step === STEPS.length - 1 ? 1 : 0)) / STEPS.length) * 100
  );

  if (error)
    return (
      <div className="center-screen">
        <div className="card error">
          <div className="icon">📚</div>
          <h2>Chưa có bài học</h2>
          <p className="muted">{error}</p>
          <div className="actions">
            <button className="primary" onClick={() => location.reload()}>
              Thử lại
            </button>
            <button className="ghost" onClick={onExit}>
              Quay lại
            </button>
          </div>
        </div>
      </div>
    );

  if (!lesson)
    return (
      <div className="center-screen">
        <div className="card-center">
          <div className="spinner" />
          <p className="muted">Đang tải bài học…</p>
        </div>
      </div>
    );

  return (
    <div className="session">
      <div className="session-bar">
        <span className="session-theme">
          Bài {lesson.seq} · {lesson.theme}
        </span>
        <button className="ghost mini" onClick={onExit}>
          ✕ Thoát
        </button>
      </div>

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="stepper">
        {STEPS.map((s, i) => (
          <div
            key={s.key}
            className={`step-dot ${i === step ? "active" : ""} ${
              i < step ? "done" : ""
            }`}
            onClick={() => i < step && setStep(i)}
          >
            <span className="num">
              <span>{i + 1}</span>
            </span>
            <span className="lbl">{s.label}</span>
          </div>
        ))}
      </div>

      <main className="card" key={step}>
        {STEPS[step].key === "review" && <Review onDone={next} />}
        {STEPS[step].key === "input" && <Input lesson={lesson} onDone={next} />}
        {STEPS[step].key === "notice" && <Notice lesson={lesson} onDone={next} />}
        {STEPS[step].key === "speak" && (
          <Speak
            lesson={lesson}
            studentName={studentName}
            onError={(t) => setSpeechErrors((e) => [...e, t])}
            onDone={next}
          />
        )}
        {STEPS[step].key === "reward" && (
          <Reward lesson={lesson} errors={speechErrors} onProgress={onProgress} />
        )}
      </main>
    </div>
  );
}
