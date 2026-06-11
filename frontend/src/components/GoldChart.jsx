import React from "react";
import { fmt } from "../format.js";

export default function GoldChart({ history }) {
  const pts = (history || []).slice(-300);
  const W = 600, H = 150, pad = 8;

  let body;
  if (pts.length < 2) {
    body = <p className="muted">aguardando mais saves para desenhar…</p>;
  } else {
    const xs = pts.map((p) => p.ticks);
    const ys = pts.map((p) => p.gold);
    const x0 = xs[0], x1 = xs[xs.length - 1];
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const sx = (x) => ((x - x0) / (x1 - x0 || 1)) * (W - 2 * pad) + pad;
    const sy = (y) => H - pad - ((y - yMin) / (yMax - yMin || 1)) * (H - 2 * pad);
    const line = pts.map((p) => `${sx(p.ticks).toFixed(1)},${sy(p.gold).toFixed(1)}`).join(" ");
    const area = `${pad},${H - pad} ${line} ${W - pad},${H - pad}`;
    body = (
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="chart">
        <defs>
          <linearGradient id="goldfill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(240,180,41,.35)" />
            <stop offset="100%" stopColor="rgba(240,180,41,0)" />
          </linearGradient>
        </defs>
        <polygon points={area} fill="url(#goldfill)" />
        <polyline points={line} fill="none" stroke="var(--gold)" strokeWidth="2" />
        <text x={pad} y={14} className="chart-label">{fmt(yMax)}</text>
        <text x={pad} y={H - 12} className="chart-label">{fmt(yMin)}</text>
      </svg>
    );
  }
  return (
    <div className="card chart-card">
      <h2>Gold (histórico)</h2>
      {body}
    </div>
  );
}
