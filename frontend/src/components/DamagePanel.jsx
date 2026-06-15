import React from "react";
import { fmt } from "../format.js";
import { elemPt } from "../statNames.js";

const ELEM_CLASS = { Fire: "e-fire", Cold: "e-cold", Lightning: "e-light", Chaos: "e-chaos", Physical: "e-phys" };

function Elem({ el }) {
  return <span className={"elem " + (ELEM_CLASS[el] || "e-phys")}>{elemPt(el)}</span>;
}

export default function DamagePanel({ heroes }) {
  return (
    <section className="sec">
      <h2>Dano real — por skill</h2>
      <p className="muted small dmg-note">
        O painel de Status do jogo mostra só o ataque básico, sem bônus
        elemental. Aqui está o dano que sai de verdade. Skills de <b>buff</b> (ex.:
        Surto Veloz) não dão dano — elas aceleram o ataque básico.
      </p>
      <div className="dmg-grid">
        {heroes.map((h) => {
          const a = h.damage?.auto;
          const skills = h.damage?.skills || [];
          const buffs = h.damage?.buffs || [];
          return (
            <div className="dmg-hero" key={h.key}>
              <div className="dmg-head">
                <b>{h.name}</b>
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
                    {fmt(s.perCast)} por uso · recarga {s.cooldown}s ={" "}
                    <b>{fmt(s.dps)}/s</b>
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
              {skills.length === 0 && buffs.length === 0 && (
                <div className="dmg-row muted">sem skills de recarga equipadas</div>
              )}
            </div>
          );
        })}
      </div>
      {heroes.some((h) => (h.damage?.buffs || []).some((b) => b.durEst != null)) && (
        <p className="muted small dmg-note" style={{ marginTop: 10 }}>
          Duração do buff vem de Param1⁄100 (confirmado in-game na Surto Veloz: 7s). O
          valor <b>ativo</b> é exato; a <b>média</b> usa o uptime = duração⁄recarga.
        </p>
      )}
    </section>
  );
}
