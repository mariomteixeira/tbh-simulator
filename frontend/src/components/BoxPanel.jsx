import React, { useMemo } from "react";
import { fmt, fmtDur } from "../format.js";

export default function BoxPanel({ farm }) {
  const bonus = farm.dropBonus || { normal: 0, boss: 0 };
  const bb = farm.bestBossBox;
  const bn = farm.bestNormalBox;

  // fases que voce LIMPA, ranqueadas por nivel do bau e depois bau azul/h
  const rows = useMemo(
    () =>
      (farm.rows || [])
        .filter((r) => r.cleared && r.type !== "ACTBOSS" && r.bossBoxPerHour > 0)
        .sort(
          (a, b) =>
            b.bossBoxLvl - a.bossBoxLvl || b.bossBoxPerHour - a.bossBoxPerHour
        )
        .slice(0, 10),
    [farm]
  );

  return (
    <div className="card">
      <h2>Baús — rota de drop</h2>
      <p className="muted small">
        Taxa por kill (datada na wiki): bau normal <b>16%</b>/kill, bau do boss
        (azul) <b>15%</b>/boss. Com seus bônus: <b>+{bonus.normal}%</b> normal ·{" "}
        <b>+{bonus.boss}%</b> boss. “1 a cada” = tempo médio até cair
        (probabilístico, não timer fixo).
      </p>

      {bb && (
        <div className="kv-big" style={{ marginTop: 8 }}>
          <i>melhor rota — bau do boss (azul)</i>
          <b>
            {bb.tag} {bb.label} · {bb.bossBox}
            <br />
            {bb.bossBoxPerHour.toFixed(1)}/h{" "}
            <span className="muted">
              (1 a cada {fmtDur(bb.secsPerBossBox)})
            </span>
          </b>
        </div>
      )}
      {bn && (
        <div className="kv-big" style={{ marginTop: 8 }}>
          <i>melhor rota — bau normal</i>
          <b>
            {bn.tag} {bn.label} · {bn.normalBox} · {fmt(bn.normalBoxPerHour)}/h
          </b>
        </div>
      )}

      <table className="mini wide" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th>fase</th>
            <th>bau (azul)</th>
            <th>azul/h</th>
            <th>1 a cada</th>
            <th>normal/h</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.current ? "is-current" : ""}>
              <td>
                {r.tag} {r.label}
              </td>
              <td className="muted">{r.bossBox}</td>
              <td>{r.bossBoxPerHour.toFixed(1)}</td>
              <td>{r.secsPerBossBox ? fmtDur(r.secsPerBossBox) : "—"}</td>
              <td>{fmt(r.normalBoxPerHour)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="muted small" style={{ marginTop: 8 }}>
        Taxas da wiki (datadas). Melhor mapa = bau de <b>nível mais alto</b>
        (gear melhor) e, entre os de mesmo nível, o de <b>clear mais rápido</b>
        (mais baús/h).
      </p>
    </div>
  );
}
