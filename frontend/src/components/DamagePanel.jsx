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
        elemental. Aqui está o dano que sai de verdade.
      </p>
      <div className="dmg-grid">
        {heroes.map((h) => {
          const a = h.damage?.auto;
          const skills = h.damage?.skills || [];
          return (
            <div className="dmg-hero" key={h.key}>
              <div className="dmg-head">
                <b>{h.name}</b>
                <span className="dmg-total">{fmt(h.dps)} dps efetivo</span>
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
              {skills.length === 0 && (
                <div className="dmg-row muted">sem skills de recarga equipadas</div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
