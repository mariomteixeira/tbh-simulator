import React from "react";
import { fmt, fmtDur } from "../format.js";
import { elemPt } from "../statNames.js";

const VERDICT = {
  passa: { label: "passa", cls: "v-pass" },
  apertado: { label: "apertado", cls: "v-tight" },
  arriscado: { label: "arriscado", cls: "v-risk" },
};

export default function CombatPanel({ combat }) {
  if (!combat || combat.length === 0) return null;
  return (
    <section className="sec">
      <h2>Combate por fase</h2>
      <p className="muted small">
        Sua fase atual e as próximas que você ainda não passa, com o veredito e o
        que falta.
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
                      {c.bottleneck === "defesa" &&
                        c.threat &&
                        c.threat !== "Physical" && (
                          <> (resist {elemPt(c.threat)})</>
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
                    {c.weakestHero}: {c.hitsToDie ?? "—"} golpe(s) de{" "}
                    {c.threat ? elemPt(c.threat) : "—"}
                  </b>
                </span>
                <span>
                  <i>dano da fase</i>
                  <b>
                    {(c.elements || []).map((e) => elemPt(e)).join(", ") || "Físico"}
                  </b>
                </span>
              </div>
              {c.needResist && (
                <div className="combat-fix">
                  <b>+{c.needResist.points}</b> resist {elemPt(c.needResist.element)} no{" "}
                  {c.weakestHero} → aguenta {c.needResist.hits} golpes
                  {c.needResist.capped && (
                    <span className="muted">
                      {" "}
                      (no teto {c.needResist.resTarget}% — ainda precisa de HP/redução de dano)
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
