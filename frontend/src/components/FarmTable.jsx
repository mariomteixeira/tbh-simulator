import React, { useMemo, useState } from "react";
import { fmt, fmtDur } from "../format.js";

const DIFFS = ["todas", "N", "NM", "H", "T"];
const COLS = [
  { key: "label", label: "Estágio", num: false },
  { key: "lvl", label: "Lvl", num: true },
  { key: "clearTime", label: "Clear", num: true },
  { key: "goldPerHour", label: "Gold/h", num: true },
  { key: "expPerHour", label: "Exp/h", num: true },
  { key: "danger", label: "Perigo", num: true },
];

export default function FarmTable({ farm }) {
  const [sort, setSort] = useState({ key: "goldPerHour", dir: -1 });
  const [diff, setDiff] = useState("todas");
  const [all, setAll] = useState(false);

  const rows = useMemo(() => {
    // runs de boss de ato nao sao farmaveis em loop: fora da tabela
    let r = (farm.rows || []).filter((x) => x.type !== "ACTBOSS");
    // por padrao so fases que voce CONSEGUE clearar (limpas) + o push (se houver);
    // "ver todas" libera as nao-limpas pra referencia
    if (!all) r = r.filter((x) => x.cleared || x.key === farm.push?.key);
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

  return (
    <section className="sec">
      <div className="sec-head">
        <h2>Farm — taxas reais por estágio</h2>
        <div className="chips">
          {DIFFS.map((dd) => (
            <button
              key={dd}
              className={"chip" + (diff === dd ? " active" : "")}
              onClick={() => setDiff(dd)}
            >
              {dd}
            </button>
          ))}
          <button className={"chip" + (all ? " active" : "")} onClick={() => setAll(!all)}>
            {all ? "ver top" : "ver todas"}
          </button>
        </div>
      </div>
      <table className="farm">
        <thead>
          <tr>
            {COLS.map((c) => (
              <th
                key={c.key}
                className={c.num ? "num" : ""}
                onClick={() => clickSort(c.key)}
              >
                {c.label}
                {sort.key === c.key ? (sort.dir < 0 ? " ▾" : " ▴") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.current ? "is-current" : ""}>
              <td>
                <span className={"diff-tag t-" + r.tag}>{r.tag}</span>{" "}
                <b>{r.label}</b> <span className="muted">{r.name}</span>
                {r.current && <span className="mark cur">atual</span>}
                {farm.bestGold?.key === r.key && <span className="mark gold">melhor gold</span>}
                {farm.bestExp?.key === r.key && <span className="mark exp">melhor exp</span>}
                {farm.push?.key === r.key && <span className="mark push">push</span>}
                {r.type === "ACTBOSS" && <span className="mark boss">boss</span>}
              </td>
              <td className="num">{r.lvl}</td>
              <td className="num">{fmtDur(r.clearTime)}</td>
              <td className="num v-gold">{fmt(r.goldPerHour)}</td>
              <td className="num v-exp">{fmt(r.expPerHour)}</td>
              <td className="num">
                <span className={"rating r-" + r.rating}>{r.rating}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
