import React from "react";
import { fmt, fmtDur, timeAgo } from "../format.js";

function median(arr) {
  const s = [...arr].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export default function ModelTab({ sim, samples, sampleLog }) {
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

  return (
    <div className="model-grid">
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
          <div className="kv-big">
            <i>correção wiki→real (economia)</i>
            <b>
              ×{sim.econScale?.global ?? 1}{" "}
              <span className="muted">
                ({Object.keys(sim.econScale?.stages || {}).length} fase(s) medidas)
              </span>
            </b>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>
          A composição de monstros da wiki se mostrou inflada em algumas fases;
          o sistema aprende kills/run reais dos contadores do save e corrige
          HP/gold/exp por fase (fases sem medição herdam a mediana).
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
            Entre dois saves <b>no mesmo mapa</b>, o contador interno de clears
            do save dá o número <b>exato</b> de runs do intervalo; tempo do
            intervalo ÷ runs = tempo por run.
          </li>
          <li>
            O contador de kills valida cada amostra: se você <b>trocou de mapa
            no meio</b>, os kills não batem com runs × monstros-por-run da fase
            e a amostra é <b>descartada</b> — trocar de mapa nunca contamina o
            modelo, só deixa de gerar amostra naquele intervalo.
          </li>
          <li>
            Com 3+ amostras, uma regressão ajusta o overhead por wave e a
            velocidade de kill aos seus dados (amostras antigas pesam menos,
            meia-vida de 14 dias, normalizadas pelo DPS da época).
          </li>
          <li>
            Sem amostras, o modelo ancora no gold/h da sessão (escala linear
            por HP — é por isso que fases distantes da atual podem mostrar
            tempo errado no começo; a tabela acima mostra o erro caindo
            conforme as amostras chegam).
          </li>
          <li>
            Bosses de ato não entram na tabela de farm: a run de boss não é um
            loop contínuo e o rendimento por hora não se aplica.
          </li>
        </ul>
      </div>
    </div>
  );
}
