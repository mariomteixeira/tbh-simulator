import React from "react";
import { fmt } from "../format.js";
import { useT } from "../i18n.jsx";

export default function OfflinePanel({ offline }) {
  const t = useT();
  if (!offline.unlocked) {
    return (
      <section className="sec">
        <h2>Offline</h2>
        <p className="muted">{t("Offline reward not yet unlocked (rune).", "Recompensa offline ainda não desbloqueada (runa).")}</p>
      </section>
    );
  }
  const { park, current } = offline;
  return (
    <section className="sec">
      <h2>{t("Offline", "Offline")} (cap {offline.capHours}h)</h2>
      {park && (
        <div className="park">
          <div className="park-label">{t("park at", "estacione em")}</div>
          <div className="park-stage">
            <span className={"diff-tag t-" + park.tag}>{park.tag}</span>{" "}
            <b>{park.label}</b> {park.name}
          </div>
          <div className="park-yield">
            <span className="v-gold">{fmt(park.gold)} gold</span> ·{" "}
            <span className="v-exp">{fmt(park.exp)} exp</span> {t("in 8h", "em 8h")}
          </div>
        </div>
      )}
      {current && (
        <p className="muted small">
          {t("at current stage:", "na fase atual:")} {fmt(current.gold)} gold / {fmt(current.exp)} exp · {t("rune bonus:", "bônus de runas:")} +{offline.goldBonusPct}% gold, +{offline.expBonusPct}% exp
        </p>
      )}
    </section>
  );
}
