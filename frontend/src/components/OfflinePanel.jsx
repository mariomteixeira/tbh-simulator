import React from "react";
import { fmt } from "../format.js";

export default function OfflinePanel({ offline }) {
  if (!offline.unlocked) {
    return (
      <div className="card">
        <h2>Offline</h2>
        <p className="muted">Recompensa offline ainda não desbloqueada (runa).</p>
      </div>
    );
  }
  const { park, current } = offline;
  return (
    <div className="card">
      <h2>Offline (cap {offline.capHours}h)</h2>
      {park && (
        <div className="park">
          <div className="park-label">estacione em</div>
          <div className="park-stage">
            <span className={"diff-tag t-" + park.tag}>{park.tag}</span>{" "}
            <b>{park.label}</b> {park.name}
          </div>
          <div className="park-yield">
            <span className="v-gold">{fmt(park.gold)} gold</span> ·{" "}
            <span className="v-exp">{fmt(park.exp)} exp</span> em 8h
          </div>
        </div>
      )}
      {current && (
        <p className="muted small">
          na fase atual: {fmt(current.gold)} gold / {fmt(current.exp)} exp · bônus de
          runas: +{offline.goldBonusPct}% gold, +{offline.expBonusPct}% exp
        </p>
      )}
    </div>
  );
}
