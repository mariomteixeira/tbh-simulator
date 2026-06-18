import { gearPt } from "./grades.js";

/* Rótulos e formatação de stats/gems compartilhados entre Builds e Atributos. */

/* número cheio (sem K/M), com separador de milhar pt-BR */
export const intfmt = (n) => Math.round(n || 0).toLocaleString("pt-BR");

/* rótulos curtos de stat (p/ filtro de buff + nomes) */
export const STAT_PT = {
  AttackDamage: "Dano", AttackSpeed: "Vel. ataque", CastSpeed: "Vel. cast",
  CriticalChance: "Crítico", CriticalDamage: "Dano crít.", CooldownReduction: "Recarga",
  MaxHp: "HP", Armor: "Armadura", MovementSpeed: "Mov.", BlockChance: "Block",
  DodgeChance: "Esquiva", ElementalDodgeChance: "Esquiva elem.",
  HpRegenPerSec: "Regen", AddHpPerHit: "Cura/hit", HpLeech: "Roubo vida",
  SkillHealIncrease: "Cura", DamageAbsorption: "Absorção", DamageReduction: "Redução",
  ChaosResistance: "Resist. caos", FireResistance: "Resist. fogo",
  ColdResistance: "Resist. gelo", LightningResistance: "Resist. raio",
  PhysicalResistance: "Resist. físico", AllElementalResistance: "Resist. elem.",
  "PhysicalDamagePercent": "Dano físico", "FireDamagePercent": "Dano fogo",
  "ColdDamagePercent": "Dano gelo", "LightningDamagePercent": "Dano raio",
  "ChaosDamagePercent": "Dano caos", AreaOfEffect: "Área",
};
export const statPt = (s) => STAT_PT[s] || s;

export const SLOT_PT = {
  BOW: "Arco", ARROW: "Flecha", SWORD: "Espada", AXE: "Machado", STAFF: "Cajado",
  SCEPTER: "Cetro", ORB: "Orbe", SHIELD: "Escudo", TOME: "Tomo", BOLT: "Virote",
  CROSSBOW: "Besta", HATCHET: "Machadinha",
  HELMET: "Elmo", ARMOR: "Armadura", GLOVES: "Luvas", BOOTS: "Botas",
  AMULET: "Amuleto", EARING: "Brinco", RING: "Anel", BRACER: "Bracelete",
};
export const slotPt = (s) => SLOT_PT[s] || gearPt(s) || s;

export const CAT_OF = {
  BOW: "WEAPON", ARROW: "WEAPON", SWORD: "WEAPON", AXE: "WEAPON", STAFF: "WEAPON",
  SCEPTER: "WEAPON", ORB: "WEAPON", SHIELD: "WEAPON", TOME: "WEAPON", BOLT: "WEAPON",
  CROSSBOW: "WEAPON", HATCHET: "WEAPON",
  HELMET: "ARMOR", ARMOR: "ARMOR", GLOVES: "ARMOR", BOOTS: "ARMOR",
  AMULET: "ACCESSORY", EARING: "ACCESSORY", RING: "ACCESSORY", BRACER: "ACCESSORY",
};
export const catOf = (gt) => CAT_OF[gt] || "WEAPON";
export const catPt = (c) => (c === "WEAPON" ? "arma" : c === "ARMOR" ? "armadura" : "acessório");

const STAT_EN = {
  AttackDamage: "Attack Damage", AttackSpeed: "Attack Speed", CastSpeed: "Cast Speed",
  CriticalChance: "Critical Chance", CriticalDamage: "Critical Damage", CooldownReduction: "Cooldown Reduction",
  MaxHp: "Max HP", Armor: "Armor", MovementSpeed: "Movement Speed", BlockChance: "Block Chance",
  DodgeChance: "Dodge Chance", ElementalDodgeChance: "Elemental Dodge", HpRegenPerSec: "HP Regen",
  AddHpPerHit: "HP per Hit", HpLeech: "HP Leech", SkillHealIncrease: "Skill Heal",
  DamageAbsorption: "Damage Absorption", DamageReduction: "Damage Reduction",
  ChaosResistance: "Chaos Resistance", FireResistance: "Fire Resistance", ColdResistance: "Cold Resistance",
  LightningResistance: "Lightning Resistance", PhysicalResistance: "Physical Resistance",
  AllElementalResistance: "All Elemental Res.", AreaOfEffect: "Area of Effect",
  PhysicalDamagePercent: "Physical Damage", FireDamagePercent: "Fire Damage",
  ColdDamagePercent: "Cold Damage", LightningDamagePercent: "Lightning Damage", ChaosDamagePercent: "Chaos Damage",
};
export const engName = (s) => STAT_EN[s] || (s || "").replace(/([a-z])([A-Z])/g, "$1 $2");
const PCT10 = new Set(["CriticalChance", "CriticalDamage", "CooldownReduction", "CastSpeed",
  "BlockChance", "DodgeChance", "ElementalDodgeChance", "SkillHealIncrease", "DamageReduction"]);
/* unidade/escala por stat e mod (More/Increased = value/1000 → %, Flat = escala nativa) */
export function statUnit(stat, mod) {
  if (mod === "ADDITIVE") return { div: 10, suf: "% increased", dec: 1 };
  if (mod === "MULTIPLICATIVE") return { div: 10, suf: "% more", dec: 1 };
  if (stat === "AttackSpeed") return { div: 100, suf: "/s", dec: 2 };
  if (stat === "HpRegenPerSec") return { div: 100, suf: "/s", dec: 1 };
  if (stat === "DamageAbsorption") return { div: 10, suf: "", dec: 1 };
  if (/Resistance$/.test(stat)) return { div: 1, suf: "%", dec: 0 };
  if (/DamagePercent$/.test(stat) || PCT10.has(stat)) return { div: 10, suf: "%", dec: 1 };
  return { div: 1, suf: "", dec: 0 }; // raw: dano, HP, armadura, movimento...
}
export const nfmt = (v, u) => (u.dec ? (v / u.div).toFixed(u.dec).replace(".", ",") : Math.round(v / u.div).toLocaleString("pt-BR"));
export const statText = (stat, mod, value) => { const u = statUnit(stat, mod); return `${engName(stat)} +${nfmt(value, u)}${u.suf}`; };
export function statRange(stat, mod, mn, mx) {
  if (mn === mx) return statText(stat, mod, mn);
  const u = statUnit(stat, mod);
  return `${engName(stat)} +${nfmt(mn, u)}~${nfmt(mx, u)}${u.suf}`;
}
/* tier pode ser número (deco/engr) ou faixa [a,b] (inscrição) */
export const tierTop = (t) => (Array.isArray(t) ? (t[t.length - 1] || 0) : (t || 0));
export const tierLabel = (t) => (Array.isArray(t) ? `T${t[0]}–${t[t.length - 1]}` : `T${t}`);
export const rollAvg = (o) => Math.round(((o.min || 0) + (o.max || 0)) / 2);
