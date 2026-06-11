import { fmt } from "./format.js";

// nomes amigáveis + unidade certa de cada stat (escala /1000 ou /100 do jogo)
const sign = (d) => (d > 0 ? "+" : "−");
const abs = Math.abs;

const FMT = {
  AttackDamage: (d) => `${sign(d)}${fmt(abs(d))} dano`,
  AttackSpeed: (d) => `${sign(d)}${(abs(d) / 100).toFixed(2)} ataques/s`,
  CastSpeed: (d) => `${sign(d)}${(abs(d) / 10).toFixed(0)}% vel. de cast`,
  CriticalChance: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% crítico`,
  CriticalDamage: (d) => `${sign(d)}${(abs(d) / 10).toFixed(0)}% dano crítico`,
  CooldownReduction: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% recarga`,
  MaxHp: (d) => `${sign(d)}${fmt(abs(d))} HP`,
  Armor: (d) => `${sign(d)}${fmt(abs(d))} armadura`,
  MovementSpeed: (d) => `${sign(d)}${fmt(abs(d))} mov.`,
  BlockChance: (d) => `${sign(d)}${(abs(d) / 10).toFixed(1)}% block`,
  HpRegenPerSec: (d) => `${sign(d)}${fmt(abs(d))} regen/s`,
};

const ELEM_PT = {
  Fire: "fogo", Cold: "gelo", Lightning: "raio",
  Chaos: "caos", Physical: "físico",
};

export function elemPt(el) {
  return ELEM_PT[el] || el;
}

export function fmtStatDelta({ stat, delta }) {
  if (FMT[stat]) return FMT[stat](delta);
  const m = stat.match(/^(Fire|Cold|Lightning|Chaos|Physical)DamagePercent$/);
  if (m) return `${sign(delta)}${(abs(delta) / 10).toFixed(0)}% dano de ${ELEM_PT[m[1]]}`;
  if (stat.endsWith("Percent") || stat.startsWith("Increase"))
    return `${sign(delta)}${(abs(delta) / 10).toFixed(1)}% ${stat
      .replace(/Percent$/, "")
      .replace(/^Increase/, "")}`;
  return `${sign(delta)}${fmt(abs(delta))} ${stat}`;
}
