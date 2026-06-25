import React, { useMemo, useState } from "react";
import { fmt } from "../format.js";
import { gradeOf } from "../grades.js";
import { useT } from "../i18n.jsx";
import ItemIcon, { typeLabel } from "./ItemIcon.jsx";

const PAGE = 49; // stash do jogo é 7×7

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

function PreviewBar({ e, cube }) {
  const t = useT();
  const need = cube?.need;
  if (!e.ok || !need) return null;
  const exp = cube.exp;
  const eff = e.eff;
  const newExp = exp + eff;
  // simula subir até 2 níveis com 1 item (need atual + nextNeed)
  let gained = 0,
    rem = newExp;
  if (rem >= need) {
    gained = 1;
    rem -= need;
    if (cube.nextNeed && rem >= cube.nextNeed) {
      gained = 2;
      rem -= cube.nextNeed;
    }
  }
  const curPct = Math.min(100, (exp / need) * 100);
  const addPct = Math.min(100 - curPct, (eff / need) * 100);
  const toLevel = gained === 0 ? Math.max(1, Math.ceil((need - exp) / eff)) : null;
  return (
    <div className="cube-preview">
      <div className="cube-prev-head">{t("cube after Alchemizing this item", "cubo depois da Alquimia deste item")}</div>
      <div className="cube-prev-bar">
        <span className="seg-cur" style={{ width: curPct + "%" }} />
        <span className="seg-add" style={{ width: addPct + "%" }} />
      </div>
      <div className="cube-prev-text">
        {gained > 0 ? (
          <>
            <b className="v-exp">
              Lv {cube.level} → Lv {cube.level + gained}
            </b>{" "}
            <span className="muted">({t("leftover", "sobra")} {fmt(Math.round(rem))} EXP)</span>
          </>
        ) : (
          <>
            <b>{fmt(exp)}</b> + <b className="v-exp">{fmt(eff)}</b> ={" "}
            {fmt(Math.round(newExp))} / {fmt(need)}{" "}
            <span className="muted">({Math.round((newExp / need) * 100)}%)</span>
          </>
        )}
      </div>
      {toLevel != null && (
        <div className="cube-prev-sub muted small">
          {t("need ~", "faltam ~")}<b>{fmt(toLevel)}</b>{t(" of this item to go up 1 level", " deste item pra subir 1 nível")}
        </div>
      )}
    </div>
  );
}

function Detail({ e, cube, mult, top, onPick }) {
  const t = useT();
  if (!e)
    return (
      <div className="cube-detail empty">
        <div className="cube-prev-head">{t("Best items for alchemy at the current cube level", "Melhores itens para alquimia no nível do cubo atual")}</div>
        <div className="cube-top-list">
          {(top || []).map((it) => {
            const tg = gradeOf(it.grade);
            return (
              <button
                key={it.uid}
                className="cube-top-row"
                style={{ "--g": tg.c }}
                onClick={() => onPick && onPick(it)}
              >
                <ItemIcon e={it} size={30} />
                <span className="cube-top-name">{it.name}</span>
                <span className="muted small">L{it.level}</span>
                <b className="v-exp">{fmt(it.eff)}</b>
              </button>
            );
          })}
          {(!top || top.length === 0) && (
            <p className="muted small">{t("No alchemizable item.", "Nenhum item alquimizável.")}</p>
          )}
        </div>
      </div>
    );
  const g = gradeOf(e.grade);
  return (
    <div className="cube-detail" style={{ "--g": g.c }}>
      <div className="cube-detail-head">
        <ItemIcon e={e} size={56} />
        <div>
          <div className="cube-detail-name">{e.name}</div>
          <div className="cube-detail-tags">
            {g.special ? (
              <span className="grade-tag gtag special">{g.label}</span>
            ) : (
              <span className="grade-tag" style={{ color: g.c, borderColor: g.c }}>
                {g.label}
              </span>
            )}
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
            <span className="muted small">{t("cube EXP", "EXP de cubo")}</span>
          </div>
          <div className="cube-rows">
            <div className="cube-row">
              <i>{t("base EXP", "EXP base")}</i>
              <b>{fmt(e.base)}</b>
            </div>
            {e.match != null && (
              <div className="cube-row">
                <i>{t(`level matching (item Lv${e.level} × cube Lv${cube?.level})`, `level matching (item Lv${e.level} × cubo Lv${cube?.level})`)}</i>
                <b
                  className={
                    e.match < 0.5 ? "badge-red" : e.match >= 0.95 ? "badge-green" : ""
                  }
                >
                  {Math.round(e.match * 100)}%
                </b>
              </div>
            )}
            <div className="cube-row">
              <i>{t("your buff", "seu buff")}</i>
              <b className="v-exp">×{mult.toFixed(2)}</b>
            </div>
          </div>
          <PreviewBar e={e} cube={cube} />
        </>
      ) : (
        <p className="muted small" style={{ marginTop: 12 }}>
          {e.equipped
            ? t("Equipped — not used in Alchemy.", "Equipado — não entra na Alquimia.")
            : e.blocked
            ? t("Blocked — not used in Alchemy.", "Bloqueado — não entra na Alquimia.")
            : t("No cube value.", "Sem valor de cubo.")}
        </p>
      )}
    </div>
  );
}

export default function CubePanel({ alchemy }) {
  const t = useT();
  const [cid, setCid] = useState("stash");
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState(null);
  const [sort, setSort] = useState("none"); // none | exp | level
  const [onlyAlch, setOnlyAlch] = useState(false);

  const containers = alchemy?.containers || [];
  const cont = containers.find((c) => c.id === cid) || containers[0];

  const slots = useMemo(() => {
    if (!cont) return [];
    let s = cont.slots;
    if (sort !== "none" || onlyAlch) {
      s = s.filter((e) => e && (!onlyAlch || e.ok));
      if (sort === "exp") s = [...s].sort((a, b) => b.eff - a.eff);
      else if (sort === "level")
        s = [...s].sort((a, b) => (b.level || 0) - (a.level || 0));
    }
    return s;
  }, [cont, sort, onlyAlch]);

  // top itens (maior EXP efetivo) pra mostrar quando nada está selecionado
  const topItems = useMemo(
    () =>
      (containers.flatMap((c) => c.slots).filter((x) => x && x.ok) || [])
        .sort((a, b) => b.eff - a.eff)
        .slice(0, 6),
    [containers]
  );

  if (!alchemy)
    return (
      <main className="page no-rail">
        <div className="loading">
          {t("no cube data yet — run", "sem dados do cubo ainda — rode")} <code>python fetch_gamedata.py --force</code> {t("and reopen the panel.", "e reabra o painel.")}
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
      {/* header do cubo (largura total) */}
      <div className="cube-head">
          <div className="cube-badge">
            <span className="cube-badge-k">{t("Cube", "Cubo")}</span>
            <span className="cube-badge-lv">Lv {cube.level}</span>
          </div>
          <div className="cube-prog">
            <div className="cube-prog-top">
              <span>
                {fmt(cube.exp)} / {cube.maxed ? t("max", "máx") : fmt(cube.need)} EXP
              </span>
              <span className="muted">
                {cube.maxed ? t("max level", "nível máximo") : t(`${cube.pctToNext}% to next`, `${cube.pctToNext}% do próximo`)}
              </span>
            </div>
            <div className="cube-bar">
              <span style={{ width: `${cube.maxed ? 100 : cube.pctToNext}%` }} />
            </div>
          </div>
          <div className="cube-chips">
            <div className="cube-chip">
              <i>{t("EXP buff", "buff de EXP")}</i>
              <b className="v-exp">+{alchemy.buff.pct}%</b>
            </div>
            <div className="cube-chip">
              <i>{t("Alchemize everything", "Alquimia de tudo")}</i>
              <b>
                Lv {cube.level} → <span className="v-exp">Lv {proj.level}</span>
                {proj.gained > 0 && ` (+${proj.gained})`}
              </b>
            </div>
            <div className="cube-chip">
              <i>{t("EXP in inventory+stash", "EXP no inventário+stash")}</i>
              <b>{fmt(alchemy.sumAll)}</b>
            </div>
            {cube.recoLevel != null && (
              <div className="cube-chip cube-chip-reco">
                <i>{t("recommended gear level for alchemy", "nível de equip. recomendado p/ alquimia")}</i>
                <b className="cube-reco-val">
                  <span className="v-exp">Lv {cube.recoLevel}</span>
                  {cube.recoMatch != null && (
                    <span className="reco-pct">{t(`${cube.recoMatch}% matching`, `${cube.recoMatch}% matching`)}</span>
                  )}
                </b>
              </div>
            )}
          </div>
        </div>

      {/* split 50/50: stash à esquerda, item+preview à direita */}
      <div className="cube-split">
        <div className="cube-left">
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
              className={"cube-toggle" + (sort === "exp" ? " on" : "")}
              onClick={() => {
                setSort((v) => (v === "exp" ? "none" : "exp"));
                setPage(0);
              }}
            >
              {t("sort by EXP", "ordenar por EXP")}
            </button>
            <button
              className={"cube-toggle" + (sort === "level" ? " on" : "")}
              onClick={() => {
                setSort((v) => (v === "level" ? "none" : "level"));
                setPage(0);
              }}
            >
              {t("sort by level", "ordenar por level")}
            </button>
            <button
              className={"cube-toggle" + (onlyAlch ? " on" : "")}
              onClick={() => {
                setOnlyAlch((v) => !v);
                setPage(0);
              }}
            >
              {t("alchemizable only", "só alquimizáveis")}
            </button>
          </div>
        </div>

        {cont && (
          <div className="cube-sub muted small">
            {cont.alchCount} {t("alchemizable", "alquimizáveis")} ·{" "}
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
        <aside className="cube-right">
          <Detail e={sel} cube={cube} mult={mult} top={topItems} onPick={setSel} />
        </aside>
      </div>
    </main>
  );
}
