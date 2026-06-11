import React from "react";

const COLORS = ["#4f9cf0", "#9d7bf0", "#45c486", "#e0a560", "#e06060", "#5bc8d6"];

export default function ProjectionChart({ projection }) {
  const W = 600, H = 150, pad = 26;
  const maxH = 24;

  let yMin = Infinity, yMax = -Infinity;
  for (const p of projection)
    for (const [, lvl] of p.series) {
      yMin = Math.min(yMin, lvl);
      yMax = Math.max(yMax, lvl);
    }
  if (!isFinite(yMin)) return null;
  yMin = Math.floor(yMin);
  yMax = Math.ceil(yMax) + 1;

  const sx = (h) => (Math.min(h, maxH) / maxH) * (W - pad - 8) + pad;
  const sy = (l) => H - 18 - ((l - yMin) / (yMax - yMin || 1)) * (H - 30);

  return (
    <div className="card chart-card">
      <h2>Projeção de nível (24h no ritmo atual)</h2>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="chart">
        {[0, 4, 8, 16, 24].map((h) => (
          <g key={h}>
            <line x1={sx(h)} y1={10} x2={sx(h)} y2={H - 18} className="gridline" />
            <text x={sx(h)} y={H - 5} className="chart-label" textAnchor="middle">
              {h}h
            </text>
          </g>
        ))}
        {[yMin, yMax].map((l) => (
          <text key={l} x={2} y={sy(l) + 4} className="chart-label">
            {l}
          </text>
        ))}
        {projection.map((p, i) => {
          const series = [...p.series];
          const last = series[series.length - 1];
          if (last && last[0] < maxH) series.push([maxH, last[1]]);
          const line = series
            .filter(([t]) => t <= maxH)
            .map(([t, l]) => `${sx(t).toFixed(1)},${sy(l).toFixed(1)}`)
            .join(" ");
          return (
            <polyline
              key={p.key}
              points={line}
              fill="none"
              stroke={COLORS[i % COLORS.length]}
              strokeWidth="2"
            />
          );
        })}
      </svg>
      <div className="legend">
        {projection.map((p, i) => (
          <span key={p.key}>
            <i style={{ background: COLORS[i % COLORS.length] }} /> {p.name}
            {p.horizons["24"] ? ` → lv ${Math.floor(p.horizons["24"])}` : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
