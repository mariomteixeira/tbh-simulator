import React from "react";
import { fmt, fmtDur } from "../format.js";

const ROLE_CLASS = { tank: "tank", dps: "dps", healer: "heal" };

export default function Heroes({ sim, state, rates }) {
  const unspent = {};
  for (const h of state.heroes || []) unspent[h.key] = h.unspent;
  const etas = {};
  for (const e of sim.levelEta || []) etas[e.key] = e;
  const expRates = rates?.exp_per_hour || {};

  return (
    <section className="sec">
      <h2>Time</h2>
      <div className="hero-list">
        {sim.heroes.map((h) => (
          <div className="hero" key={h.key}>
            <div className="hero-head">
              <span
                className="hero-name"
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <img
                  className="spr"
                  src={`/heroicon/${h.key}.png`}
                  alt={h.name}
                  onError={(e) => {
                    e.currentTarget.style.visibility = "hidden";
                  }}
                />
                {h.name}
                {h.role && (
                  <span className={"role " + (ROLE_CLASS[h.role] || "dps")}>
                    {h.role}
                  </span>
                )}
              </span>
              <span className="hero-level">Lv {h.level}</span>
            </div>
            <div className="hero-grid">
              <span className="kv">
                <i>dps status</i>
                <b>{fmt(h.statusDps)}</b>
              </span>
              <span className="kv">
                <i>dps efetivo</i>
                <b>{fmt(h.dps)}</b>
              </span>
              <span className="kv">
                <i>ehp</i>
                <b>{fmt(h.ehp)}</b>
              </span>
              <span className="kv">
                <i>exp/h</i>
                <b>{expRates[h.cls] ? fmt(expRates[h.cls]) : "—"}</b>
              </span>
            </div>
            <div className="hero-foot">
              {etas[h.key]?.etaSec != null && (
                <span className="muted">
                  próx. nível em ~{fmtDur(etas[h.key].etaSec)}
                </span>
              )}
              {unspent[h.key] > 0 && (
                <span className="badge-green">{unspent[h.key]} ponto(s) livre</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
