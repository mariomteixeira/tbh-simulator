import React from "react";
import { fmtDur, timeAgo } from "../format.js";

export default function ModelPanel({ calibration, samples }) {
  const last = (samples || []).slice(-5).reverse();
  return (
    <div className="card">
      <h2>Modelo</h2>
      <p className="small">
        Calibração: <b>{calibration.source}</b>
        {calibration.tWave != null && (
          <span className="muted"> · {calibration.tWave}s/wave</span>
        )}
      </p>
      <p className="small muted">
        {calibration.samples > 0
          ? `${calibration.samples} amostra(s) de clear persistidas — o modelo melhora sozinho enquanto você joga.`
          : "Sem amostras ainda: jogue com o painel aberto que elas são coletadas dos saves."}
      </p>
      {last.length > 0 && (
        <table className="mini">
          <thead>
            <tr><th>estágio</th><th>clear</th><th>quando</th></tr>
          </thead>
          <tbody>
            {last.map((s, i) => (
              <tr key={i}>
                <td>{s.stage}</td>
                <td>{fmtDur(s.clearSec)}</td>
                <td className="muted">{timeAgo(s.ts)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
