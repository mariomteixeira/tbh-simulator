import React, { useEffect, useMemo, useState } from "react";
import { gradeOf } from "../grades.js";
import {
  statPt, slotPt, catPt, catOf, statRange, statText,
  tierTop, tierLabel, TIER_ORDER, ATTR_GROUPS,
} from "../gemFormat.js";

const SRC_TABS = [
  { id: "all", label: "Tudo", cls: "" },
  { id: "deco", label: "Decoração", cls: "" },
  { id: "engr", label: "Gravação", cls: "engr" },
  { id: "inscr", label: "Inscrição", cls: "inscr" },
  { id: "gear", label: "Equipamento", cls: "" },
];
const SLOT_FACETS = [["WEAPON", "Arma"], ["ARMOR", "Armadura"], ["ACCESSORY", "Acessório"]];
const SRC_LABEL = { deco: "Decoração", engr: "Gravação", inscr: "Inscrição", gear: "Equip." };
const SRC_BADGE = { deco: "bg-deco", engr: "bg-engr", inscr: "bg-inscr", gear: "bg-gear" };
const CAP = 160;  // máx. de linhas exibidas (o resto vira contagem — refine os filtros)

export default function StatFinderPage({ sim }) {
  const owned = useMemo(() => new Set(sim?.owned || []), [sim]);
  const [catalog, setCatalog] = useState(null);
  const [src, setSrc] = useState("all");
  const [attrs, setAttrs] = useState(new Set());
  const [slots, setSlots] = useState(new Set());
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
  const { entries, statSet, gradeSet } = useMemo(() => {
    const out = [], ss = new Set(), gs = new Set();
    if (!catalog) return { entries: out, statSet: ss, gradeSet: gs };
    for (const [type, gems] of Object.entries(catalog.gems || {}))
      for (const g of gems) {
        gs.add(g.grade);
        for (const [cat, opts] of Object.entries(g.groups || {})) {
          opts.forEach((o) => ss.add(o.stat));
          out.push({
            kind: "gem", srcType: type, itemKey: g.itemKey, name: g.name, grade: g.grade,
            cat, opts, maxTier: opts.reduce((m, o) => Math.max(m, tierTop(o.tier)), 0),
          });
        }
      }
    for (const [gearType, items] of Object.entries(catalog.items || {}))
      for (const it of items) {
        gs.add(it.grade);
        (it.statLines || []).forEach((l) => ss.add(l.stat));
        out.push({
          kind: "gear", srcType: "gear", itemKey: it.itemKey, name: it.name, grade: it.grade,
          gearType, cat: catOf(gearType), level: it.level, lines: it.statLines || [],
        });
      }
    return { entries: out, statSet: ss, gradeSet: gs };
  }, [catalog]);

  const toggle = (set, setter, v) => {
    const n = new Set(set); n.has(v) ? n.delete(v) : n.add(v); setter(n);
  };
  const clearAll = () => { setAttrs(new Set()); setSlots(new Set()); setTiers(new Set()); setQ(""); setInvOnly(false); setSrc("all"); };
  const anyFilter = src !== "all" || attrs.size || slots.size || tiers.size || q || invOnly;

  if (!catalog) return <main className="page no-rail"><div className="loading">carregando catálogo…</div></main>;

  const matchAttr = (e) => e.kind === "gem" ? e.opts.some((o) => attrs.has(o.stat)) : e.lines.some((l) => attrs.has(l.stat));
  const view = entries.filter((e) => {
    if (src !== "all" && e.srcType !== src) return false;
    if (tiers.size && !tiers.has(e.grade)) return false;
    if (slots.size && e.cat !== "COMMON" && !slots.has(e.cat)) return false;
    if (invOnly && !owned.has(e.itemKey)) return false;
    if (attrs.size && !matchAttr(e)) return false;
    if (q && !(e.name || "").toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });
  const rank = (g) => TIER_ORDER.indexOf(g);
  view.sort((a, b) => rank(b.grade) - rank(a.grade) || (b.maxTier || 0) - (a.maxTier || 0) || (a.name || "").localeCompare(b.name || ""));
  const shownRows = view.slice(0, CAP);

  // atributos agrupados por tipo (só os que existem no catálogo) + sobras em "Outros"
  const grouped = ATTR_GROUPS.map((grp) => ({ ...grp, list: grp.stats.filter((s) => statSet.has(s)) })).filter((grp) => grp.list.length);
  const inGroups = new Set(grouped.flatMap((g) => g.list));
  const others = [...statSet].filter((s) => !inGroups.has(s)).sort((a, b) => statPt(a).localeCompare(statPt(b)));
  if (others.length) grouped.push({ key: "other", label: "Outros", list: others });
  const tierChips = TIER_ORDER.filter((g) => gradeSet.has(g));

  return (
    <main className="page no-rail finder">
      <h1>Atributos</h1>
      <p className="muted small">
        Combine filtros pra achar onde cada atributo aparece — gemas (onde dá pra
        <b> colocar</b>) e equipamentos (onde já vem nativo). Tudo dinâmico.
      </p>

      <div className="b-tabs finder-tabs">
        {SRC_TABS.map((t) => (
          <button key={t.id} className={"b-tab " + t.cls + (src === t.id ? " active" : "")}
            onClick={() => setSrc(t.id)}>{t.label}</button>
        ))}
      </div>

      <div className="b-filters finder-filters">
        <div className="frow">
          <input className="b-search" placeholder="buscar pelo nome… (ex.: esmeralda, botas)"
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
        <div className="frow">
          <span className="lbl">slot</span>
          <div className="b-chips">
            {SLOT_FACETS.map(([c, lbl]) => (
              <button key={c} className="b-chip schip" data-on={slots.has(c) ? 1 : 0}
                onClick={() => toggle(slots, setSlots, c)}>{lbl}</button>
            ))}
          </div>
        </div>
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

      <div className="b-list finder-list">
        {view.length === 0 ? (
          <div className="b-empty">Nada bate com os filtros.</div>
        ) : shownRows.map((e, i) => {
          const gr = gradeOf(e.grade);
          const showOpts = e.kind === "gem"
            ? (attrs.size ? e.opts.filter((o) => attrs.has(o.stat)) : e.opts)
            : (attrs.size ? e.lines.filter((l) => attrs.has(l.stat)) : e.lines);
          const first = showOpts[0];
          const where = e.kind === "gem"
            ? (e.cat === "COMMON" ? "qualquer slot" : catPt(e.cat))
            : slotPt(e.gearType);
          const tierTxt = e.kind === "gem"
            ? tierLabel(first ? first.tier : e.maxTier) : gr.label;
          return (
            <div className="finder-row" key={e.itemKey + "_" + e.cat + "_" + i}>
              <span className={"finder-badge " + (SRC_BADGE[e.srcType] || "bg-gear")}>{SRC_LABEL[e.srcType]}</span>
              <span className="finder-name" style={{ color: gr.c }}>
                {e.name}
                {owned.has(e.itemKey) && <span className="op-tag own">tenho</span>}
              </span>
              <span className="finder-where">{where}{e.kind === "gear" && e.level ? " · Lv" + e.level : ""}</span>
              <span className="finder-val">
                {first
                  ? (e.kind === "gem" ? statRange(first.stat, first.mod, first.min, first.max) : statText(first.stat, first.mod, first.value))
                  : "—"}
                {showOpts.length > 1 && <span className="muted"> +{showOpts.length - 1}</span>}
              </span>
              <span className="finder-tier" style={{ color: gr.c }}>{tierTxt}</span>
            </div>
          );
        })}
      </div>
    </main>
  );
}
