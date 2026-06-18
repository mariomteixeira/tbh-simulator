import React from "react";
import { fmt, fmtDur } from "../format.js";
import { elemPt } from "../statNames.js";

const VERDICT = {
  passa: { label: "passa", cls: "v-pass" },
  apertado: { label: "apertado", cls: "v-tight" },
  arriscado: { label: "arriscado", cls: "v-risk" },
};

/* número cheio (sem K/M) — golpe e dano tomado precisam ser exatos */
const full = (n) => Math.round(n || 0).toLocaleString("pt-BR");

export default function CombatPanel({ combat }) {
  if (!combat || combat.length === 0) return null;
  return (
    <section className="sec">
      <h2>Combate por fase</h2>
      <p className="muted small">
        Sua fase atual e as próximas que você ainda não passa, com o veredito e o
        que falta. O golpe é o maior daquele elemento; "toma" é o dano por golpe
        já depois de armadura/resistência, redução e absorção.
      </p>
      <div className="combat-list">
        {combat.map((c) => {
          const v = VERDICT[c.verdict] || VERDICT.passa;
          return (
            <div className={"combat-row " + v.cls} key={c.key}>
              <div className="combat-head">
                <span className="combat-stage">
                  <span className={"diff-tag t-" + c.tag}>{c.tag}</span>{" "}
                  <b>{c.label}</b> {c.name}{" "}
                  <span className="muted">Lv{c.lvl}</span>
                  {c.current && <span className="combat-cur">atual</span>}
                </span>
                <span className="combat-verdict">
                  <span className={"verdict-badge " + v.cls}>{v.label}</span>
                  {c.bottleneck && (
                    <span className="combat-gap">
                      falta {c.bottleneck}
                      {c.bottleneck === "defesa" && c.threat && (
                        c.threat === "Physical"
                          ? <> (armadura)</>
                          : <> (resist {elemPt(c.threat)})</>
                      )}
                    </span>
                  )}
                </span>
              </div>
              <div className="combat-stats">
                <span>
                  <i>dano do time</i>
                  <b>{fmt(c.partyDps)}/s · clear {fmtDur(c.clearTime)}</b>
                </span>
                <span>
                  <i>frente mais frágil</i>
                  <b>
                    {c.weakestHero}
                    {c.weakestHp ? <span className="muted"> · HP {full(c.weakestHp)}</span> : null}
                  </b>
                </span>
              </div>

              {c.byElement && c.byElement.length > 0 && (
                <div className="combat-bd">
                  {c.byElement.map((e) => (
                    <div
                      className={"bd-row" + (e.element === c.threat ? " bd-threat" : "")}
                      key={e.element}
                    >
                      <span className="bd-el">{elemPt(e.element)}</span>
                      <span className="bd-cell">golpe <b>{full(e.rawHit)}</b></span>
                      <span className="bd-arrow">→</span>
                      <span className="bd-cell">toma <b>{full(e.taken)}</b>/golpe</span>
                      <span className="bd-arrow">→</span>
                      <span className="bd-cell bd-hits">
                        <b>{e.hits ?? "—"}</b> golpe{e.hits === 1 ? "" : "s"}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {c.needResist && (
                <div className="combat-fix">
                  <b>+{c.needResist.points}</b> resist {elemPt(c.needResist.element)} no{" "}
                  {c.weakestHero} → aguenta {c.needResist.hits} golpes
                  {c.needResist.capped && (
                    <span className="muted">
                      {" "}(no teto {c.needResist.resTarget}% — ainda precisa de HP/redução de dano)
                    </span>
                  )}
                </div>
              )}
              {c.needArmor && (
                <div className="combat-fix">
                  <b>+{full(c.needArmor.points)}</b> de armadura no {c.weakestHero}
                  {" "}({full(c.needArmor.armorNow)} → {full(c.needArmor.armorTarget)})
                  {c.needArmor.capped
                    ? <span className="muted"> — no teto de mitigação (75%) ainda não chega a {c.needArmor.hits} golpes; precisa de HP/redução de dano também</span>
                    : <> → aguenta {c.needArmor.hits} golpes</>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
