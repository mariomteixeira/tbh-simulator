// Cores/labels por grau e por tipo de gear — paleta REAL do jogo.
// IMMORTAL é VERMELHO, não branco. COSMIC é holo (special) — sem cor confirmada.
// Labels seguem o idioma atual (tr): inglês por padrão, pt no toggle.
import { tr } from "./i18n.jsx";

export const GRADES = {
  COMMON: { label: "Comum", en: "Common", c: "#9c937f" },
  UNCOMMON: { label: "Incomum", en: "Uncommon", c: "#54fc0c" },
  RARE: { label: "Raro", en: "Rare", c: "#2f8bfc" },
  LEGENDARY: { label: "Lendário", en: "Legendary", c: "#fc9c0c" },
  IMMORTAL: { label: "Imortal", en: "Immortal", c: "#fc2424" },
  ARCANA: { label: "Arcana", en: "Arcana", c: "#b40cfc" },
  BEYOND: { label: "Além", en: "Beyond", c: "#fc246c" },
  CELESTIAL: { label: "Celestial", en: "Celestial", c: "#6ccce4" },
  DIVINE: { label: "Divino", en: "Divine", c: "#fce454" },
  COSMIC: { label: "Cósmico", en: "Cosmic", c: "#ff5ea8", special: true },
};

export const GEAR_PT = {
  SWORD: "Espada", AXE: "Machado", BOW: "Arco", CROSSBOW: "Besta",
  SCEPTER: "Cetro", STAFF: "Cajado", ARROW: "Flecha", BOLT: "Virote",
  ORB: "Orbe", SHIELD: "Escudo", HATCHET: "Machadinha", TOME: "Tomo",
  ARMOR: "Armadura", HELMET: "Elmo", GLOVES: "Luvas", BOOTS: "Botas",
  AMULET: "Amuleto", EARING: "Brinco", RING: "Anel", BRACER: "Bracelete",
};
export const GEAR_EN = {
  SWORD: "Sword", AXE: "Axe", BOW: "Bow", CROSSBOW: "Crossbow",
  SCEPTER: "Scepter", STAFF: "Staff", ARROW: "Arrow", BOLT: "Bolt",
  ORB: "Orb", SHIELD: "Shield", HATCHET: "Hatchet", TOME: "Tome",
  ARMOR: "Armor", HELMET: "Helmet", GLOVES: "Gloves", BOOTS: "Boots",
  AMULET: "Amulet", EARING: "Earring", RING: "Ring", BRACER: "Bracer",
};

export const gradeOf = (g) => {
  const d = GRADES[g];
  if (!d) return { label: g || "—", c: "#9c937f" };
  return { ...d, label: tr(d.en, d.label) };
};
export const gearPt = (g) => (g ? tr(GEAR_EN[g] || g.toLowerCase(), GEAR_PT[g] || g.toLowerCase()) : "");
