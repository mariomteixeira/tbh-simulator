import { gearPt } from "./grades.js";
import { tr } from "./i18n.jsx";

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
  // rótulos curtos derivados do stat_strings.json oficial (pt-BR)
  AddAllSkillLevel: "Nível skills", AddHpPerKill: "Cura/kill",
  BaseAttackCountReduction: "Red. ataque bás.", IncreaseAreaOfEffectDamage: "Dano em área",
  IncreaseExpAmount: "EXP", IncreaseMeleeDamage: "Dano corpo a corpo",
  IncreaseProjectileDamage: "Dano projétil", IncreaseSummonDamage: "Dano invocação",
  Multistrike: "Multigolpe", ProjectileCount: "Qtd. projéteis",
  SkillDurationIncrease: "Duração skill", SkillRangeExpansion: "Alcance skill",
};
/* rótulos curtos em inglês (espelho do STAT_PT) p/ o idioma EN */
export const STAT_EN_SHORT = {
  AttackDamage: "Damage", AttackSpeed: "Atk Speed", CastSpeed: "Cast Speed",
  CriticalChance: "Crit", CriticalDamage: "Crit Dmg", CooldownReduction: "Cooldown",
  MaxHp: "HP", Armor: "Armor", MovementSpeed: "Move", BlockChance: "Block",
  DodgeChance: "Dodge", ElementalDodgeChance: "Elem Dodge",
  HpRegenPerSec: "Regen", AddHpPerHit: "HP/hit", HpLeech: "Leech",
  SkillHealIncrease: "Heal", DamageAbsorption: "Absorb", DamageReduction: "Reduction",
  ChaosResistance: "Chaos Res", FireResistance: "Fire Res",
  ColdResistance: "Cold Res", LightningResistance: "Light Res",
  PhysicalResistance: "Phys Res", AllElementalResistance: "Elem Res",
  PhysicalDamagePercent: "Phys Dmg", FireDamagePercent: "Fire Dmg",
  ColdDamagePercent: "Cold Dmg", LightningDamagePercent: "Light Dmg",
  ChaosDamagePercent: "Chaos Dmg", AreaOfEffect: "Area",
  AddAllSkillLevel: "Skill Lvl", AddHpPerKill: "HP/kill",
  BaseAttackCountReduction: "Atk Req −", IncreaseAreaOfEffectDamage: "AoE Dmg",
  IncreaseExpAmount: "EXP", IncreaseMeleeDamage: "Melee Dmg",
  IncreaseProjectileDamage: "Proj Dmg", IncreaseSummonDamage: "Summon Dmg",
  Multistrike: "Multistrike", ProjectileCount: "Proj Count",
  SkillDurationIncrease: "Skill Dur", SkillRangeExpansion: "Skill Range",
};
/* statPt: nome do idioma atual (EN padrão / PT) — sem precisar de hook */
export const statPt = (s) => tr(STAT_EN_SHORT[s] || s, STAT_PT[s] || s);

export const SLOT_PT = {
  BOW: "Arco", ARROW: "Flecha", SWORD: "Espada", AXE: "Machado", STAFF: "Cajado",
  SCEPTER: "Cetro", ORB: "Orbe", SHIELD: "Escudo", TOME: "Tomo", BOLT: "Virote",
  CROSSBOW: "Besta", HATCHET: "Machadinha",
  HELMET: "Elmo", ARMOR: "Armadura", GLOVES: "Luvas", BOOTS: "Botas",
  AMULET: "Amuleto", EARING: "Brinco", RING: "Anel", BRACER: "Bracelete",
};
export const SLOT_EN = {
  BOW: "Bow", ARROW: "Arrow", SWORD: "Sword", AXE: "Axe", STAFF: "Staff",
  SCEPTER: "Scepter", ORB: "Orb", SHIELD: "Shield", TOME: "Tome", BOLT: "Bolt",
  CROSSBOW: "Crossbow", HATCHET: "Hatchet",
  HELMET: "Helmet", ARMOR: "Armor", GLOVES: "Gloves", BOOTS: "Boots",
  AMULET: "Amulet", EARING: "Earring", RING: "Ring", BRACER: "Bracer",
};
export const slotPt = (s) => tr(SLOT_EN[s] || s, SLOT_PT[s] || gearPt(s) || s);

export const CAT_OF = {
  BOW: "WEAPON", ARROW: "WEAPON", SWORD: "WEAPON", AXE: "WEAPON", STAFF: "WEAPON",
  SCEPTER: "WEAPON", ORB: "WEAPON", SHIELD: "WEAPON", TOME: "WEAPON", BOLT: "WEAPON",
  CROSSBOW: "WEAPON", HATCHET: "WEAPON",
  HELMET: "ARMOR", ARMOR: "ARMOR", GLOVES: "ARMOR", BOOTS: "ARMOR",
  AMULET: "ACCESSORY", EARING: "ACCESSORY", RING: "ACCESSORY", BRACER: "ACCESSORY",
};
export const catOf = (gt) => CAT_OF[gt] || "WEAPON";
export const catPt = (c) => (c === "WEAPON" ? tr("weapon", "arma") : c === "ARMOR" ? tr("armor", "armadura") : tr("accessory", "acessório"));

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
/* só o valor (sem o nome do stat) — p/ tabelas com o nome em coluna à parte */
export const valText = (stat, mod, value) => { const u = statUnit(stat, mod); return `+${nfmt(value, u)}${u.suf}`; };
export function valRange(stat, mod, mn, mx) {
  const u = statUnit(stat, mod);
  return mn === mx ? valText(stat, mod, mn) : `+${nfmt(mn, u)}~${nfmt(mx, u)}${u.suf}`;
}
/* grupos de atributo por tipo (p/ o facet da página Atributos) */
export const ATTR_GROUPS = [
  { key: "offense", label: "Offense", stats: ["AttackDamage", "AttackSpeed", "CastSpeed",
    "CriticalChance", "CriticalDamage", "AreaOfEffect", "PhysicalDamagePercent",
    "FireDamagePercent", "ColdDamagePercent", "LightningDamagePercent", "ChaosDamagePercent",
    "IncreaseAreaOfEffectDamage", "IncreaseMeleeDamage", "IncreaseProjectileDamage",
    "IncreaseSummonDamage", "Multistrike", "ProjectileCount"] },
  { key: "defense", label: "Defense", stats: ["MaxHp", "Armor", "BlockChance",
    "DodgeChance", "ElementalDodgeChance", "DamageAbsorption", "DamageReduction"] },
  { key: "sustain", label: "Sustain", stats: ["HpRegenPerSec", "AddHpPerHit",
    "AddHpPerKill", "HpLeech", "SkillHealIncrease"] },
  { key: "resist", label: "Resistance", stats: ["ChaosResistance", "FireResistance",
    "ColdResistance", "LightningResistance", "PhysicalResistance", "AllElementalResistance"] },
  { key: "utility", label: "Utility / Skill", stats: ["CooldownReduction", "MovementSpeed",
    "AddAllSkillLevel", "SkillDurationIncrease", "SkillRangeExpansion",
    "BaseAttackCountReduction", "IncreaseExpAmount"] },
];
export const TIER_ORDER = ["COMMON", "UNCOMMON", "RARE", "LEGENDARY", "IMMORTAL",
  "ARCANA", "BEYOND", "CELESTIAL", "DIVINE", "COSMIC"];

/* tier pode ser número (deco/engr) ou faixa [a,b] (inscrição) */
export const tierTop = (t) => (Array.isArray(t) ? (t[t.length - 1] || 0) : (t || 0));
export const tierLabel = (t) => (Array.isArray(t) ? `T${t[0]}–${t[t.length - 1]}` : `T${t}`);
export const rollAvg = (o) => Math.round(((o.min || 0) + (o.max || 0)) / 2);
