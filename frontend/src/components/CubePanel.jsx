import React, { useMemo, useState } from "react";
import { fmt } from "../format.js";

/* cores/labels por grau — escala de raridade (é o que mais dita o EXP de cubo) */
const GRADES = {
  COMMON: { label: "Comum", c: "#9aa6b2" },
  UNCOMMON: { label: "Incomum", c: "#56c777" },
  RARE: { label: "Raro", c: "#4f9cf0" },
  LEGENDARY: { label: "Lendário", c: "#b06bf0" },
  IMMORTAL: { label: "Imortal", c: "#f0863b" },
  ARCANA: { label: "Arcana", c: "#f5d24a" },
  BEYOND: { label: "Além", c: "#38d9cf" },
  CELESTIAL: { label: "Celestial", c: "#7ad7ff" },
  DIVINE: { label: "Divino", c: "#ff9ec7" },
  COSMIC: { label: "Cósmico", c: "#ff6b6b" },
};
const GEAR_PT = {
  SWORD: "Espada", AXE: "Machado", BOW: "Arco", CROSSBOW: "Besta",
  SCEPTER: "Cetro", STAFF: "Cajado", ARROW: "Flecha", BOLT: "Virote",
  ORB: "Orbe", SHIELD: "Escudo", HATCHET: "Machadinha", TOME: "Tomo",
  ARMOR: "Armadura", HELMET: "Elmo", GLOVES: "Luvas", BOOTS: "Botas",
  AMULET: "Amuleto", EARING: "Brinco", RING: "Anel", BRACER: "Bracelete",
};
const gradeOf = (g) => GRADES[g] || { label: g || "—", c: "#768192" };
const typeLabel = (e) =>
  e.type === "GEAR" ? GEAR_PT[e.gear] || e.gear : e.type === "MATERIAL" ? "Material" : e.type;
const PAGE = 56;

function ItemIcon({ e, size = 40 }) {
  const [bad, setBad] = useState(false);
  const g = gradeOf(e.grade);
  if (bad || !e.key)
    return (
      <span className="cube-ico-fallback" style={{ width: size, height: size, color: g.c }}>
        {typeLabel(e).slice(0, 2)}
      </span>
    );
  return (
    <img
      className="cube-ico"
      style={{ width: size, height: size }}
      src={`/itemicon/${e.key}.png`}
      alt=""
      loading="lazy"
      onError={() => setBad(true)}
    />
  );
}

function Cell({ e, selected, onClick }) {
  if (!e) return <div className="cube-cell empty" />;
  const g = gradeOf(e.grade);
  return (
    <button
      className={"cube-cell" + (selected ? " sel" : "") + (e.ok ? "" : " locked")}
      style={{ "--g": g.c }}
      onClick={onClick}
      title={`${e.name} · ${g.label} ${typeLabel(e)} L${e.level ?? "—"}`}
    >
      <ItemIcon e={e} />
      {e.level != null && <span className="cube-lv">{e.level}</span>}
      <span className="cube-exp">{e.ok ? fmt(e.eff) : "—"}</span>
      {!e.ok && <span className="cube-lock">{e.equipped ? "eq" : "🔒"}</span>}
    </button>
  );
}

function Detail({ e, cube, mult }) {
  if (!e)
    return (
      <div className="cube-detail empty">
        <p className="muted small">
          Clique num item pra ver o EXP que ele dá ao cubo. As células são
          coloridas por <b>grau</b> e mostram o EXP (com seus buffs) embaixo.
        </p>
        <p className="muted small" style={{ marginTop: 10 }}>
          O EXP depende de <b>grau × tipo de gear × nível do item</b> — <i>não</i> do
          nível do cubo. Por isso um Raro L30 pode dar mais que um Comum L50.
        </p>
      </div>
    );
  const g = gradeOf(e.grade);
  const need = cube?.need;
  const pctOfLevel = e.ok && need ? (e.eff / need) * 100 : null;
  const toLevel =
    e.ok && need && cube ? Math.max(1, Math.ceil((need - cube.exp) / e.eff)) : null;
  return (
    <div className="cube-detail" style={{ "--g": g.c }}>
      <div className="cube-detail-head">
        <ItemIcon e={e} size={56} />
        <div>
          <div className="cube-detail-name">{e.name}</div>
          <div className="cube-detail-tags">
            <span className="grade-tag" style={{ color: g.c, borderColor: g.c }}>
              {g.label}
            </span>
            <span className="muted small">
              {typeLabel(e)} · L{e.level ?? "—"}
            </span>
          </div>
        </div>
      </div>

      {e.ok ? (
        <>
          <div className="cube-eff">
            <span className="cube-eff-num">{fmt(e.eff)}</span>
            <span className="muted small">EXP de cubo</span>
          </div>
          <div className="cube-rows">
            <div className="cube-row">
              <i>EXP base</i>
              <b>{fmt(e.base)}</b>
            </div>
            <div className="cube-row">
              <i>seu buff</i>
              <b className="v-exp">×{mult.toFixed(2)}</b>
            </div>
            {pctOfLevel != null && (
              <div className="cube-row">
                <i>do nível atual do cubo</i>
                <b>{pctOfLevel < 0.1 ? "<0,1" : pctOfLevel.toFixed(1)}%</b>
              </div>
            )}
            {toLevel != null && (
              <div className="cube-row">
                <i>faltam ~deste item p/ subir</i>
                <b>{fmt(toLevel)}</b>
              </div>
            )}
          </div>
        </>
      ) : (
        <p className="muted small" style={{ marginTop: 12 }}>
          {e.equipped
            ? "Equipado — não pode ser alquimizado."
            : e.blocked
            ? "Bloqueado — não pode ser alquimizado."
            : "Sem valor de cubo."}
        </p>
      )}
    </div>
  );
}

export default function CubePanel({ alchemy }) {
  const [cid, setCid] = useState("stash");
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState(null);
  const [sortExp, setSortExp] = useState(false);
  const [onlyAlch, setOnlyAlch] = useState(false);

  const containers = alchemy?.containers || [];
  const cont = containers.find((c) => c.id === cid) || containers[0];

  const slots = useMemo(() => {
    if (!cont) return [];
    let s = cont.slots;
    if (sortExp || onlyAlch) {
      s = s.filter((e) => e && (!onlyAlch || e.ok));
      if (sortExp) s = [...s].sort((a, b) => b.eff - a.eff);
    }
    return s;
  }, [cont, sortExp, onlyAlch]);

  if (!alchemy)
    return (
      <main className="page no-rail">
        <div className="loading">
          sem dados do cubo ainda — rode <code>python fetch_gamedata.py --force</code> e
          reabra o painel.
        </div>
      </main>
    );

  const cube = alchemy.cube;
  const mult = alchemy.buff?.mult ?? 1;
  const pages = Math.max(1, Math.ceil(slots.length / PAGE));
  const pg = Math.min(page, pages - 1);
  const view = slots.slice(pg * PAGE, pg * PAGE + PAGE);
  const proj = alchemy.projectAll;

  return (
    <main className="page cube-page no-rail">
      <div className="cube-main">
        {/* header do cubo */}
        <div className="cube-head">
          <div className="cube-badge">
            <span className="cube-badge-k">Cubo</span>
            <span className="cube-badge-lv">Lv {cube.level}</span>
          </div>
          <div className="cube-prog">
            <div className="cube-prog-top">
              <span>
                {fmt(cube.exp)} / {cube.maxed ? "máx" : fmt(cube.need)} EXP
              </span>
              <span className="muted">
                {cube.maxed ? "nível máximo" : `${cube.pctToNext}% do próximo`}
              </span>
            </div>
            <div className="cube-bar">
              <span style={{ width: `${cube.maxed ? 100 : cube.pctToNext}%` }} />
            </div>
          </div>
          <div className="cube-chips">
            <div className="cube-chip">
              <i>buff de EXP</i>
              <b className="v-exp">+{alchemy.buff.pct}%</b>
            </div>
            <div className="cube-chip">
              <i>alquimizar tudo</i>
              <b>
                Lv {cube.level} → <span className="v-exp">Lv {proj.level}</span>
                {proj.gained > 0 && ` (+${proj.gained})`}
              </b>
            </div>
            <div className="cube-chip">
              <i>EXP no inventário+stash</i>
              <b>{fmt(alchemy.sumAll)}</b>
            </div>
          </div>
        </div>

        {/* controles: containers + ordenação */}
        <div className="cube-bar-row">
          <div className="cube-tabs">
            {containers.map((c) => (
              <button
                key={c.id}
                className={"cube-tab" + (c.id === (cont?.id) ? " active" : "")}
                onClick={() => {
                  setCid(c.id);
                  setPage(0);
                  setSel(null);
                }}
              >
                {c.label}
                <span className="cube-tab-n">{c.filled}</span>
              </button>
            ))}
          </div>
          <div className="cube-toggles">
            <button
              className={"cube-toggle" + (sortExp ? " on" : "")}
              onClick={() => {
                setSortExp((v) => !v);
                setPage(0);
              }}
            >
              ordenar por EXP
            </button>
            <button
              className={"cube-toggle" + (onlyAlch ? " on" : "")}
              onClick={() => {
                setOnlyAlch((v) => !v);
                setPage(0);
              }}
            >
              só alquimizáveis
            </button>
          </div>
        </div>

        {cont && (
          <div className="cube-sub muted small">
            {cont.alchCount} alquimizáveis ·{" "}
            <span className="v-exp">{fmt(cont.sumEff)}</span> EXP → Lv {cont.project.level}
            {cont.project.gained > 0 && ` (+${cont.project.gained})`}
          </div>
        )}

        {/* grade estilo stash */}
        <div className="cube-grid">
          {view.map((e, i) => (
            <Cell
              key={(e && e.uid) || "e" + (pg * PAGE + i)}
              e={e}
              selected={e && sel && e.uid === sel.uid}
              onClick={() => e && setSel(e)}
            />
          ))}
        </div>

        {pages > 1 && (
          <div className="cube-pages">
            {Array.from({ length: pages }, (_, i) => (
              <button
                key={i}
                className={"cube-pg" + (i === pg ? " active" : "")}
                onClick={() => setPage(i)}
              >
                {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>

      <aside className="cube-side">
        <Detail e={sel} cube={cube} mult={mult} />
      </aside>
    </main>
  );
}
