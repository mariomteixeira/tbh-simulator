import React, { useEffect, useMemo, useState } from "react";
import { gradeOf } from "../grades.js";
import { useT, useLang } from "../i18n.jsx";
import ItemIcon, { typeLabel } from "./ItemIcon.jsx";

const PAGE = 49; // 7×7 como o stash

const brl = (cents) =>
  cents == null
    ? "—"
    : (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function Cell({ e, selected, onClick }) {
  if (!e) return <div className="cube-cell empty" />;
  const g = gradeOf(e.grade);
  return (
    <button
      className={"cube-cell" + (selected ? " sel" : "") + (e.matched ? "" : " locked")}
      style={{ "--g": g.c }}
      onClick={onClick}
      title={`${e.name} · ${g.label} ${typeLabel(e)}`}
    >
      <ItemIcon e={e} />
      {e.level != null && <span className="cube-lv">{e.level}</span>}
      <span className="cube-exp mk-price">{e.matched ? brl(e.listed) : e.pending ? "…" : "—"}</span>
    </button>
  );
}

function Detail({ e, fee, cooldown, appid }) {
  const t = useT();
  if (!e)
    return (
      <div className="cube-detail empty">
        <p className="muted small">{t("Select an item to see its Steam value.", "Selecione um item para ver o valor na Steam.")}</p>
      </div>
    );
  const g = gradeOf(e.grade);
  const url = e.hashName
    ? `https://steamcommunity.com/market/listings/${appid}/${encodeURIComponent(e.hashName)}`
    : null;
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
              <span className="grade-tag" style={{ color: g.c, borderColor: g.c }}>{g.label}</span>
            )}
            <span className="muted small">{typeLabel(e)}{e.level != null ? ` · L${e.level}` : ""}</span>
          </div>
        </div>
      </div>

      {!e.marketable ? (
        <p className="muted small" style={{ marginTop: 12 }}>
          {t("Not tradable on the Steam Market.", "Não negociável no Steam Market.")}
        </p>
      ) : e.matched ? (
        <>
          <div className="cube-rows">
            <div className="cube-row">
              <i>{t("listed price", "preço listado")}</i>
              <b>{brl(e.listed)}</b>
            </div>
            <div className="cube-row">
              <i>{t(`you receive (−${fee}%)`, `você recebe (−${fee}%)`)}</i>
              <b className="v-gold">{brl(e.receive)}</b>
            </div>
            <div className="cube-row">
              <i>{t("tradeship cooldown", "cooldown do tradeship")}</i>
              <b>{cooldown}h</b>
            </div>
          </div>
          {url && (
            <a className="mk-link" href={url} target="_blank" rel="noreferrer">
              {t("open on Steam Market", "abrir no Steam Market")}
            </a>
          )}
        </>
      ) : e.pending ? (
        <p className="muted small" style={{ marginTop: 12 }}>
          {t("fetching price…", "buscando preço…")}
        </p>
      ) : (
        <p className="muted small" style={{ marginTop: 12 }}>
          {t("Not listed on the Steam Market.", "Não listado no Steam Market.")}
        </p>
      )}
    </div>
  );
}

export default function MarketPage() {
  const t = useT();
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [cid, setCid] = useState("stash");
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState(null);
  const [sortVal, setSortVal] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`/api/market?lang=${lang}`)
        .then((r) => r.json())
        .then((d) => { if (alive) { setData(d); setErr(d.error || null); } })
        .catch((e) => { if (alive) setErr(String(e)); });
    load();
    const id = setInterval(load, 6000); // worker preenche ~1 preço/3s; recarrega pra mostrar
    return () => { alive = false; clearInterval(id); };
  }, [lang]);

  const containers = data?.containers || [];
  const cont = containers.find((c) => c.id === cid) || containers[0];

  const slots = useMemo(() => {
    if (!cont) return [];
    if (!sortVal) return cont.slots; // ordem nativa (igual cubo) — cada página = 1 aba do stash
    return cont.slots.filter(Boolean).sort((a, b) => (b.receive || 0) - (a.receive || 0));
  }, [cont, sortVal]);

  if (!data && !err)
    return <main className="page no-rail"><div className="loading">{t("loading…", "carregando…")}</div></main>;
  if (err)
    return <main className="page no-rail"><div className="loading">{err}</div></main>;

  const pages = Math.max(1, Math.ceil(slots.length / PAGE));
  const pg = Math.min(page, pages - 1);
  const view = slots.slice(pg * PAGE, pg * PAGE + PAGE);

  return (
    <main className="page cube-page no-rail">
      <div className="cube-split">
        <div className="cube-left">
          <div className="cube-bar-row">
            <div className="cube-tabs">
              {containers.map((c) => (
                <button
                  key={c.id}
                  className={"cube-tab" + (c.id === cont?.id ? " active" : "")}
                  onClick={() => { setCid(c.id); setPage(0); setSel(null); }}
                >
                  {c.id === "inventory" ? t("Inventory", "Inventário")
                    : c.id === "stash" ? "Stash"
                    : t("Trade stash", "Stash de troca")}
                  <span className="cube-tab-n">{c.filled}</span>
                </button>
              ))}
            </div>
            <div className="cube-toggles">
              <button
                className={"cube-toggle" + (sortVal ? " on" : "")}
                onClick={() => { setSortVal((v) => !v); setPage(0); }}
              >
                {t("sort by value", "ordenar por valor")}
              </button>
            </div>
          </div>

          {cont && (
            <div className="cube-sub muted small">
              {cont.matched}/{cont.tradable} {t("priced", "com preço")} ·{" "}
              <span className="v-gold">{brl(cont.sumReceive)}</span> {t("if you sell all", "vendendo tudo")}
              {cont.pending > 0 && <span className="muted"> · {cont.pending} {t("loading…", "carregando…")}</span>}
            </div>
          )}

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
                <button key={i} className={"cube-pg" + (i === pg ? " active" : "")} onClick={() => setPage(i)}>
                  {i + 1}
                </button>
              ))}
            </div>
          )}
        </div>
        <aside className="cube-right">
          <Detail e={sel} fee={data.feePct} cooldown={data.cooldownHours} appid={data.appid} />
        </aside>
      </div>
    </main>
  );
}
