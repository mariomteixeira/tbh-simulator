import React from "react";
import { fmt, fmtDur } from "../format.js";

export default function ModelTab({ sim, manualSamples }) {
  const cal = sim.calibration;
  const rowByKey = {};
  for (const r of sim.farm.rows || []) rowByKey[r.key] = r;

  // previsto x medido: compara o modelo com as SUAS calibracoes (verdade-base).
  // OBS: o previsto usa o DPS ATUAL; se o time ficou mais forte desde a
  // calibracao, e CERTO o previsto ficar menor que o cronometrado da epoca.
  const comparison = (manualSamples || [])
    .map((m) => {
      const row = rowByKey[m.stage];
      return {
        key: m.stage,
        label: row ? `${row.tag} ${row.label}` : m.stage,
        name: row?.name,
        observed: m.clearSec,
        dpsThen: m.partyDps,
        predicted: row ? row.clearTime : null,
        errPct: row ? ((row.clearTime - m.clearSec) / m.clearSec) * 100 : null,
      };
    })
    .sort((a, b) => String(a.label).localeCompare(String(b.label)));
  const dpsNow = sim.party?.dps;

  const killRate = sim.party?.dps && cal.factor ? sim.party.dps * cal.factor : null;

  const [secs, setSecs] = React.useState("");
  const curRow = (sim.farm.rows || []).find((r) => r.current);
  async function saveCal(stageKey) {
    const v = parseFloat(secs);
    if (!v || v <= 0) return;
    await fetch("/api/calibration", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: Number(stageKey), clearSec: v }),
    });
    setSecs("");
  }
  async function removeCal(stageKey) {
    await fetch("/api/calibration/" + stageKey, { method: "DELETE" });
  }

  return (
    <div className="model-grid">
      <section className="sec">
        <h2>Calibrar tempo de clear (manual)</h2>
        <p className="muted small">
          Cronometre uma run e digite o tempo <b>em segundos</b> (o Records do
          jogo mostra, ex.: "Cleared Stage 2-6. (257s)"). É a única fonte de
          tempo do modelo — um único tempo já ancora a velocidade de kill.
        </p>
        {curRow ? (
          <div className="cal-form">
            <div className="cal-stage">
              fase atual: <b>{curRow.tag} {curRow.label}</b>{" "}
              <span className="muted">{curRow.name}</span>
              {curRow.clearTime != null && (
                <span className="muted"> · previsto agora {fmtDur(curRow.clearTime)}</span>
              )}
            </div>
            <div className="cal-row">
              <input
                type="number" min="1" step="1" placeholder="segundos"
                value={secs}
                onChange={(e) => setSecs(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && saveCal(curRow.key)}
              />
              <span className="muted">s</span>
              <button onClick={() => saveCal(curRow.key)} disabled={!secs}>
                Salvar
              </button>
            </div>
          </div>
        ) : (
          <p className="muted small">aguardando o save pra saber a fase atual…</p>
        )}
      </section>

      <section className="sec">
        <h2>Previsto × medido (suas calibrações)</h2>
        {comparison.length === 0 ? (
          <p className="muted small">
            Nenhuma calibração ainda. Cronometre uma run no card acima — o
            modelo extrapola dela pra todas as fases.
          </p>
        ) : (
          <>
            <table className="mini wide">
              <thead>
                <tr>
                  <th>estágio</th><th>cronometrado</th><th>dps na época</th>
                  <th>previsto hoje{dpsNow ? ` (dps ${fmt(dpsNow)})` : ""}</th>
                  <th>Δ</th><th></th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((c) => (
                  <tr key={c.key}>
                    <td>{c.label} <span className="muted">{c.name}</span></td>
                    <td>{Math.round(c.observed)}s</td>
                    <td className="muted">{c.dpsThen ? fmt(c.dpsThen) : "—"}</td>
                    <td>{c.predicted != null ? fmtDur(c.predicted) : "—"}</td>
                    <td className={Math.abs(c.errPct ?? 0) > 25 ? "err-bad" : "err-ok"}>
                      {c.errPct != null ? (c.errPct > 0 ? "+" : "") + c.errPct.toFixed(0) + "%" : "—"}
                    </td>
                    <td>
                      <button className="link" onClick={() => removeCal(c.key)}>
                        remover
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small" style={{ marginTop: 8 }}>
              O previsto usa seu DPS <b>atual</b> — se o time ficou mais forte
              desde a calibração, é normal o previsto ser menor que o tempo
              cronometrado na época. Recalibre de vez em quando pra acompanhar.
            </p>
          </>
        )}
      </section>

      <section className="sec">
        <h2>Estado da calibração</h2>
        <div className="model-stats">
          <div className="kv-big">
            <i>fonte ativa</i>
            <b>{cal.source}</b>
          </div>
          <div className="kv-big">
            <i>calibrações</i>
            <b>{(manualSamples || []).length}</b>
          </div>
          <div className="kv-big">
            <i>overhead por wave</i>
            <b>{cal.tWave != null ? cal.tWave + "s" : "—"}</b>
          </div>
          <div className="kv-big">
            <i>velocidade de kill</i>
            <b>{killRate ? fmt(killRate) + " HP/s" : "—"}</b>
          </div>
          <div className="kv-big">
            <i>fator (kill ÷ DPS teórico)</i>
            <b>{cal.factor ?? "—"}</b>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>
          Economia (gold/exp por run) vem do reward dataminado da wiki, como o
          Farming Planner. A amostragem automática foi removida: o contador de
          "clears" do save conta várias vezes por run e gerava tempos ~5×
          menores que o real.
        </p>
      </section>

      <section className="sec">
        <h2>Como o tempo é medido</h2>
        <ul className="method-list">
          <li>
            <b>Você cronometra</b> uma run (ou copia do Records do jogo) e digita
            em segundos. É a verdade-base; quanto mais fases, melhor a curva.
          </li>
          <li>
            O modelo é <b>tempo = overhead·waves + HP ÷ velocidade de kill</b>,
            ajustado às suas calibrações — igual ao Farming Planner da wiki.
            Com 3+ tempos ele separa o overhead por wave da velocidade de kill.
          </li>
          <li>
            EXP por hora aplica a <b>curva de EXP por nível</b> exata do jogo e
            ancora no exp/h medido da sessão.
          </li>
          <li>
            Baús por hora são <b>medidos dos contadores do save</b> — o drop é
            limitado pelo jogo, não dá pra derivar da chance.
          </li>
          <li>
            Bosses de ato não entram na tabela: a run de boss não é um loop
            contínuo e o rendimento por hora não se aplica.
          </li>
        </ul>
      </section>
    </div>
  );
}
