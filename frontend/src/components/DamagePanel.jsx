import React from "react";
import { fmt } from "../format.js";
import { elemPt } from "../statNames.js";
import { RoleTag } from "./GearPanel.jsx";

const ELEM_CLASS = { Fire: "e-fire", Cold: "e-cold", Lightning: "e-light", Chaos: "e-chaos", Physical: "e-phys" };

function Elem({ el }) {
  return <span className={"elem " + (ELEM_CLASS[el] || "e-phys")}>{elemPt(el)}</span>;
}

export default function DamagePanel({ heroes }) {
  return (
    <section className="sec">
      <h2>Dano real — por skill</h2>
      <div className="dmg-grid">
        {heroes.map((h) => {
          const a = h.damage?.auto;
          const skills = h.damage?.skills || [];
          const buffs = h.damage?.buffs || [];
          const utility = h.damage?.utility || [];
          return (
            <div className="dmg-hero" key={h.key}>
              <div className="dmg-head">
                <b>{h.name}</b> <RoleTag role={h.role} />
                <span className="dmg-total">
                  {fmt(h.dps)} dps efetivo
                  {h.buffDps > 0 && (
                    <span className="muted"> · ~{fmt(h.dpsBuffed)} c/ buffs</span>
                  )}
                </span>
              </div>
              {a && (
                <div className="dmg-row">
                  <span>
                    Ataque básico <Elem el={a.element} />
                  </span>
                  <span className="dmg-calc">
                    {fmt(a.statusDps)} status
                    {a.bonusMult > 1.001 && (
                      <> × <b>{a.bonusMult.toFixed(2)}</b> bônus</>
                    )}{" "}
                    = <b>{fmt(a.dps)}/s</b>
                  </span>
                </div>
              )}
              {skills.map((s) => (
                <div className="dmg-row" key={s.key}>
                  <span>
                    {s.name} <span className="muted">lv {s.level}</span>{" "}
                    <Elem el={s.element} />
                  </span>
                  <span className="dmg-calc">
                    {fmt(s.perCast)} por uso ·{" "}
                    {s.everyAttacks != null
                      ? `a cada ${s.everyAttacks} ataques`
                      : `recarga ${s.cooldown}s`}{" "}
                    = <b>{fmt(s.dps)}/s</b>
                  </span>
                </div>
              ))}
              {buffs.map((b) => (
                <div className="dmg-row dmg-buff" key={"b" + b.key}>
                  <span>
                    {b.name} <span className="muted">lv {b.level}</span>{" "}
                    <span className="buff-tag">buff</span>
                  </span>
                  <span className="dmg-calc">
                    +{b.pct}% {b.stat} · recarga {b.cooldown}s
                    {b.affectsDps && b.dpsActive != null && (
                      <> · ativo <b>{fmt(b.dpsActive)}/s</b></>
                    )}
                    {b.dpsAvg != null && (
                      <>
                        {" "}
                        · <b className="v-exp">+{fmt(b.dpsAvg)}/s</b>{" "}
                        <span className="muted">
                          méd. (~{b.uptime}%, dura {b.durEst}s)
                        </span>
                      </>
                    )}
                  </span>
                </div>
              ))}
              {utility.map((u) => (
                <div className="dmg-row dmg-util" key={"u" + u.key}>
                  <span>
                    {u.name} <span className="muted">lv {u.level}</span>{" "}
                    <span className="util-tag">{u.kind}</span>
                  </span>
                  <span className="dmg-calc muted">
                    utilidade · recarga {u.cooldown}s · não dá dano
                  </span>
                </div>
              ))}
              {skills.length === 0 && buffs.length === 0 && utility.length === 0 && (
                <div className="dmg-row muted">sem skills de recarga equipadas</div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
