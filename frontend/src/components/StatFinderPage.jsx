import React, { useEffect, useMemo, useState } from "react";
import { gradeOf, gearPt } from "../grades.js";
import {
  statPt, catOf, statRange, statText, valRange, valText, tierTop, tierLabel, TIER_ORDER,
} from "../gemFormat.js";
import { useT, useLang } from "../i18n.jsx";

const TYPES = [["all", "All", "Todos"], ["weapon", "Weapon", "Arma"], ["offhand", "Off-hand", "Off-hand"], ["armor", "Armor", "Armadura"], ["accessory", "Accessory", "Acessório"]];
const GEARTYPE_TYPE = {
  SWORD: "weapon", AXE: "weapon", BOW: "weapon", CROSSBOW: "weapon", SCEPTER: "weapon", STAFF: "weapon", HATCHET: "weapon",
  SHIELD: "offhand", ORB: "offhand", TOME: "offhand", ARROW: "offhand", BOLT: "offhand",
  HELMET: "armor", ARMOR: "armor", GLOVES: "armor", BOOTS: "armor",
  AMULET: "accessory", EARING: "accessory", RING: "accessory", BRACER: "accessory",
};
const TYPE_CAT = { weapon: "WEAPON", offhand: "WEAPON", armor: "ARMOR", accessory: "ACCESSORY" };
const SRC_L = { deco: ["Decoration", "Decoração"], engr: ["Engraving", "Gravação"], inscr: ["Inscription", "Inscrição"] };
const CAT_L = { WEAPON: ["Weapon", "Arma"], ARMOR: ["Armor", "Armadura"], ACCESSORY: ["Accessory", "Acessório"], COMMON: ["Any slot", "Qualquer slot"] };
const LVL_MAX = 100;
const CAP = 120;

function ItemIco({ k, name, grade }) {
  const [bad, setBad] = useState(false);
  const g = gradeOf(grade);
  if (bad || !k)
    return <span className="acard-ico fb" style={{ "--g": g.c }}>{(name || "?").slice(0, 2).toUpperCase()}</span>;
  return <img className="acard-ico" style={{ "--g": g.c }} src={`/itemicon/${k}.png`} alt=""
    loading="lazy" onError={() => setBad(true)} />;
}

function DualRange({ min, max, onChange }) {
  const lo = ((min - 1) / (LVL_MAX - 1)) * 100, hi = ((max - 1) / (LVL_MAX - 1)) * 100;
  return (
    <div className="b-range">
      <div className="track" /><div className="fill" style={{ left: lo + "%", width: (hi - lo) + "%" }} />
      <input type="range" min={1} max={LVL_MAX} value={min} onChange={(e) => onChange(Math.min(+e.target.value, max), max)} />
      <input type="range" min={1} max={LVL_MAX} value={max} onChange={(e) => onChange(min, Math.max(+e.target.value, min))} />
    </div>
  );
}

export default function StatFinderPage({ sim }) {
  const t = useT();
  const { lang } = useLang();
  const owned = useMemo(() => new Set(sim?.owned || []), [sim]);
  const [catalog, setCatalog] = useState(null);
  const [type, setType] = useState("all");
  const [rarity, setRarity] = useState("all");
  const [attrs, setAttrs] = useState(new Set());
  const [lvl, setLvl] = useState([1, LVL_MAX]);
  const [q, setQ] = useState("");
  const [tip, setTip] = useState(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/catalog?lang=" + lang).then((r) => r.json())
      .then((d) => { if (alive && d && !d.error) setCatalog(d); }).catch(() => {});
    return () => { alive = false; };
  }, [lang]);

  const { entries, gemByKey } = useMemo(() => {
    const out = [], gk = {};
    if (!catalog) return { entries: out, gemByKey: gk };
    for (const [srcType, gems] of Object.entries(catalog.gems || {}))
      for (const g of gems) {
        gk[g.itemKey] = g;
        for (const [cat, opts] of Object.entries(g.groups || {}))
          out.push({ kind: "gem", srcType, itemKey: g.itemKey, name: g.name, grade: g.grade,
            cat, opts, maxTier: opts.reduce((m, o) => Math.max(m, tierTop(o.tier)), 0) });
      }
    for (const [gearType, items] of Object.entries(catalog.items || {}))
      for (const it of items)
        out.push({ kind: "gear", srcType: "gear", itemKey: it.itemKey, name: it.name, grade: it.grade,
          gearType, cat: catOf(gearType), gtype: GEARTYPE_TYPE[gearType] || "weapon",
          level: it.level || 0, lines: it.statLines || [],
          maxVal: (it.statLines || []).reduce((m, l) => Math.max(m, l.value || 0), 0) });
    return { entries: out, gemByKey: gk };
  }, [catalog]);

  const statsOf = (e) => (e.kind === "gem" ? e.opts : e.lines).map((o) => o.stat);
  const typeMatch = (e, t) => {
    if (t === "all") return true;
    if (e.kind === "gem") return e.cat === "COMMON" || e.cat === TYPE_CAT[t];
    return e.gtype === t;
  };
  const matchAttr = (e) => statsOf(e).some((s) => attrs.has(s));

  // cascata: raridades dado o tipo; atributos dado tipo+raridade
  const availGrades = useMemo(() => {
    const s = new Set(); for (const e of entries) if (typeMatch(e, type)) s.add(e.grade); return s;
  }, [entries, type]);
  const availStats = useMemo(() => {
    const s = new Set();
    for (const e of entries) if (typeMatch(e, type) && (rarity === "all" || e.grade === rarity)) statsOf(e).forEach((x) => s.add(x));
    return s;
  }, [entries, type, rarity]);

  const toggleAttr = (v) => setAttrs((p) => { const n = new Set(p); n.has(v) ? n.delete(v) : n.add(v); return n; });
  const pickType = (t) => {
    const ng = new Set(); const ns = new Set();
    for (const e of entries) if (typeMatch(e, t)) { ng.add(e.grade); }
    for (const e of entries) if (typeMatch(e, t) && (rarity === "all" || e.grade === rarity)) statsOf(e).forEach((x) => ns.add(x));
    if (rarity !== "all" && !ng.has(rarity)) setRarity("all");
    setAttrs((p) => new Set([...p].filter((a) => ns.has(a))));
    setType(t);
  };
  const pickRarity = (r) => {
    const ns = new Set();
    for (const e of entries) if (typeMatch(e, type) && (r === "all" || e.grade === r)) statsOf(e).forEach((x) => ns.add(x));
    setAttrs((p) => new Set([...p].filter((a) => ns.has(a))));
    setRarity(r);
  };

  if (!catalog) return <main className="page no-rail"><div className="loading">{t("loading catalog…", "carregando catálogo…")}</div></main>;

  const passes = (e) => {
    if (!typeMatch(e, type)) return false;
    if (rarity !== "all" && e.grade !== rarity) return false;
    if (attrs.size && !matchAttr(e)) return false;
    if (e.kind === "gear" && (e.level < lvl[0] || e.level > lvl[1])) return false;
    if (q && !(e.name || "").toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  };
  const view = entries.filter(passes);
  const rank = (g) => TIER_ORDER.indexOf(g);
  view.sort((a, b) => rank(a.grade) - rank(b.grade)        // menor tier -> maior
    || (a.maxTier || 0) - (b.maxTier || 0) || (a.maxVal || 0) - (b.maxVal || 0)
    || (a.name || "").localeCompare(b.name || ""));
  const shown = view.slice(0, CAP);
  const gems = shown.filter((e) => e.kind === "gem");
  const gear = shown.filter((e) => e.kind === "gear");

  const attrChips = [...availStats].sort((a, b) => statPt(a).localeCompare(statPt(b)));
  const rarChips = TIER_ORDER.filter((g) => availGrades.has(g));

  const tipFor = (node) => ({
    onMouseMove: (e) => setTip({ x: e.clientX, y: e.clientY, node }),
    onMouseLeave: () => setTip(null),
  });

  const card = (e, i) => {
    const gr = gradeOf(e.grade);
    const lines0 = e.kind === "gem" ? e.opts : e.lines;
    // inscrição rola 1 de ~16: só mostra o bônus quando há atributo selecionado
    const lines = attrs.size ? lines0.filter((l) => attrs.has(l.stat))
      : (e.srcType === "inscr" ? [] : lines0);
    const sub = e.kind === "gem"
      ? `${t(...SRC_L[e.srcType])} · ${gr.label}`
      : `${gearPt(e.gearType)} · Lv${e.level} · ${gr.label}`;
    return (
      <div className="acard" key={e.itemKey + "_" + e.cat + "_" + i} style={{ "--g": gr.c }}
        {...tipFor(<FinderTip e={e} gem={gemByKey[e.itemKey]} />)}>
        <div className="acard-h">
          <ItemIco k={e.itemKey} name={e.name} grade={e.grade} />
          <div className="acard-id">
            <span className="acard-nm">{e.name}{owned.has(e.itemKey) && <span className="op-tag own">{t("owned", "tenho")}</span>}</span>
            <span className="acard-sub">{sub}</span>
          </div>
          {e.kind === "gem" && <span className="acard-tier">{tierLabel(e.maxTier)}</span>}
        </div>
        {lines.length > 0 && (
          <div className="acard-stats">
            {lines.map((l, j) => (
              <div className={"acard-stat" + (attrs.has(l.stat) ? " hit" : "")} key={j}>
                <span>{statPt(l.stat)}</span>
                <span className="v">{e.kind === "gem" ? valRange(l.stat, l.mod, l.min, l.max) : valText(l.stat, l.mod, l.value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <main className="page no-rail finder">
      <h1>{t("Attributes", "Atributos")}</h1>

      <div className="afilters">
        <Row label={t("Type", "Tipo")}>
          {TYPES.map(([id, en, pt]) => (
            <button key={id} className={"achip" + (type === id ? " on" : "")} onClick={() => pickType(id)}>{t(en, pt)}</button>
          ))}
        </Row>
        <Row label={t("Rarity", "Raridade")}>
          <button className={"achip" + (rarity === "all" ? " on" : "")} onClick={() => pickRarity("all")}>{t("All", "Todas")}</button>
          {rarChips.map((g) => (
            <button key={g} className={"achip rchip" + (rarity === g ? " on" : "")}
              style={{ "--g": gradeOf(g).c }} onClick={() => pickRarity(g)}>{gradeOf(g).label}</button>
          ))}
        </Row>
        {attrChips.length > 0 && (
          <Row label={t("Attribute", "Atributo")}>
            {attrChips.map((s) => (
              <button key={s} className={"achip" + (attrs.has(s) ? " on" : "")} onClick={() => toggleAttr(s)}>{statPt(s)}</button>
            ))}
          </Row>
        )}
        <Row label={t("Level", "Nível")}>
          <span className="lvbox">{t("min", "mín")} {lvl[0]}</span><span className="lvbox">{t("max", "máx")} {lvl[1]}</span>
          <DualRange min={lvl[0]} max={lvl[1]} onChange={(a, b) => setLvl([a, b])} />
        </Row>
        <Row label={t("Search", "Buscar")}>
          <input className="b-search" placeholder={t("filter by name…", "filtrar pelo nome…")} value={q} onChange={(e) => setQ(e.target.value)} />
        </Row>
      </div>

      <div className="finder-count">{view.length} {t(view.length === 1 ? "result" : "results", view.length === 1 ? "resultado" : "resultados")}{view.length > CAP && <span className="muted"> · {t("showing", "mostrando")} {CAP}</span>}</div>

      {view.length === 0 && <div className="b-empty">{t("Nothing matches the filters.", "Nada bate com os filtros.")}</div>}
      {gems.length > 0 && (
        <>
          <div className="finder-sec-h"><span className="t">{t("Gems", "Gemas")}</span><span className="ln" /><span className="n">{gems.length}</span></div>
          <div className="acard-grid">{gems.map(card)}</div>
        </>
      )}
      {gear.length > 0 && (
        <>
          <div className="finder-sec-h"><span className="t">{t("Equipment", "Equipamentos")}</span><span className="ln" /><span className="n">{gear.length}</span></div>
          <div className="acard-grid">{gear.map(card)}</div>
        </>
      )}

      {tip && (
        <div className="finder-tip" style={{ left: Math.min(tip.x + 16, window.innerWidth - 320), top: Math.min(tip.y + 16, window.innerHeight - 260) }}>{tip.node}</div>
      )}
    </main>
  );
}

function Row({ label, children }) {
  return (
    <div className="afrow">
      <span className="aflabel"><span className="gi" />{label}</span>
      <div className="achips">{children}</div>
    </div>
  );
}

function FinderTip({ e, gem }) {
  const t = useT();
  const gr = gradeOf(e.grade);
  if (e.kind === "gear") {
    return (
      <>
        <div className="tip-name" style={{ color: gr.c }}>{e.name}</div>
        <div className="tip-meta">{gearPt(e.gearType)} · {gr.label} · Lv{e.level}</div>
        <div className="tip-stats">
          {(e.lines || []).map((l, i) => <div className="tip-stat" key={i}>{statText(l.stat, l.mod, l.value)}</div>)}
        </div>
      </>
    );
  }
  const groups = gem?.groups || { [e.cat]: e.opts };
  return (
    <>
      <div className="tip-name" style={{ color: gr.c }}>{e.name}</div>
      <div className="tip-meta">{t(...SRC_L[e.srcType])} · {gr.label}</div>
      <div className="tip-stats">
        {Object.entries(groups).map(([cat, opts]) => (
          <div key={cat}>
            <div className="tip-cat">{CAT_L[cat] ? t(...CAT_L[cat]) : cat}</div>
            {opts.map((o, i) => <div className="tip-stat" key={i}>{statRange(o.stat, o.mod, o.min, o.max)} · {tierLabel(o.tier)}</div>)}
          </div>
        ))}
      </div>
    </>
  );
}
