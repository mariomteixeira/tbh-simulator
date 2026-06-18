import React, { useEffect, useState } from "react";
import { useSnapshot } from "./useSnapshot.js";
import { fmt, fmtDur, fmtHours, timeAgo } from "./format.js";
import ModelTab from "./components/ModelTab.jsx";
import FarmTable from "./components/FarmTable.jsx";
import Heroes from "./components/Heroes.jsx";
import GearPanel from "./components/GearPanel.jsx";
import DamagePanel from "./components/DamagePanel.jsx";
import CombatPanel from "./components/CombatPanel.jsx";
import OfflinePanel from "./components/OfflinePanel.jsx";
import BoxPanel from "./components/BoxPanel.jsx";
import RunesPage from "./components/RunesPage.jsx";
import CubePanel from "./components/CubePanel.jsx";
import BuildsPage from "./components/BuildsPage.jsx";
import StatFinderPage from "./components/StatFinderPage.jsx";

const ROUTES = [
  { id: "farm", hash: "#/", label: "Farm", group: "Painel", icon: "i-farm" },
  { id: "boxes", hash: "#/baus", label: "Baús", group: "Painel", icon: "i-box" },
  { id: "builds", hash: "#/builds", label: "Builds", group: "Painel", icon: "i-build" },
  { id: "stats", hash: "#/atributos", label: "Atributos", group: "Painel", icon: "i-find" },
  { id: "cube", hash: "#/cubo", label: "Cubo", group: "Painel", icon: "i-cube" },
  { id: "runes", hash: "#/runas", label: "Runas", group: "Painel", icon: "i-rune" },
  { id: "heroes", hash: "#/herois", label: "Heróis & Gear", group: "Painel", icon: "i-hero" },
  { id: "offline", hash: "#/offline", label: "Offline", group: "Painel", icon: "i-off" },
  { id: "model", hash: "#/modelo", label: "Calibração", group: "Sistema", icon: "i-model" },
];

/* ícones pixel (silhuetas crispEdges) — copiados do mockup; injetados 1x no shell */
function NavIcons() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
      <defs>
        <g id="i-farm">
          <rect x="7" y="2" width="2" height="7" />
          <rect x="4" y="9" width="8" height="2" />
          <rect x="7" y="11" width="2" height="3" />
        </g>
        <g id="i-box">
          <rect x="3" y="4" width="10" height="2" />
          <rect x="3" y="7" width="10" height="6" />
        </g>
        <g id="i-cube">
          <path d="M4 4h8v8H4z" fill="none" stroke="currentColor" strokeWidth="2" />
          <rect x="4" y="4" width="8" height="2" />
        </g>
        <g id="i-build">
          <rect x="3" y="2" width="10" height="3" />
          <rect x="3" y="6" width="4" height="8" />
          <rect x="9" y="6" width="4" height="8" />
        </g>
        <g id="i-find">
          <circle cx="7" cy="7" r="4" fill="none" stroke="currentColor" strokeWidth="2" />
          <rect x="10" y="10" width="2" height="5" transform="rotate(-45 11 12)" />
        </g>
        <g id="i-rune">
          <path d="M8 2l5 5-5 7-5-7z" />
        </g>
        <g id="i-hero">
          <path d="M3 3h10v5l-5 6-5-6z" />
        </g>
        <g id="i-off">
          <path d="M10 2a6 6 0 1 0 0 12 7 7 0 0 1 0-12z" />
        </g>
        <g id="i-model">
          <rect x="3" y="3" width="2" height="10" />
          <rect x="2" y="6" width="4" height="2" />
          <rect x="7" y="3" width="2" height="10" />
          <rect x="6" y="9" width="4" height="2" />
          <rect x="11" y="3" width="2" height="10" />
          <rect x="10" y="5" width="4" height="2" />
        </g>
      </defs>
    </svg>
  );
}

function useRoute() {
  const find = () =>
    ROUTES.find((r) => r.hash === (window.location.hash || "#/")) || ROUTES[0];
  const [route, setRoute] = useState(find);
  useEffect(() => {
    const on = () => setRoute(find());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

/* ---------- blocos do rail (coluna direita) ---------- */
function RailRows({ title, rows }) {
  const visible = rows.filter((r) => r);
  if (!visible.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <div className="rail-rows">
        {visible.map(([label, value, cls], i) => (
          <div className="rail-row" key={i}>
            <i>{label}</i>
            <b className={cls || ""}>{value}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function StageRef({ r }) {
  if (!r) return null;
  return (
    <span>
      <span className={"diff-tag t-" + r.tag}>{r.tag}</span> {r.label}
    </span>
  );
}

/* ---------- páginas ---------- */
function CeilingPicker({ farm }) {
  const opts = (farm.rows || []).filter(
    (r) => r.cleared && r.type !== "ACTBOSS"
  );
  // UI otimista: mostra a escolha na hora; sincroniza quando o servidor refletir
  const [pending, setPending] = useState(null);
  useEffect(() => {
    if (pending !== null && String(farm.ceiling ?? "") === String(pending)) {
      setPending(null);
    }
  }, [farm.ceiling, pending]);
  async function set(v) {
    setPending(v);
    if (v === "") await fetch("/api/ceiling", { method: "DELETE" });
    else
      await fetch("/api/ceiling", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: Number(v) }),
      });
  }
  const shown = pending !== null ? pending : String(farm.ceiling ?? "");
  return (
    <div>
      <h3>Teto — até onde você farma</h3>
      <select
        className="ceiling-sel"
        value={shown}
        onChange={(e) => set(e.target.value)}
      >
        <option value="">sem teto (tudo liberado)</option>
        {opts.map((r) => (
          <option key={r.key} value={r.key}>
            {r.tag} {r.label} — {r.name}
          </option>
        ))}
      </select>
      <p className="muted small" style={{ marginTop: 6 }}>
        {pending !== null && <em className="muted">aplicando… </em>}
        Nada <b>acima do teto</b> entra em recomendação (farm, push ou baús) —
        mesmo que o jogo já tenha liberado.
      </p>
    </div>
  );
}

function FarmPage({ sim }) {
  const f = sim?.farm;
  const cur = f?.current;
  return {
    main: f ? <FarmTable farm={f} /> : null,
    rail: f && (
      <>
        <CeilingPicker farm={f} />
        <RailRows
          title="Recomendações"
          rows={[
            f.bestGold && ["melhor gold", <StageRef r={f.bestGold} />],
            f.bestExp && ["melhor exp", <StageRef r={f.bestExp} />],
            f.push && ["push", <StageRef r={f.push} />],
          ]}
        />
        {cur && (
          <RailRows
            title="Estágio atual"
            rows={[
              ["fase", <StageRef r={cur} />],
              ["clear previsto", fmtDur(cur.clearTime)],
              ["gold/h", fmt(cur.goldPerHour), "v-gold"],
              ["exp/h", fmt(cur.expPerHour), "v-exp"],
              ["risco", cur.rating],
            ]}
          />
        )}
      </>
    ),
  };
}

function BoxesPage({ d, sim }) {
  const f = sim?.farm;
  const chests = (d.sessionRates || d.rates)?.chests_per_hour || {};
  return {
    main: f ? <BoxPanel farm={f} rates={d.sessionRates || d.rates} /> : null,
    rail: f && (
      <>
        <RailRows
          title="Medido na sessão"
          rows={[
            ["baús normais/h", chests.normal != null ? chests.normal.toFixed(1) : "—"],
            ["baús de boss/h", chests.boss != null ? chests.boss.toFixed(1) : "—"],
          ]}
        />
        {f.bestBossBox && (
          <RailRows
            title="Bau do boss (azul)"
            rows={[
              ["melhor fase", <StageRef r={f.bestBossBox} />],
              ["bau", f.bestBossBox.bossBox],
              ["clear", fmtDur(f.bestBossBox.clearTime)],
            ]}
          />
        )}
        {f.bestNormalBox && (
          <RailRows
            title="Bau normal"
            rows={[
              ["melhor fase", <StageRef r={f.bestNormalBox} />],
              ["bau", f.bestNormalBox.normalBox],
            ]}
          />
        )}
        {f.dropBonus && (
          <RailRows
            title="Bônus de chance"
            rows={[
              ["bau normal", "+" + f.dropBonus.normal + "%"],
              ["bau do boss", "+" + f.dropBonus.boss + "%"],
            ]}
          />
        )}
      </>
    ),
  };
}

function HeroesPage({ d, sim, st }) {
  return {
    main: (
      <>
        {sim?.combat?.length > 0 && <CombatPanel combat={sim.combat} />}
        {sim?.heroes?.length > 0 && <DamagePanel heroes={sim.heroes} />}
        {sim?.gear && <GearPanel gear={sim.gear} />}
      </>
    ),
    rail: sim && (
      <div className="rail-hero">
        <Heroes sim={sim} state={st} rates={d.sessionRates || d.rates} />
      </div>
    ),
  };
}

function OfflinePage({ sim }) {
  return { main: sim?.offline ? <OfflinePanel offline={sim.offline} /> : null, rail: null };
}

function ModelPage({ d, sim }) {
  return {
    main: sim ? <ModelTab sim={sim} manualSamples={d.manualSamples} /> : null,
    rail: null,
  };
}

/* ---------- shell ---------- */
export default function App() {
  const { data: d, online } = useSnapshot();
  const route = useRoute();
  const st = d?.state;
  const sim = d?.sim;
  const status = d?.status;
  const sr = d?.sessionRates;
  const version = d?.version;

  const msgs = [];
  if (status) {
    if (!status.saveFound) msgs.push("Save não encontrado: " + status.savePath);
    else if (status.error) msgs.push(status.error);
    if (status.gamedataError) msgs.push(status.gamedataError);
    if (status.simError) msgs.push(status.simError);
  }

  let page = { main: null, rail: null };
  if (st) {
    if (route.id === "farm") page = FarmPage({ sim });
    else if (route.id === "boxes") page = BoxesPage({ d, sim });
    else if (route.id === "heroes") page = HeroesPage({ d, sim, st });
    else if (route.id === "offline") page = OfflinePage({ sim });
    else if (route.id === "model") page = ModelPage({ d, sim });
  }

  const groups = [...new Set(ROUTES.map((r) => r.group))];

  return (
    <div className="app">
      <NavIcons />
      <aside className="sidenav">
        <div className="brand">
          <span className="brand-mark">TBH</span>
          <span className="brand-name">Copilot</span>
        </div>
        <nav className="nav">
          {groups.map((g) => (
            <div className="nav-group" key={g}>
              <div className="nav-group-label">{g}</div>
              {ROUTES.filter((r) => r.group === g).map((r, i) => (
                <a
                  key={r.id}
                  href={r.hash}
                  className={"nav-item" + (route.id === r.id ? " active" : "")}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <use href={"#" + r.icon} />
                  </svg>
                  {r.label}
                </a>
              ))}
            </div>
          ))}
        </nav>
        <div className="side-foot">
          <span>
            <span className={"conn-dot " + (online ? "ok" : "bad")} />
            {online ? "conectado" : "sem backend"}
          </span>
          {status?.lastRead && <span>save lido {timeAgo(status.lastRead)}</span>}
          <span>somente leitura</span>
        </div>
      </aside>

      <div className="content">
        <header className="topbar">
          <div className="crumb">
            TBH Copilot <span className="sep">/</span>{" "}
            <span className="here">{route.label}</span>
          </div>
          <div className="topbar-right">
            {st && <span>estágio {st.currentStage}</span>}
            <span className="live">
              {online ? (
                <span className="dot" />
              ) : (
                <span className="conn-dot bad" />
              )}
              <span className="lbl">{online ? "ao vivo" : "sem backend"}</span>
            </span>
            {version && <span className="ver">v{version}</span>}
          </div>
        </header>

        {msgs.length > 0 && <div className="banner">{msgs.join(" · ")}</div>}

        {!st ? (
          <div className="loading">aguardando primeira leitura do save…</div>
        ) : route.id === "runes" ? (
          <RunesPage key="runes" runes={sim?.runes} />
        ) : route.id === "builds" ? (
          <BuildsPage key="builds" sim={sim} />
        ) : route.id === "stats" ? (
          <StatFinderPage key="stats" sim={sim} />
        ) : route.id === "cube" ? (
          <CubePanel key="cube" alchemy={sim?.alchemy} />
        ) : (
          <main
            key={route.id}
            className={"page" + (page.rail ? "" : " no-rail")}
          >
            <div className="main-col">{page.main}</div>
            {page.rail && <aside className="rail">{page.rail}</aside>}
          </main>
        )}

        <footer className="foot">
          o save nunca é tocado · dados: taskbarhero.wiki
        </footer>
      </div>
    </div>
  );
}
