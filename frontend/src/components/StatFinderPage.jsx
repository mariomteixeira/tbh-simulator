import React, { useEffect, useMemo, useState } from "react";
import { gradeOf } from "../grades.js";
import {
  statPt, slotPt, statRange, statText, tierTop, tierLabel,
} from "../gemFormat.js";

const GEM_LABEL = { deco: "Decoração", engr: "Gravação", inscr: "Inscrição" };
const CAT_LABEL = { WEAPON: "Arma", ARMOR: "Armadura", ACCESSORY: "Acessório", COMMON: "Qualquer slot" };
const CAT_ORDER = ["WEAPON", "ARMOR", "ACCESSORY", "COMMON"];
const GEAR_CAP = 8;   // máximo de peças listadas por tipo (o resto vira contagem)

export default function StatFinderPage({ sim }) {
  const owned = useMemo(() => new Set(sim?.owned || []), [sim]);
  const [catalog, setCatalog] = useState(null);
  const [sel, setSel] = useState(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    let alive = true;
    fetch("/api/catalog").then((r) => r.json())
      .then((d) => { if (alive && d && !d.error) setCatalog(d); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // índice: stat -> { gems:[{type,cat,...}], gear:{gearType:[{...}]} }
  const index = useMemo(() => {
    if (!catalog) return null;
    const ix = {};
    const get = (s) => (ix[s] || (ix[s] = { gems: [], gear: {} }));
    for (const [type, gems] of Object.entries(catalog.gems || {}))
      for (const g of gems)
        for (const [cat, opts] of Object.entries(g.groups || {}))
          for (const o of opts)
            get(o.stat).gems.push({
              type, cat, name: g.name, itemKey: g.itemKey, grade: g.grade,
              mod: o.mod, min: o.min, max: o.max, tier: o.tier,
            });
    for (const [gearType, items] of Object.entries(catalog.items || {}))
      for (const it of items)
        for (const l of it.statLines || []) {
          const e = get(l.stat).gear;
          (e[gearType] || (e[gearType] = [])).push({
            name: it.name, itemKey: it.itemKey, grade: it.grade,
            level: it.level, mod: l.mod, value: l.value,
          });
        }
    return ix;
  }, [catalog]);

  const stats = useMemo(
    () => (index ? Object.keys(index).sort((a, b) => statPt(a).localeCompare(statPt(b))) : []),
    [index]
  );
  const shown = stats.filter((s) =>
    statPt(s).toLowerCase().includes(q.toLowerCase()) || s.toLowerCase().includes(q.toLowerCase()));

  if (!catalog) return <main className="page no-rail"><div className="loading">carregando catálogo…</div></main>;

  const data = sel && index[sel];
  // gemas agrupadas por slot-alvo (= onde colocar), mais fortes primeiro
  const gemsByCat = {};
  (data?.gems || []).forEach((g) => (gemsByCat[g.cat] || (gemsByCat[g.cat] = [])).push(g));
  Object.values(gemsByCat).forEach((arr) =>
    arr.sort((a, b) => tierTop(b.tier) - tierTop(a.tier) || (b.max || 0) - (a.max || 0)));
  // equipamentos por tipo de slot, melhor valor primeiro
  const gearTypes = Object.entries(data?.gear || {})
    .map(([gt, arr]) => [gt, [...arr].sort((a, b) => (b.value || 0) - (a.value || 0))])
    .sort((a, b) => (b[1][0]?.value || 0) - (a[1][0]?.value || 0));

  return (
    <main className="page no-rail finder">
      <h1>Atributos</h1>
      <p className="muted small">
        Onde cada atributo aparece — em gemas (decoração / gravação / inscrição, =
        onde dá pra <b>colocar</b>) e em equipamentos (onde já vem nativo). Escolha
        um atributo abaixo.
      </p>

      <input className="b-search finder-search" placeholder="filtrar atributo… (ex.: mov, crítico, resist)"
        value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="finder-chips">
        {shown.map((s) => (
          <button key={s} className="b-chip schip" data-on={sel === s ? 1 : 0}
            onClick={() => setSel(s)}>{statPt(s)}</button>
        ))}
        {shown.length === 0 && <span className="muted small">nenhum atributo bate com "{q}"</span>}
      </div>

      {!sel ? (
        <div className="b-empty">Escolha um atributo pra ver onde encontrá-lo.</div>
      ) : (
        <div className="finder-out">
          <section className="sec">
            <h2>Gemas — onde colocar {statPt(sel)}</h2>
            {CAT_ORDER.filter((c) => gemsByCat[c]).length === 0 ? (
              <div className="b-empty">Nenhuma gema dá {statPt(sel)}.</div>
            ) : (
              CAT_ORDER.filter((c) => gemsByCat[c]).map((cat) => (
                <div className="finder-grp" key={cat}>
                  <div className="finder-grp-h">{CAT_LABEL[cat] || cat}</div>
                  {gemsByCat[cat].map((g, i) => {
                    const gr = gradeOf(g.grade);
                    return (
                      <div className="finder-row" key={g.itemKey + "_" + i}>
                        <span className={"finder-badge bg-" + g.type}>{GEM_LABEL[g.type]}</span>
                        <span className="finder-name" style={{ color: gr.c }}>
                          {g.name}
                          {owned.has(g.itemKey) && <span className="op-tag own">tenho</span>}
                        </span>
                        <span className="finder-val">{statRange(g.stat || sel, g.mod, g.min, g.max)}</span>
                        <span className="finder-tier" style={{ color: gr.c }}>{tierLabel(g.tier)}</span>
                      </div>
                    );
                  })}
                </div>
              ))
            )}
          </section>

          <section className="sec">
            <h2>Equipamentos com {statPt(sel)}</h2>
            {gearTypes.length === 0 ? (
              <div className="b-empty">Nenhum equipamento traz {statPt(sel)} nativo.</div>
            ) : (
              gearTypes.map(([gt, arr]) => (
                <div className="finder-grp" key={gt}>
                  <div className="finder-grp-h">{slotPt(gt)} <span className="muted">· {arr.length}</span></div>
                  {arr.slice(0, GEAR_CAP).map((it, i) => {
                    const gr = gradeOf(it.grade);
                    return (
                      <div className="finder-row" key={it.itemKey + "_" + i}>
                        <span className="finder-name" style={{ color: gr.c }}>
                          {it.name}
                          {owned.has(it.itemKey) && <span className="op-tag own">tenho</span>}
                        </span>
                        <span className="muted finder-lv">Lv{it.level}</span>
                        <span className="finder-val">{statText(it.stat || sel, it.mod, it.value)}</span>
                      </div>
                    );
                  })}
                  {arr.length > GEAR_CAP && (
                    <div className="finder-more muted">+{arr.length - GEAR_CAP} outras peças</div>
                  )}
                </div>
              ))
            )}
          </section>
        </div>
      )}
    </main>
  );
}
