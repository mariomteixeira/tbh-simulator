import React from "react";
import { fmt, fmtDur, timeAgo } from "../format.js";

function median(arr) {
  const s = [...arr].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export default function ModelTab({ sim, samples, manualSamples, sampleLog }) {
  const cal = sim.calibration;
  const rowByKey = {};
  for (const r of sim.farm.rows || []) rowByKey[r.key] = r;

  // agrupa amostras por estágio para comparar com a previsão atual
  const byStage = {};
  for (const s of samples || []) {
    (byStage[s.stage] = byStage[s.stage] || []).push(s);
  }
  const comparison = Object.entries(byStage)
    .map(([key, ss]) => {
      const row = rowByKey[key];
      const observed = median(ss.map((x) => x.clearSec));
      const predicted = row ? row.clearTime : null;
      return {
        key,
        label: row ? `${row.tag} ${row.label}` : key,
        name: row?.name,
        n: ss.length,
        observed,
        predicted,
        errPct: predicted ? ((predicted - observed) / observed) * 100 : null,
      };
    })
    .sort((a, b) => b.n - a.n);

  const killRate = sim.party?.dps && cal.factor ? sim.party.dps * cal.factor : null;
  const recent = [...(samples || [])].reverse().slice(0, 30);

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
      <div className="card">
        <h2>Calibrar tempo de clear (manual)</h2>
        <p className="muted small">
          Cronometre uma run e digite o tempo <b>em segundos</b>. Vale como
          verdade-base (peso alto) e melhora o modelo na hora — um único tempo
          já ancora a velocidade de kill.
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
        {manualSamples?.length > 0 && (
          <table className="mini wide">
            <thead>
              <tr><th>fase</th><th>tempo (s)</th><th>dps na época</th><th></th></tr>
            </thead>
            <tbody>
              {manualSamples.map((m) => {
                const row = rowByKey[m.stage];
                return (
                  <tr key={m.stage}>
                    <td>{row ? `${row.tag} ${row.label}` : m.stage}</td>
                    <td>{Math.round(m.clearSec)}s</td>
                    <td>{fmt(m.partyDps)}</td>
                    <td>
                      <button className="link" onClick={() => removeCal(m.stage)}>
                        remover
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Estado da calibração</h2>
        <div className="model-stats">
          <div className="kv-big">
            <i>fonte ativa</i>
            <b>{cal.source}</b>
          </div>
          <div className="kv-big">
            <i>amostras persistidas</i>
            <b>{cal.samples}</b>
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
          Economia (gold/exp por run) vem do reward dataminado da wiki direto,
          como o Farming Planner. O tempo de clear vem das suas calibrações
          manuais; o contador de "clears" do save conta várias vezes por run e
          não é usado.
        </p>
      </div>

      <div className="card">
        <h2>Previsto × medido (por estágio)</h2>
        {comparison.length === 0 ? (
          <p className="muted small">
            Ainda sem amostras para comparar. Jogue alguns minutos num mesmo
            mapa com o painel aberto — cada save no mesmo estágio vira uma
            medição de tempo de run.
          </p>
        ) : (
          <table className="mini wide">
            <thead>
              <tr>
                <th>estágio</th><th>amostras</th><th>medido (mediana)</th>
                <th>previsto agora</th><th>erro</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((c) => (
                <tr key={c.key}>
                  <td>{c.label} <span className="muted">{c.name}</span></td>
                  <td>{c.n}</td>
                  <td>{fmtDur(c.observed)}</td>
                  <td>{c.predicted != null ? fmtDur(c.predicted) : "—"}</td>
                  <td className={Math.abs(c.errPct ?? 0) > 30 ? "err-bad" : "err-ok"}>
                    {c.errPct != null ? (c.errPct > 0 ? "+" : "") + c.errPct.toFixed(0) + "%" : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Amostras recentes</h2>
        {recent.length === 0 ? (
          <p className="muted small">nenhuma ainda</p>
        ) : (
          <table className="mini wide">
            <thead>
              <tr>
                <th>estágio</th><th>tempo/run</th><th>runs</th>
                <th>método</th><th>dps na época</th><th>quando</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((s, i) => (
                <tr key={i}>
                  <td>{rowByKey[s.stage] ? `${rowByKey[s.stage].tag} ${rowByKey[s.stage].label}` : s.stage}</td>
                  <td>{fmtDur(s.clearSec)}</td>
                  <td>{s.clears}</td>
                  <td className="muted">{s.method === "clears" ? "contador exato" : "estimado por gold"}</td>
                  <td>{fmt(s.partyDps)}</td>
                  <td className="muted">{timeAgo(s.ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Decisões de janela (auditoria)</h2>
        {!sampleLog?.length ? (
          <p className="muted small">nenhuma decisão registrada ainda</p>
        ) : (
          <table className="mini wide">
            <thead>
              <tr>
                <th>quando</th><th>estágio</th><th>janela</th><th>runs</th>
                <th>kills por run (obs vs wiki)</th><th>resultado</th>
              </tr>
            </thead>
            <tbody>
              {[...sampleLog].reverse().map((l, i) => (
                <tr key={i}>
                  <td className="muted">{timeAgo(l.ts)}</td>
                  <td>{l.stage ?? "—"}</td>
                  <td>{l.dt != null ? fmtDur(l.dt) : "—"}</td>
                  <td>{l.clears ?? "—"}</td>
                  <td>
                    {l.killsPorRun != null
                      ? `${l.killsPorRun}${l.killsWiki ? ` vs ${l.killsWiki} (×${l.ratio})` : ""}`
                      : "—"}
                  </td>
                  <td className={l.why === "amostra registrada" ? "err-ok" : "muted"}>
                    {l.why}{l.clearSec ? ` — ${fmtDur(l.clearSec)}/run` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Como o tempo é medido</h2>
        <ul className="method-list">
          <li>
            <b>Você cronometra</b> uma run e digita o tempo em segundos (no card
            acima). É a verdade-base: um único tempo já ancora a velocidade de
            kill, e quanto mais fases você cronometrar, melhor a curva.
          </li>
          <li>
            O modelo é <b>tempo = overhead·waves + HP ÷ velocidade de kill</b>,
            ajustado aos seus tempos — igual ao Farming Planner da wiki. Com 3+
            tempos ele separa o overhead por wave da velocidade de kill.
          </li>
          <li>
            O contador de "clears" do save <b>não é confiável</b> (conta várias
            vezes por run), então o automático derivado dele é ignorado sempre
            que há qualquer tempo manual.
          </li>
          <li>
            EXP por hora aplica a <b>curva de EXP por nível</b> do jogo (fases
            muito abaixo do seu nível rendem quase nada de exp) e ancora no
            exp/h medido da sessão.
          </li>
          <li>
            Bosses de ato não entram na tabela: a run de boss não é um loop
            contínuo e o rendimento por hora não se aplica.
          </li>
        </ul>
      </div>
    </div>
  );
}
