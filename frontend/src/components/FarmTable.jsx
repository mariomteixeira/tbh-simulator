import React, { useMemo, useState } from "react";
import { fmt, fmtDur } from "../format.js";

const DIFFS = ["todas", "N", "NM", "H", "T"];
// controles de ordenação (substituem os <th> clicáveis da tabela antiga)
const SORTS = [
  { key: "goldPerHour", label: "gold/h" },
  { key: "expPerHour", label: "exp/h" },
  { key: "clearTime", label: "clear" },
  { key: "lvl", label: "lvl" },
  { key: "label", label: "estágio" },
];

export default function FarmTable({ farm }) {
  const [sort, setSort] = useState({ key: "goldPerHour", dir: -1 });
  const [diff, setDiff] = useState("todas");
  const [all, setAll] = useState(false);

  const rows = useMemo(() => {
    // runs de boss de ato nao sao farmaveis em loop: fora da lista
    let r = (farm.rows || []).filter((x) => x.type !== "ACTBOSS");
    // por padrao so fases que voce FARMA (limpas e dentro do teto) + o push;
    // "ver todas" libera o resto pra referencia
    if (!all)
      r = r.filter(
        (x) => (x.cleared && !x.beyondCeiling) || x.key === farm.push?.key
      );
    if (diff !== "todas") r = r.filter((x) => x.tag === diff);
    r.sort((a, b) => {
      const va = a[sort.key], vb = b[sort.key];
      if (typeof va === "string") return sort.dir * va.localeCompare(vb);
      return sort.dir * ((va ?? 0) - (vb ?? 0));
    });
    if (!all) {
      const specials = new Set(
        [farm.current, farm.bestGold, farm.bestExp, farm.push]
          .filter(Boolean)
          .map((x) => x.key)
      );
      const top = r.slice(0, 12);
      const topKeys = new Set(top.map((x) => x.key));
      for (const x of r) if (specials.has(x.key) && !topKeys.has(x.key)) top.push(x);
      r = top;
    }
    return r;
  }, [farm, sort, diff, all]);

  const clickSort = (key) =>
    setSort((s) => ({ key, dir: s.key === key ? -s.dir : -1 }));

  const arrow = (key) =>
    sort.key === key ? (sort.dir < 0 ? " ▾" : " ▴") : "";

  return (
    <section className="sec">
      <div className="sec-head">
        <h2>Farm — taxas reais por estágio</h2>
        <div className="row-chips">
          {DIFFS.map((dd) => (
            <button
              key={dd}
              className={"chip" + (diff === dd ? " on" : "")}
              onClick={() => setDiff(dd)}
            >
              {dd}
            </button>
          ))}
          {SORTS.map((c) => (
            <button
              key={c.key}
              className={"chip" + (sort.key === c.key ? " on" : "")}
              onClick={() => clickSort(c.key)}
            >
              {c.label}
              {arrow(c.key)}
            </button>
          ))}
          <button className="chip" onClick={() => setAll(!all)}>
            {all ? "ver top" : "ver todas"}
          </button>
        </div>
      </div>

      <div className="farm-list">
        {rows.map((r) => {
          const isBestGold = farm.bestGold?.key === r.key;
          const isBestExp = farm.bestExp?.key === r.key;
          const isPush = farm.push?.key === r.key;
          // o card destacado = melhor gold (recomendação principal)
          const best = isBestGold;
          return (
            <div className={"stage" + (best ? " best" : "")} key={r.key}>
              <div className="name">
                <span className={"diff " + r.tag}>{r.tag}</span>
                <span className="id">{r.label}</span>
                <span className="dim">{r.name}</span>
                {r.current && <span className="badge cur">atual</span>}
                {isBestGold && <span className="badge gold">★ melhor gold</span>}
                {isBestExp && <span className="badge exp">★ melhor exp</span>}
                {isPush && <span className="badge push">push</span>}
                {r.beyondCeiling && (
                  <span className="badge push">acima do teto</span>
                )}
                {r.type === "ACTBOSS" && <span className="badge cur">boss</span>}
              </div>
              <div className="metrics">
                <div className="m">
                  <span className="lbl">clear</span>
                  <span className="num">{fmtDur(r.clearTime)}</span>
                </div>
                <div className="m gold">
                  <span className="lbl">gold/h</span>
                  <span className="num">{fmt(r.goldPerHour)}</span>
                </div>
                <div className="m exp">
                  <span className="lbl">exp/h</span>
                  <span className="num">{fmt(r.expPerHour)}</span>
                </div>
                <div className="m">
                  <span className="lbl">perigo</span>
                  <span className={"rating " + r.rating}>{r.rating}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
