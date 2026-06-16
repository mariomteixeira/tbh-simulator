// Cores/labels por grau e por tipo de gear — paleta REAL do jogo.
// Fonte única (CubePanel e GearPanel usam isto) pra não divergir de novo:
// IMMORTAL é VERMELHO, não branco. COSMIC é holo (special) — sem cor confirmada.
export const GRADES = {
  COMMON: { label: "Comum", c: "#9c937f" },
  UNCOMMON: { label: "Incomum", c: "#54fc0c" },
  RARE: { label: "Raro", c: "#2f8bfc" },
  LEGENDARY: { label: "Lendário", c: "#fc9c0c" }, // dourado/amarelo (jogo)
  IMMORTAL: { label: "Imortal", c: "#fc2424" }, // vermelho (jogo)
  ARCANA: { label: "Arcana", c: "#b40cfc" },
  BEYOND: { label: "Além", c: "#fc246c" },
  CELESTIAL: { label: "Celestial", c: "#6ccce4" },
  DIVINE: { label: "Divino", c: "#fce454" },
  COSMIC: { label: "Cósmico", c: "#ff5ea8", special: true }, // holo placeholder
};

export const GEAR_PT = {
  SWORD: "Espada", AXE: "Machado", BOW: "Arco", CROSSBOW: "Besta",
  SCEPTER: "Cetro", STAFF: "Cajado", ARROW: "Flecha", BOLT: "Virote",
  ORB: "Orbe", SHIELD: "Escudo", HATCHET: "Machadinha", TOME: "Tomo",
  ARMOR: "Armadura", HELMET: "Elmo", GLOVES: "Luvas", BOOTS: "Botas",
  AMULET: "Amuleto", EARING: "Brinco", RING: "Anel", BRACER: "Bracelete",
};

export const gradeOf = (g) => GRADES[g] || { label: g || "—", c: "#9c937f" };
export const gearPt = (g) => GEAR_PT[g] || (g ? g.toLowerCase() : "");
