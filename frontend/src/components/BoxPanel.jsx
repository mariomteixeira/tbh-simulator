import React, { useMemo } from "react";
import { fmt, fmtDur } from "../format.js";

export default function BoxPanel({ farm, rates }) {
  const bonus = farm.dropBonus || { normal: 0, boss: 0 };
  const chests = rates?.chests_per_hour || {};

  // fases que voce LIMPA, ranqueadas por nivel do bau (clear rapido desempata)
  const rows = useMemo(
    () =>
      (farm.rows || [])
        .filter((r) => r.cleared && r.type !== "ACTBOSS" && r.bossBoxLvl > 0)
        .sort(
          (a, b) =>
            b.bossBoxLvl - a.bossBoxLvl || a.clearTime - b.clearTime
        )
        .slice(0, 10),
    [farm]
  );

  return (
    <section className="sec">
      <h2>Baús — rota de drop</h2>

      <div className="box-measured">
        <div className="bm">
          <i>bônus chance · normal</i>
          <b className="v-gold">+{bonus.normal}%</b>
        </div>
        <div className="bm">
          <i>bônus chance · boss</i>
          <b className="v-gold">+{bonus.boss}%</b>
        </div>
        <div className="bm">
          <i>baús normais/h (medido)</i>
          <b>{chests.normal != null ? chests.normal.toFixed(1) : "—"}</b>
        </div>
        <div className="bm">
          <i>baús de boss/h (medido)</i>
          <b>{chests.boss != null ? chests.boss.toFixed(1) : "—"}</b>
        </div>
      </div>

      <table className="mini wide" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th>fase</th>
            <th>clear</th>
            <th>bau do boss (azul)</th>
            <th>chance/run</th>
            <th>bau normal</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.current ? "is-current" : ""}>
              <td>
                {r.tag} {r.label}
              </td>
              <td>{fmtDur(r.clearTime)}</td>
              <td className="muted">{r.bossBox}</td>
              <td>
                {r.bossBoxPerClear != null
                  ? Math.round(Math.min(r.bossBoxPerClear, 1) * 100) + "%"
                  : "—"}
              </td>
              <td className="muted">{r.normalBox}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
