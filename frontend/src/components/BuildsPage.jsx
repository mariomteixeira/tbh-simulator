import React, { useEffect, useMemo, useRef, useState } from "react";
import { fmt } from "../format.js";
import { gradeOf, gearPt } from "../grades.js";

/* rótulos curtos de stat (p/ filtro de buff + nomes) */
const STAT_PT = {
  AttackDamage: "Dano", AttackSpeed: "Vel. ataque", CastSpeed: "Vel. cast",
  CriticalChance: "Crítico", CriticalDamage: "Dano crít.", CooldownReduction: "Recarga",
  MaxHp: "HP", Armor: "Armadura", MovementSpeed: "Mov.", BlockChance: "Block",
  DodgeChance: "Esquiva", ElementalDodgeChance: "Esquiva elem.",
  HpRegenPerSec: "Regen", AddHpPerHit: "Cura/hit", HpLeech: "Roubo vida",
  SkillHealIncrease: "Cura", DamageAbsorption: "Absorção", DamageReduction: "Redução",
  ChaosResistance: "Resist. caos", FireResistance: "Resist. fogo",
  ColdResistance: "Resist. gelo", LightningResistance: "Resist. raio",
  PhysicalResistance: "Resist. físico", AllElementalResistance: "Resist. elem.",
  "PhysicalDamagePercent": "Dano físico", "FireDamagePercent": "Dano fogo",
  "ColdDamagePercent": "Dano gelo", "LightningDamagePercent": "Dano raio",
  "ChaosDamagePercent": "Dano caos", AreaOfEffect: "Área",
};
const statPt = (s) => STAT_PT[s] || s;

const SLOT_PT = {
  BOW: "Arco", ARROW: "Flecha", SWORD: "Espada", AXE: "Machado", STAFF: "Cajado",
  SCEPTER: "Cetro", ORB: "Orbe", SHIELD: "Escudo", TOME: "Tomo", BOLT: "Virote",
  CROSSBOW: "Besta", HATCHET: "Machadinha",
  HELMET: "Elmo", ARMOR: "Armadura", GLOVES: "Luvas", BOOTS: "Botas",
  AMULET: "Amuleto", EARING: "Brinco", RING: "Anel", BRACER: "Bracelete",
};
const slotPt = (s) => SLOT_PT[s] || gearPt(s) || s;

const CAT_OF = {
  BOW: "WEAPON", ARROW: "WEAPON", SWORD: "WEAPON", AXE: "WEAPON", STAFF: "WEAPON",
  SCEPTER: "WEAPON", ORB: "WEAPON", SHIELD: "WEAPON", TOME: "WEAPON", BOLT: "WEAPON",
  CROSSBOW: "WEAPON", HATCHET: "WEAPON",
  HELMET: "ARMOR", ARMOR: "ARMOR", GLOVES: "ARMOR", BOOTS: "ARMOR",
  AMULET: "ACCESSORY", EARING: "ACCESSORY", RING: "ACCESSORY", BRACER: "ACCESSORY",
};
const catOf = (gt) => CAT_OF[gt] || "WEAPON";
const catPt = (c) => (c === "WEAPON" ? "arma" : c === "ARMOR" ? "armadura" : "acessório");

const SOCK_SYM = { deco: "◆", engr: "❖", inscr: "§" };
const TIER_ORDER = ["COMMON", "UNCOMMON", "RARE", "LEGENDARY", "IMMORTAL",
  "ARCANA", "BEYOND", "CELESTIAL", "DIVINE", "COSMIC"];
const LVL_MAX = 100;

/* ícone do item (backend serve /itemicon); cai para tile de iniciais */
function ItemIco({ k, name, grade, cls = "ico" }) {
  const [bad, setBad] = useState(false);
  const g = gradeOf(grade);
  if (bad || !k)
    return <span className={cls + " ico-fb"} style={{ "--g": g.c }}>{(name || "?").slice(0, 2).toUpperCase()}</span>;
  return <img className={cls} style={{ "--g": g.c }} src={`/itemicon/${k}.png`} alt=""
    loading="lazy" onError={() => setBad(true)} />;
}
function HeroIco({ k, name, cls = "ico" }) {
  const [bad, setBad] = useState(false);
  if (bad || !k)
    return <span className={cls + " ico-fb"}>{(name || "?").slice(0, 2).toUpperCase()}</span>;
  return <img className={cls} src={`/heroicon/${k}.png`} alt="" onError={() => setBad(true)} />;
}

function RoleTag({ role }) {
  const cls = { tank: "r-tank", dps: "r-dps", healer: "r-healer" }[role] || "r-dps";
  return <span className={"role-tag " + cls}>{role}</span>;
}

/* ---------------- roster ---------------- */
function Roster({ builds, onPick }) {
  const list = useMemo(
    () => [...builds].sort((a, b) =>
      (b.fielded ? 1 : 0) - (a.fielded ? 1 : 0) || (b.level || 0) - (a.level || 0)),
    [builds]
  );
  return (
    <main className="page builds-page no-rail">
      <h1>Builds</h1>
      <div className="roster">
        {list.map((h) => (
          <div
            key={h.key}
            className={"bcard " + (h.fielded ? "fielded" : "bench")}
            tabIndex={0}
            onClick={() => onPick(h.key)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onPick(h.key))}
          >
            <div className="bcard-head">
              <HeroIco k={h.key} name={h.name} cls="spr-ico" />
              <div className="bcard-id">
                <span className="bcard-name">{h.name}</span>
                <span className="bcard-sub"><RoleTag role={h.role} /></span>
              </div>
              <span className={"bcard-lv" + (h.fielded ? "" : " bench")}>
                {h.level != null ? "Lv " + h.level : "reserva"}
              </span>
            </div>
            <div className="bcard-stats">
              <div className="bstat"><i>DPS</i><b className="dps">{fmt(h.dps)}</b></div>
              <div className="bstat"><i>EHP</i><b className="ehp">{fmt(h.ehp)}</b></div>
              <div className="bstat"><i>HP</i><b>{fmt(h.stats?.MaxHp || 0)}</b></div>
              <div className="bstat"><i>Crit</i><b>{((h.stats?.CriticalChance || 0) / 10).toFixed(1)}%</b></div>
            </div>
            <div className="bcard-foot">
              <span>{h.fielded ? "em campo" : "reserva"}</span>
              <span className="bcard-cta">{h.fielded ? "editar build ▸" : "ver build ▸"}</span>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

/* ---------------- editor ---------------- */
const GROUPS = [
  { label: "Arma", cat: "WEAPON" },
  { label: "Armadura", cat: "ARMOR" },
  { label: "Acessórios", cat: "ACCESSORY" },
];
/* posição no paper-doll por categoria/ordem (col,row); preenchido em runtime */
const DOLL_COL = { WEAPON: [1, 2], ARMOR: [1, 2], ACCESSORY: [4, 5] };

function Editor({ build, catalog, ownedSet, onBack }) {
  const [work, setWork] = useState(() =>
    build.loadout.filter((s) => s.itemKey).map((s) => ({ ...s, sockets: s.sockets.map((k) => ({ ...k })) }))
  );
  const [selIdx, setSelIdx] = useState(0);
  const [tab, setTab] = useState("item");
  const [filt, setFilt] = useState({ lvlMin: 1, lvlMax: LVL_MAX, search: "", tiers: new Set(), stats: new Set(), invOnly: false });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  // recompute (debounced) sempre que o loadout mudar
  useEffect(() => {
    const spec = work.map((s) => ({ itemKey: s.itemKey, sockets: s.sockets.map((k) => ({ stat: k.stat, mod: k.mod, value: k.value })) }));
    const t = setTimeout(() => {
      setBusy(true);
      fetch("/api/whatif", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ heroKey: build.key, loadout: spec }),
      })
        .then((r) => r.json())
        .then((d) => { if (d && !d.error) setResult(d); })
        .catch(() => {})
        .finally(() => setBusy(false));
    }, 180);
    return () => clearTimeout(t);
  }, [work, build.key]);

  const slot = work[selIdx];
  const cat = slot ? catOf(slot.gearType) : "WEAPON";
  const cap = (catalog?.slotsByGrade?.[slot?.grade]) || { deco: 0, engr: 0, inscr: 0 };
  const base = build;                 // baseline = build atual (sim)
  const cur = result || base;         // valores mostrados (recalculados)
  const dDps = result ? result.dps - base.dps : 0;
  const dEhp = result ? result.ehp - base.ehp : 0;

  function selectSlot(i) {
    setSelIdx(i); setTab("item");
    setFilt({ lvlMin: 1, lvlMax: LVL_MAX, search: "", tiers: new Set(), stats: new Set(), invOnly: false });
  }
  function update(mut) {
    setWork((w) => { const nw = w.map((s) => ({ ...s, sockets: s.sockets.map((k) => ({ ...k })) })); mut(nw); return nw; });
  }
  function removeSock(k) { update((nw) => { nw[selIdx].sockets.splice(k, 1); }); }
  function equipGem(row) {
    const eff = row.eff;
    if (!eff) return;
    update((nw) => {
      nw[selIdx].sockets.push({ type: tab, stat: eff.stat, mod: eff.mod, value: eff.max, gemKey: row.itemKey, gemName: row.name });
    });
  }
  function equipItem(it) {
    update((nw) => {
      const s = nw[selIdx];
      const ncap = (catalog?.slotsByGrade?.[it.grade]) || { deco: 0, engr: 0, inscr: 0 };
      ["deco", "engr", "inscr"].forEach((t) => {
        const same = s.sockets.filter((x) => x.type === t);
        let extra = same.length - ncap[t];
        while (extra-- > 0) { const last = s.sockets.map((x, i) => [x, i]).filter(([x]) => x.type === t).pop(); s.sockets.splice(last[1], 1); }
      });
      s.item = it.name; s.grade = it.grade; s.level = it.level; s.itemKey = it.itemKey;
    });
  }
  function reset() {
    setWork(build.loadout.filter((s) => s.itemKey).map((s) => ({ ...s, sockets: s.sockets.map((k) => ({ ...k })) })));
    setResult(null); setSelIdx(0); setTab("item");
  }

  return (
    <main className="page builds-page no-rail">
      <div className="builds-crumb">
        <button className="link-back" onClick={onBack}>‹ Equipe</button>
        <span className="bc-sep">/</span>
        <span className="bc-here">{build.name}</span>
      </div>
      <div className="editor">
        {/* ESQUERDA: lista do slot selecionado */}
        <Catalog
          slot={slot} cat={cat} cap={cap} tab={tab} setTab={setTab}
          filt={filt} setFilt={setFilt} catalog={catalog} ownedSet={ownedSet}
          onEquipItem={equipItem} onEquipGem={equipGem}
        />
        {/* DIREITA: card do personagem + dados */}
        <aside className="card">
          <Doll build={build} work={work} cap={catalog?.slotsByGrade} selIdx={selIdx} onSelect={selectSlot} />
          <SelSock slot={slot} cap={cap} onRemove={removeSock} />
          <div className="kpis2">
            <div className="kpi2 dps">
              <div className="k-lbl">DPS efetivo</div>
              <div className="k-val">{fmt(cur.dps)}</div>
              <div className="k-delta">{dDps ? <Delta v={dDps} unit="dps" /> : null}</div>
            </div>
            <div className="kpi2 ehp">
              <div className="k-lbl">EHP</div>
              <div className="k-val">{fmt(cur.ehp)}</div>
              <div className="k-delta">{dEhp ? <Delta v={dEhp} unit="ehp" /> : null}</div>
            </div>
          </div>
          <StatList stats={cur.stats} />
          <div className="card-actions">
            <button className="b-btn" onClick={reset}>resetar</button>
            <button className="b-btn ghost" onClick={onBack}>voltar para equipe</button>
            {busy && <span className="b-busy">recalculando…</span>}
          </div>
        </aside>
      </div>
    </main>
  );
}

function Delta({ v, unit }) {
  return <span className={v > 0 ? "b-up" : "b-down"}>{v > 0 ? "+" : ""}{fmt(v)} {unit}</span>;
}

function StatList({ stats }) {
  const s = stats || {};
  const rows = [
    ["HP", fmt(s.MaxHp || 0)],
    ["Ataque", fmt(s.AttackDamage || 0)],
    ["Vel. ataque", ((s.AttackSpeed || 0) / 100).toFixed(2) + "/s"],
    ["Crítico", ((s.CriticalChance || 0) / 10).toFixed(1) + "%"],
    ["Dano crít.", ((s.CriticalDamage || 0) / 10).toFixed(0) + "%"],
    ["Armadura", fmt(s.Armor || 0)],
    s.DamageReduction ? ["Redução", ((s.DamageReduction || 0) / 10).toFixed(1) + "%"] : null,
    s.DamageAbsorption ? ["Absorção", ((s.DamageAbsorption || 0) / 10).toFixed(1)] : null,
    s.BlockChance ? ["Block", ((s.BlockChance || 0) / 10).toFixed(1) + "%"] : null,
    s.ChaosResistance ? ["Resist. caos", (s.ChaosResistance || 0).toFixed(0) + "%"] : null,
    s.MovementSpeed ? ["Vel. mov.", fmt(s.MovementSpeed || 0)] : null,
  ].filter(Boolean);
  return (
    <div className="statlist">
      {rows.map(([k, v]) => (
        <div className="statline" key={k}><i>{k}</i><span className="sv">{v}</span></div>
      ))}
    </div>
  );
}

/* paper-doll: boneco no centro, gear em volta (arma/armadura esq., acessórios dir.) */
function Doll({ build, work, cap, selIdx, onSelect }) {
  // posiciona cada slot: weapons+armor à esquerda (cols 1-2), accessories à dir (4-5)
  const cells = [];
  const counters = { WEAPON: 0, ARMOR: 0, ACCESSORY: 0 };
  const rowBase = { WEAPON: 1, ARMOR: 2, ACCESSORY: 1 };
  work.forEach((s, i) => {
    const c = catOf(s.gearType);
    const n = counters[c]++;
    let col, row;
    if (c === "ACCESSORY") { col = 4 + (n % 2); row = 1 + Math.floor(n / 2); }
    else if (c === "WEAPON") { col = 1 + (n % 2); row = 1 + Math.floor(n / 2); }
    else { col = 1 + (n % 2); row = 2 + Math.floor(n / 2); } // armor abaixo das armas
    cells.push({ s, i, col, row });
  });
  return (
    <div className="doll">
      <div className="portrait" style={{ gridColumn: 3, gridRow: "1 / 4" }}>
        <div className="pname"><span className="ar">◄</span> {build.name} <span className="ar">►</span></div>
        <div className="pimg"><HeroIco k={build.key} name={build.name} cls="pimg-img" /></div>
        <div className="plv">LV.{build.level}</div>
      </div>
      {cells.map(({ s, i, col, row }) => {
        const g = gradeOf(s.grade);
        const slotCap = (cap?.[s.grade]) || { deco: 0, engr: 0, inscr: 0 };
        const pips = [];
        ["deco", "engr", "inscr"].forEach((t) => {
          const filled = s.sockets.filter((x) => x.type === t);
          for (let k = 0; k < slotCap[t]; k++)
            pips.push(<span key={t + k} className={"dpip " + (filled[k] ? t : "empty")} />);
        });
        return (
          <button
            key={i}
            className={"dslot" + (selIdx === i ? " sel" : "")}
            style={{ gridColumn: col, gridRow: row, "--g": g.c }}
            title={`${slotPt(s.gearType)}: ${s.item} (${gradeOf(s.grade).label} Lv${s.level})`}
            onClick={() => onSelect(i)}
          >
            <ItemIco k={s.itemKey} name={s.item} grade={s.grade} cls="dslot-img" />
            {pips.length > 0 && <span className="dpips">{pips}</span>}
          </button>
        );
      })}
    </div>
  );
}

/* tira de sockets do slot selecionado (remover direto na direita) */
function SelSock({ slot, cap, onRemove }) {
  if (!slot) return null;
  const g = gradeOf(slot.grade);
  const types = [["deco", "Decoração"], ["engr", "Gravação"], ["inscr", "Inscrição"]].filter(([t]) => cap[t] > 0);
  return (
    <div className="sel-sock">
      <div className="ss-head">
        <span className="ss-where">{slotPt(slot.gearType)}</span>
        <span className="ss-name" style={{ color: g.c }}>{slot.item}</span>
        <span className="muted small">Lv{slot.level}</span>
      </div>
      {types.length === 0 ? (
        <div className="ss-empty small">sem socket nesse item</div>
      ) : (
        <div className="ss-rows">
          {types.map(([t, lbl]) => {
            const cur = slot.sockets.map((sk, k) => ({ sk, k })).filter((o) => o.sk.type === t);
            return (
              <div className="ss-row" key={t}>
                <span className={"ss-cap " + t}>{lbl} {cur.length}/{cap[t]}</span>
                {cur.length === 0 ? <span className="ss-empty">vazio</span> : cur.map((o) => (
                  <span className={"csock " + t} key={o.k}>
                    {o.sk.gemName || o.sk.stat}
                    <button className="x" title="remover" onClick={() => onRemove(o.k)}>×</button>
                  </span>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* lista (esquerda): aba item/gem + filtros + opções */
const TABS = [
  { id: "item", label: "Trocar item", cls: "" },
  { id: "deco", label: "Decoração", cls: "" },
  { id: "engr", label: "Gravação", cls: "engr" },
  { id: "inscr", label: "Inscrição", cls: "inscr" },
];
function Catalog({ slot, cat, cap, tab, setTab, filt, setFilt, catalog, ownedSet, onEquipItem, onEquipGem }) {
  if (!slot) return <section className="sec b-cat"><div className="b-empty">selecione um slot</div></section>;
  if (!catalog) return <section className="sec b-cat"><div className="b-empty">carregando catálogo…</div></section>;
  const g = gradeOf(slot.grade);

  // monta as linhas conforme a aba
  const isItem = tab === "item";
  let rows = [];
  if (isItem) {
    const curStats = catalog.items[slot.gearType]?.find((it) => it.itemKey === slot.itemKey)?.stats || [];
    const cur = { kind: "item", itemKey: slot.itemKey, name: slot.item, grade: slot.grade, level: slot.level, equipped: true, stats: curStats };
    const pool = (catalog.items[slot.gearType] || [])
      .filter((it) => it.itemKey !== slot.itemKey)
      .map((it) => ({ kind: "item", ...it }));
    rows = [cur, ...pool];
  } else {
    rows = (catalog.gems[tab] || []).map((gm) => {
      const eff = gm.groups?.[cat];
      return { kind: "gem", itemKey: gm.itemKey, name: gm.name, grade: gm.grade, eff, statKey: eff?.stat };
    }).filter((r) => r.eff);
  }

  // stats disponíveis no pool (chips de buff)
  const statSet = new Set();
  rows.forEach((r) => { if (r.kind === "gem") { if (r.statKey) statSet.add(r.statKey); } else (r.stats || []).forEach((x) => statSet.add(x)); });
  // o item equipado não tem stats no catálogo cur; pega do pool por itemKey
  if (isItem) (catalog.items[slot.gearType] || []).forEach((it) => (it.stats || []).forEach((x) => statSet.add(x)));
  const statChips = [...statSet];

  const matchStat = (r) => !filt.stats.size || (r.kind === "gem" ? (r.statKey && filt.stats.has(r.statKey)) : (r.stats || []).some((x) => filt.stats.has(x)));
  const matchTxt = (n) => (n || "").toLowerCase().includes(filt.search.toLowerCase());

  let view;
  if (isItem) {
    const [cur, ...pool] = rows;
    const filtered = pool.filter((it) =>
      (!filt.invOnly || ownedSet.has(it.itemKey)) &&
      (!filt.tiers.size || filt.tiers.has(it.grade)) &&
      ((it.level || 0) >= filt.lvlMin && (it.level || 0) <= filt.lvlMax) &&
      matchTxt(it.name) && matchStat(it));
    view = [cur, ...filtered];
  } else {
    view = rows.filter((r) => (!filt.invOnly || ownedSet.has(r.itemKey)) && matchTxt(r.name) && matchStat(r));
  }

  const set = (patch) => setFilt((f) => ({ ...f, ...patch }));
  const toggle = (key, val) => setFilt((f) => { const s = new Set(f[key]); s.has(val) ? s.delete(val) : s.add(val); return { ...f, [key]: s }; });

  return (
    <section className="sec b-cat">
      <div className="b-cat-head">
        <ItemIco k={slot.itemKey} name={slot.item} grade={slot.grade} cls="ch-ico" />
        <div>
          <div className="ch-where">{slotPt(slot.gearType)}</div>
          <div className="ch-item" style={{ color: g.c }}>{slot.item}</div>
        </div>
      </div>
      <div className="b-tabs">
        {TABS.map((t) => {
          const dis = t.id !== "item" && !cap[t.id];
          return (
            <button key={t.id} className={"b-tab " + t.cls + (tab === t.id ? " active" : "")}
              disabled={dis} onClick={() => setTab(t.id)}>{t.label}</button>
          );
        })}
      </div>
      <div className="b-filters">
        <div className="frow">
          <span className="lbl">buscar</span>
          <input className="b-search" placeholder={isItem ? "item…" : "gem…"} value={filt.search}
            onChange={(e) => set({ search: e.target.value })} />
          <button className={"b-toggle" + (filt.invOnly ? " on" : "")} onClick={() => set({ invOnly: !filt.invOnly })}>só inventário</button>
        </div>
        {isItem && (
          <>
            <div className="frow">
              <span className="lbl">nível</span>
              <DualRange min={filt.lvlMin} max={filt.lvlMax} onChange={(a, b) => set({ lvlMin: a, lvlMax: b })} />
              <span className="b-range-val">Lv {filt.lvlMin}–{filt.lvlMax}</span>
            </div>
            <div className="frow">
              <span className="lbl">tier</span>
              <div className="b-chips">
                {TIER_ORDER.map((gr) => (
                  <button key={gr} className="b-chip" data-on={filt.tiers.has(gr) ? 1 : 0}
                    style={{ "--g": gradeOf(gr).c }} onClick={() => toggle("tiers", gr)}>{gr.slice(0, 4)}</button>
                ))}
              </div>
            </div>
          </>
        )}
        {statChips.length > 0 && (
          <div className="frow">
            <span className="lbl">buff</span>
            <div className="b-chips">
              {statChips.map((st) => (
                <button key={st} className="b-chip schip" data-on={filt.stats.has(st) ? 1 : 0}
                  onClick={() => toggle("stats", st)}>{statPt(st)}</button>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="b-list">
        {view.length === 0 ? <div className="b-empty">Nada bate com os filtros.</div> : view.map((r, i) => {
          const gr = gradeOf(r.grade);
          const owned = ownedSet.has(r.itemKey);
          const full = r.kind === "gem" && slot.sockets.filter((x) => x.type === tab).length >= (cap[tab] || 0);
          return (
            <div className={"b-opt" + (r.equipped ? " equipped" : "")} key={(r.itemKey || "x") + "_" + i} style={{ "--g": gr.c }}>
              <ItemIco k={r.itemKey} name={r.name} grade={r.grade} cls="op-ico" />
              <div className="op-meta">
                <span className="op-name" style={{ color: gr.c }}>
                  {r.name}
                  {r.equipped && <span className="op-tag eq">equipado</span>}
                  {!r.equipped && owned && <span className="op-tag own">tenho</span>}
                </span>
                <span className="op-fx">
                  {r.kind === "item"
                    ? <span style={{ color: gr.c }}>{gradeOf(r.grade).label} · Lv{r.level}</span>
                    : <span className="op-stat">{statPt(r.eff.stat)} {r.eff.mod === "MULTIPLICATIVE" ? "(more)" : r.eff.mod === "ADDITIVE" ? "(incr)" : ""} {r.eff.min}~{r.eff.max} · T{r.eff.tier}</span>}
                </span>
              </div>
              {r.equipped ? <span className="op-eqtag">equipado</span> : (
                r.kind === "gem"
                  ? <button className="b-equip" disabled={full} title={full ? "sem slot livre — remova um no card" : ""} onClick={() => onEquipGem(r)}>{full ? "cheio" : "encaixar"}</button>
                  : <button className="b-equip" onClick={() => onEquipItem(r)}>equipar</button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* slider de range duplo (nível) */
function DualRange({ min, max, onChange }) {
  const lo = ((min - 1) / (LVL_MAX - 1)) * 100;
  const hi = ((max - 1) / (LVL_MAX - 1)) * 100;
  return (
    <div className="b-range">
      <div className="track" />
      <div className="fill" style={{ left: lo + "%", width: (hi - lo) + "%" }} />
      <input type="range" min={1} max={LVL_MAX} value={min}
        onChange={(e) => { const a = Math.min(+e.target.value, max); onChange(a, max); }} />
      <input type="range" min={1} max={LVL_MAX} value={max}
        onChange={(e) => { const b = Math.max(+e.target.value, min); onChange(min, b); }} />
    </div>
  );
}

/* ---------------- página ---------------- */
export default function BuildsPage({ sim }) {
  const builds = sim?.builds || [];
  const owned = sim?.owned || [];
  const ownedSet = useMemo(() => new Set(owned), [owned]);
  const [sel, setSel] = useState(null);
  const [catalog, setCatalog] = useState(null);
  useEffect(() => {
    let alive = true;
    fetch("/api/catalog").then((r) => r.json()).then((d) => { if (alive && d && !d.error) setCatalog(d); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!builds.length)
    return <main className="page no-rail"><div className="loading">sem dados de heróis ainda…</div></main>;
  if (sel == null) return <Roster builds={builds} onPick={setSel} />;
  const build = builds.find((b) => b.key === sel) || builds[0];
  return (
    <EB>
      <Editor key={build.key} build={build} catalog={catalog} ownedSet={ownedSet} onBack={() => setSel(null)} />
    </EB>
  );
}

class EB extends React.Component {
  constructor(p) { super(p); this.state = { e: null }; }
  static getDerivedStateFromError(e) { return { e }; }
  render() {
    if (this.state.e)
      return <main className="page no-rail"><pre style={{ color: "#ff5b5b", padding: 20, whiteSpace: "pre-wrap", fontSize: 13 }}>{String(this.state.e && this.state.e.stack || this.state.e)}</pre></main>;
    return this.props.children;
  }
}
