import React from "react";
import { fmt } from "../format.js";
import { fmtStatDelta } from "../statNames.js";

const GRADE_CLASS = {
  COMMON: "g-common", UNCOMMON: "g-uncommon", RARE: "g-rare",
  EPIC: "g-epic", LEGENDARY: "g-legendary", MYTHIC: "g-mythic",
};

function Item({ it }) {
  if (!it) return <span className="muted">vazio</span>;
  return (
    <span className={GRADE_CLASS[it.grade] || ""}>
      {it.name} <span className="muted">lvl {it.level}</span>
    </span>
  );
}

export function RoleTag({ role }) {
  if (!role) return null;
  const tank = role === "tank";
  return (
    <span className={"role-tag " + (tank ? "r-tank" : "r-dps")}>
      {tank ? "tank" : "dps"}
    </span>
  );
}

export default function GearPanel({ gear }) {
  const upgrades = [];
  const empties = [];
  for (const g of gear) {
    for (const s of g.slots) {
      if (s.upgrade) upgrades.push({ cls: g.cls, role: g.role, ...s });
      else if (s.empty) empties.push({ cls: g.cls, role: g.role, ...s });
    }
  }
  if (!upgrades.length && !empties.length) {
    return (
      <section className="sec">
        <h2>Gear</h2>
        <p className="muted">Nenhuma troca melhor no inventário. Tudo otimizado.</p>
      </section>
    );
  }
  upgrades.sort((a, b) => b.upgrade.dPower - a.upgrade.dPower);
  return (
    <section className="sec">
      <h2>Gear — trocas que valem</h2>
      <div className="gear-list">
        {upgrades.map((u, i) => (
          <div className="gear-row" key={i}>
            <div className="gear-slot">
              {u.cls} <RoleTag role={u.role} /> · {u.gearType.toLowerCase()}
            </div>
            <div className="gear-swap">
              <Item it={u.current} /> <span className="arrow">→</span>{" "}
              <Item it={u.upgrade} />
            </div>
            {u.upgrade.statDiff?.length > 0 && (
              <div className="gear-stats">
                {u.upgrade.statDiff.map((d, j) => (
                  <span key={j} className={"stat-chip" + (d.delta < 0 ? " neg" : "")}>
                    {fmtStatDelta(d)}
                  </span>
                ))}
              </div>
            )}
            <div className="gear-effect">
              {u.upgrade.dDps !== 0 && (
                <span className={u.upgrade.dDps > 0 ? "badge-green" : "badge-red"}>
                  {u.upgrade.dDps > 0 ? "+" : ""}{fmt(u.upgrade.dDps)} dps
                </span>
              )}
              {u.upgrade.dEhp !== 0 && (
                <span className={u.upgrade.dEhp > 0 ? "badge-green" : "badge-red"}>
                  {u.upgrade.dEhp > 0 ? "+" : ""}{fmt(u.upgrade.dEhp)} ehp
                </span>
              )}
            </div>
          </div>
        ))}
        {empties.length > 0 && (
          <div className="gear-empties">
            <b>{empties.length} slot(s) vazio(s):</b>{" "}
            <span className="muted">
              {empties.map((e) => `${e.cls} ${e.gearType.toLowerCase()}`).join(", ")}
            </span>
          </div>
        )}
        <p className="muted small">
          A troca recalcula o herói inteiro (flats × percentuais × crítico ×
          recarga, com todos os affixes) contra a fase atual. O ranking é por
          papel: <b>tank</b> (Knight, Priest) pesa mais EHP; <b>dps</b> (Ranger,
          Sorcerer, Hunter, Slayer) pesa mais dano.
        </p>
      </div>
    </section>
  );
}
