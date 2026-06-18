import React from "react";
import { fmt } from "../format.js";
import { elemPt } from "../statNames.js";
import { RoleTag } from "./GearPanel.jsx";
import { useT } from "../i18n.jsx";

const ELEM_CLASS = { Fire: "e-fire", Cold: "e-cold", Lightning: "e-light", Chaos: "e-chaos", Physical: "e-phys" };

function Elem({ el }) {
  return <span className={"elem " + (ELEM_CLASS[el] || "e-phys")}>{elemPt(el)}</span>;
}

export default function DamagePanel({ heroes }) {
  const t = useT();
  return (
    <section className="sec">
      <h2>{t("Real damage — per skill", "Dano real — por skill")}</h2>
      <div className="dmg-grid">
        {heroes.map((h) => {
          const a = h.damage?.auto;
          const skills = h.damage?.skills || [];
          const buffs = h.damage?.buffs || [];
          const utility = h.damage?.utility || [];
          return (
            <div className="dmg-hero" key={h.key}>
              <div className="dmg-head">
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <img
                    className="spr"
                    src={`/heroicon/${h.key}.png`}
                    alt={h.name}
                    onError={(e) => {
                      e.currentTarget.style.visibility = "hidden";
                    }}
                  />
                  <b>{h.name}</b> <RoleTag role={h.role} />
                </span>
                <span className="dmg-total">
                  {fmt(h.dps)} DPS
                  {h.buffDps > 0 && (
                    <span className="muted"> · ~{fmt(h.dpsBuffed)} {t("w/ buffs", "c/ buffs")}</span>
                  )}
                  {h.ehp != null && (
                    <span className="muted"> · {fmt(h.ehp)} EHP</span>
                  )}
                </span>
              </div>
              {a && (
                <div className="dmg-row">
                  <span>
                    {t("Basic attack", "Ataque básico")} <Elem el={a.element} />
                  </span>
                  <span className="dmg-calc">
                    {fmt(a.statusDps)} {t("status", "status")}
                    {a.bonusMult > 1.001 && (
                      <> × <b>{a.bonusMult.toFixed(2)}</b> {t("bonus", "bônus")}</>
                    )}{" "}
                    = <b>{fmt(a.dps)}/s</b>
                  </span>
                </div>
              )}
              {skills.map((s) => (
                <div className="dmg-row" key={s.key}>
                  <span>
                    {s.name} <span className="muted">{t("lv", "lv")} {s.level}</span>{" "}
                    <Elem el={s.element} />
                  </span>
                  <span className="dmg-calc">
                    {fmt(s.perCast)} {t("per use", "por uso")} ·{" "}
                    {s.everyAttacks != null
                      ? t(`every ${s.everyAttacks} attacks`, `a cada ${s.everyAttacks} ataques`)
                      : t(`cooldown ${s.cooldown}s`, `recarga ${s.cooldown}s`)}{" "}
                    = <b>{fmt(s.dps)}/s</b>
                  </span>
                </div>
              ))}
              {buffs.map((b) => (
                <div className="dmg-row dmg-buff" key={"b" + b.key}>
                  <span>
                    {b.name} <span className="muted">{t("lv", "lv")} {b.level}</span>{" "}
                    <span className="buff-tag">buff</span>
                  </span>
                  <span className="dmg-calc">
                    +{b.pct}% {b.stat} · {t("cooldown", "recarga")} {b.cooldown}s
                    {b.affectsDps && b.dpsActive != null && (
                      <> · {t("active", "ativo")} <b>{fmt(b.dpsActive)}/s</b></>
                    )}
                    {b.dpsAvg != null && (
                      <>
                        {" "}
                        · <b className="v-exp">+{fmt(b.dpsAvg)}/s</b>{" "}
                        <span className="muted">
                          {t("avg.", "méd.")} (~{b.uptime}%, {t("lasts", "dura")} {b.durEst}s)
                        </span>
                      </>
                    )}
                  </span>
                </div>
              ))}
              {utility.map((u) => (
                <div className="dmg-row dmg-util" key={"u" + u.key}>
                  <span>
                    {u.name} <span className="muted">{t("lv", "lv")} {u.level}</span>{" "}
                    <span className="util-tag">{u.kind}</span>
                  </span>
                  <span className="dmg-calc">
                    {u.healAmount != null ? (
                      <>
                        {t("heals", "cura")} <b className="v-exp">{fmt(u.healAmount)} {t("of health", "de vida")}</b>{" "}
                        <span className="muted">
                          ({u.healPct}% {t("max HP", "HP máx")}
                          {u.healBonus ? t(` · +${u.healBonus}% heal`, ` · +${u.healBonus}% cura`) : ""}) · {t("every", "a cada")}{" "}
                          {u.cooldown}s
                        </span>
                      </>
                    ) : (
                      <span className="muted">{t("utility", "utilidade")} · {t("cooldown", "recarga")} {u.cooldown}s</span>
                    )}
                  </span>
                </div>
              ))}
              {skills.length === 0 && buffs.length === 0 && utility.length === 0 && (
                <div className="dmg-row muted">{t("no cooldown skills equipped", "sem skills de recarga equipadas")}</div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
