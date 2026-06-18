import React, { useMemo, useState, useRef, useEffect } from "react";
import { fmt } from "../format.js";
import { fmtStatDelta } from "../statNames.js";
import { gradeOf, gearPt } from "../grades.js";
import { useT } from "../i18n.jsx";

// opção de fase: chip de dificuldade colorido + id em mono + nome
function StageOpt({ o }) {
  const t = useT();
  return (
    <span className="stage-opt">
      <span className={"diff " + o.tag}>{o.tag}</span>
      <span className="so-id num">{o.label}</span>
      <span className="dim so-name">{o.name}</span>
      <span className="dim num so-lv">Lv{o.lvl}</span>
      {o.current && <span className="badge cur">{t("current", "atual")}</span>}
    </span>
  );
}

// dropdown pixel custom (o <select> nativo não renderiza cor/símbolo nas options)
function StageSelect({ options, value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  const sel = options.find((o) => o.key === value) || options[0];
  return (
    <div className={"pix-select" + (open ? " open" : "")} ref={ref}>
      <button type="button" className="pix-select-btn" onClick={() => setOpen((o) => !o)}>
        {sel ? <StageOpt o={sel} /> : <span className="dim">—</span>}
        <span className="pix-caret">▾</span>
      </button>
      {open && (
        <div className="pix-select-list">
          {options.map((o) => (
            <button
              type="button"
              key={o.key}
              className={"pix-opt" + (o.key === value ? " on" : "")}
              onClick={() => {
                onChange(o.key);
                setOpen(false);
              }}
            >
              <StageOpt o={o} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function RoleTag({ role }) {
  if (!role) return null;
  const cls = { tank: "r-tank", dps: "r-dps", healer: "r-heal" }[role] || "r-dps";
  return <span className={"role-tag " + cls}>{role}</span>;
}

function Item({ it }) {
  const t = useT();
  if (!it) return <span className="muted">{t("empty", "vazio")}</span>;
  const g = gradeOf(it.grade);
  // Cosmic (special) = holo: gradiente no nome em vez de cor flat.
  const nameStyle = g.special
    ? {
        background: "linear-gradient(90deg, #54b9ff, #c06bff, #ffd23f)",
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        color: "transparent",
      }
    : { color: g.c };
  return (
    <span>
      <span style={nameStyle}>{it.name}</span>{" "}
      <span className="muted">{t("lvl", "lvl")} {it.level}</span>
    </span>
  );
}

function SwapRow({ cls, role, slot }) {
  const u = slot.upgrade;
  return (
    <div className="gear-row">
      <div className="gear-slot">
        {cls} <RoleTag role={role} /> · {gearPt(slot.gearType)}
      </div>
      <div className="gear-swap">
        <Item it={slot.current} /> <span className="arrow">→</span>{" "}
        <Item it={u} />
      </div>
      {u.statDiff?.length > 0 && (
        <div className="gear-stats">
          {u.statDiff.map((d, j) => (
            <span key={j} className={"stat-chip" + (d.delta < 0 ? " neg" : "")}>
              {fmtStatDelta(d)}
            </span>
          ))}
        </div>
      )}
      <div className="gear-effect">
        {u.dDps !== 0 && (
          <span className={u.dDps > 0 ? "badge-green" : "badge-red"}>
            {u.dDps > 0 ? "+" : ""}{fmt(u.dDps)} dps
          </span>
        )}
        {u.dEhp !== 0 && (
          <span className={u.dEhp > 0 ? "badge-green" : "badge-red"}>
            {u.dEhp > 0 ? "+" : ""}{fmt(u.dEhp)} ehp
          </span>
        )}
      </div>
    </div>
  );
}

// achata os heróis -> uma lista de trocas, ordenada por ganho de power
function flatten(heroes) {
  const out = [];
  for (const h of heroes || [])
    for (const s of h.slots || [])
      if (s.upgrade) out.push({ cls: h.cls, role: h.role, slot: s });
  out.sort((a, b) => b.slot.upgrade.dPower - a.slot.upgrade.dPower);
  return out;
}

export default function GearPanel({ gear }) {
  const t = useT();
  const byStage = gear?.byStage || [];
  const [stageKey, setStageKey] = useState(null);
  const sel = useMemo(() => {
    if (!byStage.length) return null;
    const k = stageKey ?? (byStage.find((s) => s.current) || byStage[0]).key;
    return byStage.find((s) => s.key === k) || byStage[0];
  }, [byStage, stageKey]);

  const general = flatten(gear?.general);
  const stageSwaps = sel ? flatten(sel.heroes) : [];

  return (
    <>
      {/* 1) UPGRADES DIRETOS — item é melhor no geral, independe da fase (TOPO) */}
      <section className="sec">
        <h2>{t("Gear — direct upgrades", "Gear — upgrades diretos")}</h2>
        <p className="lbl" style={{ marginBottom: 10 }}>
          {t("Items that are better overall", "Itens que são melhores no geral")}
        </p>
        {general.length > 0 ? (
          <div className="gear-list">
            {general.map((u, i) => (
              <SwapRow key={i} {...u} />
            ))}
          </div>
        ) : (
          <p className="muted">{t("No better swap in your inventory. Everything optimized.", "Nenhuma troca melhor no inventário. Tudo otimizado.")}</p>
        )}
      </section>

      {/* 2) BUILD PRA UMA FASE — escolhe a fase, vê o que trocar pra aguentá-la */}
      <section className="sec">
        <h2>{t("Gear — build for a stage", "Gear — build pra uma fase")}</h2>
        <div className="gear-stage-pick">
          <span className="lbl">{t("Choose the stage", "Escolha a fase")}</span>
          <StageSelect
            options={byStage}
            value={sel?.key}
            onChange={(k) => setStageKey(k)}
          />
        </div>
        {stageSwaps.length > 0 ? (
          <div className="gear-list">
            {stageSwaps.map((u, i) => (
              <SwapRow key={i} {...u} />
            ))}
          </div>
        ) : (
          <p className="muted">
            {t("Nothing in your inventory improves the team for this stage. Check the skill/rune tree or level up your items.", "Nada no inventário melhora o time pra essa fase. Veja a árvore de skill/runas ou suba o nível dos itens.")}
          </p>
        )}
      </section>
    </>
  );
}
