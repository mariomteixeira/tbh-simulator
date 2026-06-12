import React, { useEffect, useState } from "react";
import { useSnapshot } from "./useSnapshot.js";
import { fmt, fmtDur, fmtHours, timeAgo } from "./format.js";
import ModelTab from "./components/ModelTab.jsx";
import Coach from "./components/Coach.jsx";
import FarmTable from "./components/FarmTable.jsx";
import Heroes from "./components/Heroes.jsx";
import GearPanel from "./components/GearPanel.jsx";
import DamagePanel from "./components/DamagePanel.jsx";
import OfflinePanel from "./components/OfflinePanel.jsx";
import GoldChart from "./components/GoldChart.jsx";
import ProjectionChart from "./components/ProjectionChart.jsx";
import BoxPanel from "./components/BoxPanel.jsx";
import RunesPage from "./components/RunesPage.jsx";

const ROUTES = [
  { id: "overview", hash: "#/", label: "Visão geral", group: "Painel" },
  { id: "farm", hash: "#/farm", label: "Farm", group: "Painel" },
  { id: "boxes", hash: "#/baus", label: "Baús", group: "Painel" },
  { id: "runes", hash: "#/runas", label: "Runas", group: "Painel" },
  { id: "heroes", hash: "#/herois", label: "Heróis & Gear", group: "Painel" },
  { id: "offline", hash: "#/offline", label: "Offline", group: "Painel" },
  { id: "model", hash: "#/modelo", label: "Modelo & Calibração", group: "Sistema" },
];

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
function Overview({ d, sim, st, sr }) {
  const goldRate =
    sr && sr.dt_hours > 0
      ? sr.gold_per_hour === null
        ? "gold gasto na sessão"
        : fmt(sr.gold_per_hour) + "/h líquido"
      : "aguardando 2º save…";
  const expSession = sr?.exp_per_hour
    ? Object.values(sr.exp_per_hour).reduce((a, b) => a + (b || 0), 0)
    : null;
  return {
    main: (
      <>
        <div className="kpis">
          <div className="kpi">
            <span className="kpi-label">Gold</span>
            <span className="kpi-value gold">{fmt(st.gold)}</span>
            <span className="kpi-sub">{goldRate}</span>
          </div>
          <div className="kpi">
            <span className="kpi-label">DPS do time</span>
            <span className="kpi-value">{sim ? fmt(sim.party.dps) : "—"}</span>
            <span className="kpi-sub">{sim ? sim.calibration.source : "—"}</span>
          </div>
          <div className="kpi">
            <span className="kpi-label">Estágio</span>
            <span className="kpi-value">{st.currentStage}</span>
            <span className="kpi-sub">máx concluído {st.maxStage}</span>
          </div>
          <div className="kpi">
            <span className="kpi-label">Tempo de jogo</span>
            <span className="kpi-value">{(st.playTime / 3600).toFixed(1)}h</span>
            <span className="kpi-sub">
              {sr && sr.dt_hours > 0
                ? "sessão: " + fmtHours(sr.dt_hours)
                : "sessão começando"}
            </span>
          </div>
        </div>
        {sim?.coach && <Coach paragraphs={sim.coach} />}
        <div className="charts-duo">
          <GoldChart history={d.history} />
          {sim?.projection?.length > 0 && (
            <ProjectionChart projection={sim.projection} />
          )}
        </div>
      </>
    ),
    rail: (
      <>
        <RailRows
          title="Sessão"
          rows={[
            ["gold/h", sr?.gold_per_hour != null ? fmt(sr.gold_per_hour) : "—", "v-gold"],
            ["exp/h", expSession ? fmt(expSession) : "—", "v-exp"],
            ["medida em", sr?.dt_hours > 0 ? fmtHours(sr.dt_hours) : "—"],
          ]}
        />
        {sim && (
          <RailRows
            title="Bônus ativos"
            rows={[
              ["gold", "+" + sim.goldBonusPct + "%", "v-gold"],
              ["exp", "+" + sim.expBonusPct + "%", "v-exp"],
              sim.farm?.dropBonus && ["bau normal", "+" + sim.farm.dropBonus.normal + "%"],
              sim.farm?.dropBonus && ["bau do boss", "+" + sim.farm.dropBonus.boss + "%"],
            ]}
          />
        )}
        {sim?.offline?.park && (
          <div>
            <h3>Estacionar offline</h3>
            <div className="park">
              <div className="park-stage">
                <StageRef r={sim.offline.park} /> {sim.offline.park.name}
              </div>
              <div className="park-yield">
                <span className="v-gold">{fmt(sim.offline.park.gold)}</span> ·{" "}
                <span className="v-exp">{fmt(sim.offline.park.exp)}</span> em 8h
              </div>
            </div>
          </div>
        )}
      </>
    ),
  };
}

function CeilingPicker({ farm }) {
  const opts = (farm.rows || []).filter(
    (r) => r.cleared && r.type !== "ACTBOSS"
  );
  async function set(v) {
    if (v === "") await fetch("/api/ceiling", { method: "DELETE" });
    else
      await fetch("/api/ceiling", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: Number(v) }),
      });
  }
  return (
    <div>
      <h3>Teto — até onde você farma</h3>
      <select
        className="ceiling-sel"
        value={farm.ceiling ?? ""}
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

  const msgs = [];
  if (status) {
    if (!status.saveFound) msgs.push("Save não encontrado: " + status.savePath);
    else if (status.error) msgs.push(status.error);
    if (status.gamedataError) msgs.push(status.gamedataError);
    if (status.simError) msgs.push(status.simError);
  }

  let page = { main: null, rail: null };
  if (st) {
    if (route.id === "overview") page = Overview({ d, sim, st, sr });
    else if (route.id === "farm") page = FarmPage({ sim });
    else if (route.id === "boxes") page = BoxesPage({ d, sim });
    else if (route.id === "heroes") page = HeroesPage({ d, sim, st });
    else if (route.id === "offline") page = OfflinePage({ sim });
    else if (route.id === "model") page = ModelPage({ d, sim });
  }

  const groups = [...new Set(ROUTES.map((r) => r.group))];

  return (
    <div className="app">
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
                  <span className="idx">
                    {String(ROUTES.indexOf(r) + 1).padStart(2, "0")}
                  </span>
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
            <span className={"conn-dot " + (online ? "ok" : "bad")} />
          </div>
        </header>

        {msgs.length > 0 && <div className="banner">{msgs.join(" · ")}</div>}

        {!st ? (
          <div className="loading">aguardando primeira leitura do save…</div>
        ) : route.id === "runes" ? (
          <RunesPage key="runes" runes={sim?.runes} />
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
