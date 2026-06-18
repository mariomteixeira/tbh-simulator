import React from "react";
import { fmt, fmtDur } from "../format.js";
import { elemPt } from "../statNames.js";
import { useT } from "../i18n.jsx";

const VERDICT = {
  passa: { en: "pass", label: "passa", cls: "v-pass" },
  apertado: { en: "tight", label: "apertado", cls: "v-tight" },
  arriscado: { en: "risky", label: "arriscado", cls: "v-risk" },
};

/* número cheio (sem K/M) — golpe e dano tomado precisam ser exatos */
const full = (n) => Math.round(n || 0).toLocaleString("pt-BR");

export default function CombatPanel({ combat }) {
  const t = useT();
  if (!combat || combat.length === 0) return null;
  return (
    <section className="sec">
      <h2>{t("Combat by stage", "Combate por fase")}</h2>
      <p className="muted small">
        {t(
          'Your current stage and the next ones you can\'t clear yet, with the verdict and what\'s missing. The hit is the biggest of that element; "takes" is the damage per hit after armor/resistance, reduction and absorption.',
          'Sua fase atual e as próximas que você ainda não passa, com o veredito e o que falta. O golpe é o maior daquele elemento; "toma" é o dano por golpe já depois de armadura/resistência, redução e absorção.'
        )}
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
                  {c.current && <span className="combat-cur">{t("current", "atual")}</span>}
                </span>
                <span className="combat-verdict">
                  <span className={"verdict-badge " + v.cls}>{t(v.en, v.label)}</span>
                  {c.bottleneck && (
                    <span className="combat-gap">
                      {t("missing", "falta")} {c.bottleneck}
                      {c.bottleneck === "defesa" && c.threat && (
                        c.threat === "Physical"
                          ? <> {t("(armor)", "(armadura)")}</>
                          : <> {t("(resist", "(resist")} {elemPt(c.threat)})</>
                      )}
                    </span>
                  )}
                </span>
              </div>
              <div className="combat-stats">
                <span>
                  <i>{t("team damage", "dano do time")}</i>
                  <b>{fmt(c.partyDps)}/s · clear {fmtDur(c.clearTime)}</b>
                </span>
                <span>
                  <i>{t("frailest front line", "frente mais frágil")}</i>
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
                      <span className="bd-cell">{t("hit", "golpe")} <b>{full(e.rawHit)}</b></span>
                      <span className="bd-arrow">→</span>
                      <span className="bd-cell">{t("takes", "toma")} <b>{full(e.taken)}</b>/{t("hit", "golpe")}</span>
                      <span className="bd-arrow">→</span>
                      <span className="bd-cell bd-hits">
                        <b>{e.hits ?? "—"}</b> {t("hit", "golpe")}{e.hits === 1 ? "" : t("s", "s")}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {c.needResist && (
                <div className="combat-fix">
                  <b>+{c.needResist.points}</b> {t("resist", "resist")} {elemPt(c.needResist.element)} {t("on", "no")}{" "}
                  {c.weakestHero} → {t("survives", "aguenta")} {c.needResist.hits} {t("hits", "golpes")}
                  {c.needResist.capped && (
                    <span className="muted">
                      {" "}({t("at the cap", "no teto")} {c.needResist.resTarget}% — {t("still needs HP/damage reduction", "ainda precisa de HP/redução de dano")})
                    </span>
                  )}
                </div>
              )}
              {c.needArmor && (
                <div className="combat-fix">
                  <b>+{full(c.needArmor.points)}</b> {t("of armor on", "de armadura no")} {c.weakestHero}
                  {" "}({full(c.needArmor.armorNow)} → {full(c.needArmor.armorTarget)})
                  {c.needArmor.capped
                    ? <span className="muted"> {t(`— at the mitigation cap (75%) still doesn't reach ${c.needArmor.hits} hits; also needs HP/damage reduction`, `— no teto de mitigação (75%) ainda não chega a ${c.needArmor.hits} golpes; precisa de HP/redução de dano também`)}</span>
                    : <> → {t("survives", "aguenta")} {c.needArmor.hits} {t("hits", "golpes")}</>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
