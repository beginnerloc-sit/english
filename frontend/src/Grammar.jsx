import React, { useEffect, useState } from "react";
import { api, speak } from "./api.js";

const PER_PAGE = 8;

// Grammar review — the points you've learned, paginated, tap to expand.
export default function Grammar() {
  const [items, setItems] = useState(null);
  const [openG, setOpenG] = useState(null);
  const [page, setPage] = useState(0);

  useEffect(() => {
    api.getGrammar().then(setItems).catch(() => setItems([]));
  }, []);

  if (!items)
    return <div className="card-center"><div className="spinner" /></div>;

  const learned = items.filter((g) => g.learned);
  const pageCount = Math.max(1, Math.ceil(learned.length / PER_PAGE));
  const safe = Math.min(page, pageCount - 1);
  const slice = learned.slice(safe * PER_PAGE, safe * PER_PAGE + PER_PAGE);

  return (
    <div className="view lessons-view">
      <div className="view-head">
        <div className="avatar">🔤</div>
        <div>
          <h2>Ngữ pháp</h2>
          <p className="muted">{learned.length} điểm đã học · chạm để xem lại</p>
        </div>
      </div>

      {learned.length === 0 ? (
        <p className="muted">Hoàn thành một bài học để học điểm ngữ pháp đầu tiên.</p>
      ) : (
        <>
          <div className="review-list lesson-list">
            {slice.map((g) => (
              <div key={g.id} className={`review-g ${openG === g.id ? "open" : ""}`}>
                <button className="review-g-head" onClick={() => setOpenG(openG === g.id ? null : g.id)}>
                  <span className="review-g-title">{g.title}</span>
                  <span className="review-g-lvl">{g.level}</span>
                </button>
                {openG === g.id && (
                  <div className="review-g-body">
                    {g.structure_hint && <div className="grammar-struct">{g.structure_hint}</div>}
                    {g.explanation && <p className="grammar-exp">{g.explanation}</p>}
                    {g.vi_note && <p className="grammar-vi">{g.vi_note}</p>}
                    {g.examples?.map((e, i) => (
                      <div key={i} className="review-ex">
                        <span>{e}</span>
                        <button className="icon-btn mini" onClick={() => speak(e)}><Spk /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {pageCount > 1 && (
            <div className="pager">
              <button className="ghost" onClick={() => setPage(safe - 1)} disabled={safe === 0}>
                ‹ Trước
              </button>
              <span className="pager-info">Trang {safe + 1}/{pageCount}</span>
              <button className="ghost" onClick={() => setPage(safe + 1)} disabled={safe >= pageCount - 1}>
                Tiếp ›
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Spk() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
      <path d="M11 5 6 9H2v6h4l5 4V5z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7" />
    </svg>
  );
}
