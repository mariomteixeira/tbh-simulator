import React, { useMemo } from "react";
import { fmt, fmtDur } from "../format.js";
import { useT } from "../i18n.jsx";

export default function BoxPanel({ farm, rates }) {
  const t = useT();
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
      <h2>{t("Chests — drop route", "Baús — rota de drop")}</h2>

      <div className="box-measured">
        <div className="bm">
          <i>{t("chance bonus · normal", "bônus chance · normal")}</i>
          <b className="v-gold">+{bonus.normal}%</b>
        </div>
        <div className="bm">
          <i>{t("chance bonus · boss", "bônus chance · boss")}</i>
          <b className="v-gold">+{bonus.boss}%</b>
        </div>
        <div className="bm">
          <i>{t("normal chests/h (measured)", "baús normais/h (medido)")}</i>
          <b>{chests.normal != null ? chests.normal.toFixed(1) : "—"}</b>
        </div>
        <div className="bm">
          <i>{t("boss chests/h (measured)", "baús de boss/h (medido)")}</i>
          <b>{chests.boss != null ? chests.boss.toFixed(1) : "—"}</b>
        </div>
      </div>

      <table className="mini wide" style={{ marginTop: 10 }}>
        <thead>
          <tr>
            <th>{t("stage", "fase")}</th>
            <th>{t("clear", "clear")}</th>
            <th>{t("boss chest (blue)", "bau do boss (azul)")}</th>
            <th>{t("chance/run", "chance/run")}</th>
            <th>{t("normal chest", "bau normal")}</th>
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
