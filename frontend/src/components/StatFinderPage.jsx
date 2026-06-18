import React, { useEffect, useMemo, useState } from "react";
import { gradeOf } from "../grades.js";
import {
  statPt, slotPt, catOf, statRange, statText,
  tierTop, tierLabel, TIER_ORDER, ATTR_GROUPS,
} from "../gemFormat.js";

const SRC_TABS = [
  { id: "all", label: "Tudo", cls: "" },
  { id: "deco", label: "Decoração", cls: "" },
  { id: "engr", label: "Gravação", cls: "engr" },
  { id: "inscr", label: "Inscrição", cls: "inscr" },
  { id: "gear", label: "Equipamento", cls: "" },
];
const SLOTS = [["all", "Todos"], ["WEAPON", "Arma"], ["ARMOR", "Armadura"], ["ACCESSORY", "Acessório"]];
const SLOT_ORDER = ["WEAPON", "ARMOR", "ACCESSORY", "COMMON"];
const SLOT_LABEL = { WEAPON: "Arma", ARMOR: "Armadura", ACCESSORY: "Acessório", COMMON: "Qualquer slot" };
const SRC_LABEL = { deco: "Decoração", engr: "Gravação", inscr: "Inscrição", gear: "Equip." };
const SRC_BADGE = { deco: "bg-deco", engr: "bg-engr", inscr: "bg-inscr", gear: "bg-gear" };
const CAP = 200;

/* ícone do item (backend serve /itemicon); cai para tile de iniciais */
function ItemIco({ k, name, grade }) {
  const [bad, setBad] = useState(false);
  const g = gradeOf(grade);
  if (bad || !k)
    return <span className="finder-ico fb" style={{ "--g": g.c }}>{(name || "?").slice(0, 2).toUpperCase()}</span>;
  return <img className="finder-ico" style={{ "--g": g.c }} src={`/itemicon/${k}.png`} alt=""
    loading="lazy" onError={() => setBad(true)} />;
}

export default function StatFinderPage({ sim }) {
  const owned = useMemo(() => new Set(sim?.owned || []), [sim]);
  const [catalog, setCatalog] = useState(null);
  const [src, setSrc] = useState("all");
  const [slot, setSlot] = useState("all");
  const [attrs, setAttrs] = useState(new Set());
  const [tiers, setTiers] = useState(new Set());
  const [q, setQ] = useState("");
  const [invOnly, setInvOnly] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch("/api/catalog").then((r) => r.json())
      .then((d) => { if (alive && d && !d.error) setCatalog(d); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // entradas planas: 1 por (gema × categoria) + 1 por peça de gear
  const entries = useMemo(() => {
    const out = [];
    if (!catalog) return out;
    for (const [type, gems] of Object.entries(catalog.gems || {}))
      for (const g of gems)
        for (const [cat, opts] of Object.entries(g.groups || {}))
          out.push({
            kind: "gem", srcType: type, itemKey: g.itemKey, name: g.name, grade: g.grade,
            cat, opts, maxTier: opts.reduce((m, o) => Math.max(m, tierTop(o.tier)), 0),
          });
    for (const [gearType, items] of Object.entries(catalog.items || {}))
      for (const it of items)
        out.push({
          kind: "gear", srcType: "gear", itemKey: it.itemKey, name: it.name, grade: it.grade,
          gearType, cat: catOf(gearType), level: it.level, lines: it.statLines || [],
          maxVal: (it.statLines || []).reduce((m, l) => Math.max(m, l.value || 0), 0),
        });
    return out;
  }, [catalog]);

  const statsOf = (e) => (e.kind === "gem" ? e.opts : e.lines).map((o) => o.stat);
  // o que existe dado source+slot (pra cascatear os outros filtros)
  const availFor = (srcV, slotV) => {
    const ss = new Set(), gs = new Set();
    for (const e of entries) {
      if (srcV !== "all" && e.srcType !== srcV) continue;
      if (slotV !== "all" && e.cat !== "COMMON" && e.cat !== slotV) continue;
      gs.add(e.grade); statsOf(e).forEach((s) => ss.add(s));
    }
    return { ss, gs };
  };
  const avail = useMemo(() => availFor(src, slot), [entries, src, slot]);

  const toggle = (set, setter, v) => { const n = new Set(set); n.has(v) ? n.delete(v) : n.add(v); setter(n); };
  const prune = (srcV, slotV) => {
    const { ss, gs } = availFor(srcV, slotV);
    setAttrs((p) => new Set([...p].filter((a) => ss.has(a))));
    setTiers((p) => new Set([...p].filter((t) => gs.has(t))));
  };
  const pickSlot = (s) => { prune(src, s); setSlot(s); };
  const pickSrc = (s) => { prune(s, slot); setSrc(s); };
  const clearAll = () => { setSrc("all"); setSlot("all"); setAttrs(new Set()); setTiers(new Set()); setQ(""); setInvOnly(false); };
  const anyFilter = src !== "all" || slot !== "all" || attrs.size || tiers.size || q || invOnly;

  if (!catalog) return <main className="page no-rail"><div className="loading">carregando catálogo…</div></main>;

  const matchAttr = (e) => statsOf(e).some((s) => attrs.has(s));
  const passes = (e, slotV) => {
    if (src !== "all" && e.srcType !== src) return false;
    if (slotV !== "all" && e.cat !== "COMMON" && e.cat !== slotV) return false;
    if (tiers.size && !tiers.has(e.grade)) return false;
    if (invOnly && !owned.has(e.itemKey)) return false;
    if (attrs.size && !matchAttr(e)) return false;
    if (q && !(e.name || "").toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  };
  const view = entries.filter((e) => passes(e, slot));
  const rank = (g) => TIER_ORDER.indexOf(g);
  view.sort((a, b) => rank(b.grade) - rank(a.grade)
    || (b.maxTier || 0) - (a.maxTier || 0) || (b.maxVal || 0) - (a.maxVal || 0)
    || (a.name || "").localeCompare(b.name || ""));
  const shown = view.slice(0, CAP);

  // agrupa por slot-categoria; dentro: gemas antes do gear (já ordenado por grau)
  const sections = SLOT_ORDER.map((cat) => ({
    cat,
    rows: shown.filter((e) => e.cat === cat).sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "gem" ? -1 : 1)),
  })).filter((s) => s.rows.length);

  // facets cascateados
  const grouped = ATTR_GROUPS.map((g) => ({ ...g, list: g.stats.filter((s) => avail.ss.has(s)) })).filter((g) => g.list.length);
  const inG = new Set(grouped.flatMap((g) => g.list));
  const others = [...avail.ss].filter((s) => !inG.has(s)).sort((a, b) => statPt(a).localeCompare(statPt(b)));
  if (others.length) grouped.push({ key: "other", label: "Outros", list: others });
  const tierChips = TIER_ORDER.filter((g) => avail.gs.has(g));

  return (
    <main className="page no-rail finder">
      <h1>Atributos</h1>
      <p className="muted small">
        Onde cada atributo aparece — gemas (onde dá pra <b>colocar</b>) e equipamentos
        (onde já vem nativo). Escolha o slot e os filtros cascateiam, igual ao Builds.
      </p>

      <div className="b-tabs finder-tabs">
        {SRC_TABS.map((t) => (
          <button key={t.id} className={"b-tab " + t.cls + (src === t.id ? " active" : "")}
            onClick={() => pickSrc(t.id)}>{t.label}</button>
        ))}
      </div>

      <div className="finder-slotsel">
        {SLOTS.map(([id, label]) => (
          <button key={id} className={"slotbtn" + (slot === id ? " on" : "")} onClick={() => pickSlot(id)}>
            <span className="si" /> {label}
            <span className="c">·{entries.filter((e) => passes(e, id)).length}</span>
          </button>
        ))}
      </div>

      <div className="b-filters finder-filters">
        <div className="frow">
          <input className="b-search" placeholder="buscar pelo nome… (ex.: esmeralda, brinco)"
            value={q} onChange={(e) => setQ(e.target.value)} />
          <button className={"b-toggle" + (invOnly ? " on" : "")} onClick={() => setInvOnly(!invOnly)}>só inventário</button>
          {anyFilter ? <button className="b-toggle" onClick={clearAll}>limpar</button> : null}
        </div>
        {tierChips.length > 0 && (
          <div className="frow">
            <span className="lbl">tier</span>
            <div className="b-chips">
              {tierChips.map((gr) => (
                <button key={gr} className="b-chip tchip" data-on={tiers.has(gr) ? 1 : 0}
                  style={{ "--g": gradeOf(gr).c }} onClick={() => toggle(tiers, setTiers, gr)}>{gr.slice(0, 4)}</button>
              ))}
            </div>
          </div>
        )}
        <div className="afacets">
          {grouped.map((grp) => (
            <div className="afacet" key={grp.key}>
              <span className="afacet-h">{grp.label}</span>
              <div className="b-chips">
                {grp.list.map((s) => (
                  <button key={s} className="b-chip schip" data-on={attrs.has(s) ? 1 : 0}
                    onClick={() => toggle(attrs, setAttrs, s)}>{statPt(s)}</button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="finder-count">
        {view.length} resultado{view.length === 1 ? "" : "s"}
        {view.length > CAP && <span className="muted"> · mostrando {CAP} (refine os filtros)</span>}
      </div>

      {view.length === 0 ? (
        <div className="b-empty">Nada bate com os filtros.</div>
      ) : sections.map((sec) => (
        <div className="finder-sec" key={sec.cat}>
          <div className="finder-sec-h">
            <span className="t">{SLOT_LABEL[sec.cat]}</span>
            <span className="ln" />
            <span className="n">{sec.rows.length}</span>
          </div>
          {sec.rows.map((e, i) => {
            const gr = gradeOf(e.grade);
            const sel = e.kind === "gem"
              ? (attrs.size ? e.opts.filter((o) => attrs.has(o.stat)) : e.opts)
              : (attrs.size ? e.lines.filter((l) => attrs.has(l.stat)) : e.lines);
            const f = sel[0];
            return (
              <div className="finder-row" key={e.itemKey + "_" + e.cat + "_" + i}>
                <ItemIco k={e.itemKey} name={e.name} grade={e.grade} />
                <span className="finder-name" style={{ color: gr.c }}>
                  {e.name}
                  {owned.has(e.itemKey) && <span className="op-tag own">tenho</span>}
                </span>
                <span className={"finder-badge " + (SRC_BADGE[e.srcType] || "bg-gear")}>
                  {e.kind === "gear" ? slotPt(e.gearType) : SRC_LABEL[e.srcType]}
                </span>
                <span className="finder-val">
                  {f ? (e.kind === "gem" ? statRange(f.stat, f.mod, f.min, f.max) : statText(f.stat, f.mod, f.value)) : "—"}
                  {sel.length > 1 && <span className="muted"> +{sel.length - 1}</span>}
                  {e.kind === "gear" && e.level ? <span className="muted"> · Lv{e.level}</span> : null}
                </span>
                <span className="finder-tier" style={{ color: gr.c }}>
                  {e.kind === "gem" ? tierLabel(f ? f.tier : e.maxTier) : gr.label}
                </span>
              </div>
            );
          })}
        </div>
      ))}
    </main>
  );
}
