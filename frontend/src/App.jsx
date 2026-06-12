import React, { useState } from "react";
import { useSnapshot } from "./useSnapshot.js";
import { fmt, fmtHours, timeAgo } from "./format.js";
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

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="card stat">
      <span className="stat-label">{label}</span>
      <span className={"stat-value" + (accent ? " " + accent : "")}>{value}</span>
      <span className="stat-sub">{sub}</span>
    </div>
  );
}

export default function App() {
  const { data: d, online } = useSnapshot();
  const [tab, setTab] = useState("painel");
  const st = d?.state;
  const sim = d?.sim;
  const status = d?.status;

  const sr = d?.sessionRates;
  const goldRate =
    sr && sr.dt_hours > 0
      ? sr.gold_per_hour === null
        ? "gold gasto na sessão"
        : fmt(sr.gold_per_hour) + "/h na sessão"
      : "aguardando 2º save…";

  const msgs = [];
  if (status) {
    if (!status.saveFound) msgs.push("Save não encontrado: " + status.savePath);
    else if (status.error) msgs.push(status.error);
    if (status.gamedataError) msgs.push(status.gamedataError);
    if (status.simError) msgs.push(status.simError);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">TBH</span>
          <span className="brand-name">Copilot</span>
          <nav className="tabs">
            <button
              className={"tab" + (tab === "painel" ? " active" : "")}
              onClick={() => setTab("painel")}
            >
              Painel
            </button>
            <button
              className={"tab" + (tab === "modelo" ? " active" : "")}
              onClick={() => setTab("modelo")}
            >
              Modelo
            </button>
          </nav>
        </div>
        <div className="topbar-right">
          {status?.lastRead && (
            <span className="muted">save lido {timeAgo(status.lastRead)}</span>
          )}
          <span className={"conn-dot " + (online ? "ok" : "bad")} />
          <span className="muted">{online ? "conectado" : "sem backend"}</span>
        </div>
      </header>

      {msgs.length > 0 && <div className="banner">{msgs.join(" · ")}</div>}

      {!st ? (
        <div className="loading">aguardando primeira leitura do save…</div>
      ) : tab === "modelo" && sim ? (
        <ModelTab
          sim={sim}
          samples={d.samples}
          manualSamples={d.manualSamples}
          sampleLog={d.sampleLog}
        />
      ) : (
        <main className="bento">
          <section className="kpi-strip">
            <StatCard label="Gold" value={fmt(st.gold)} sub={goldRate} accent="gold" />
            <StatCard
              label="DPS do time"
              value={sim ? fmt(sim.party.dps) : "—"}
              sub={sim ? sim.calibration.source : "simulador indisponível"}
            />
            <StatCard
              label="Estágio"
              value={st.currentStage}
              sub={"máx concluído " + st.maxStage}
            />
            <StatCard
              label="Tempo de jogo"
              value={(st.playTime / 3600).toFixed(1) + "h"}
              sub={
                sr && sr.dt_hours > 0
                  ? "sessão medida: " + fmtHours(sr.dt_hours)
                  : "sessão começando"
              }
            />
          </section>

          {sim?.coach && (
            <div className="cell c-8">
              <Coach paragraphs={sim.coach} />
            </div>
          )}
          {sim && (
            <div className="cell c-4">
              <Heroes sim={sim} state={st} rates={d.sessionRates || d.rates} />
            </div>
          )}
          {sim && (
            <div className="cell c-12">
              <FarmTable farm={sim.farm} />
            </div>
          )}
          {sim?.farm && (
            <div className="cell c-7">
              <BoxPanel farm={sim.farm} />
            </div>
          )}
          {sim?.offline && (
            <div className="cell c-5">
              <OfflinePanel offline={sim.offline} />
            </div>
          )}
          <div className="cell c-12">
            <div className="charts-row">
              <GoldChart history={d.history} />
              {sim?.projection?.length > 0 && (
                <ProjectionChart projection={sim.projection} />
              )}
            </div>
          </div>
          {sim?.gear && (
            <div className="cell c-6">
              <GearPanel gear={sim.gear} />
            </div>
          )}
          {sim?.heroes?.length > 0 && (
            <div className="cell c-6">
              <DamagePanel heroes={sim.heroes} />
            </div>
          )}
        </main>
      )}

      <footer className="foot">
        somente leitura · o save nunca é tocado · dados: taskbarhero.wiki
      </footer>
    </div>
  );
}
