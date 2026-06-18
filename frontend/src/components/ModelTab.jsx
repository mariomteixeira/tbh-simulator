import React from "react";
import { fmt } from "../format.js";
import { useT } from "../i18n.jsx";

export default function ModelTab({ sim, manualSamples }) {
  const t = useT();
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
        ts: m.ts || 0,
        predicted: row ? row.clearTime : null,
        errPct: row ? ((row.clearTime - m.clearSec) / m.clearSec) * 100 : null,
      };
    })
    .sort((a, b) => b.ts - a.ts); // mais recém-sincronizados primeiro
  const dpsNow = sim.party?.dps;
  const [showAll, setShowAll] = React.useState(false);
  const visibleCmp = showAll ? comparison : comparison.slice(0, 10);

  const killRate = sim.party?.dps && cal.factor ? sim.party.dps * cal.factor : null;

  const [secs, setSecs] = React.useState("");
  const [calKey, setCalKey] = React.useState(null); // null = segue a fase atual
  const curRow = (sim.farm.rows || []).find((r) => r.current);
  const calOptions = (sim.farm.rows || []).filter((r) => r.type !== "ACTBOSS");
  const calRow =
    calKey != null
      ? calOptions.find((r) => r.key === calKey) || curRow
      : curRow;
  async function saveCal(stageKey) {
    const v = parseFloat(secs);
    if (!v || v <= 0) return;
    await fetch("/api/calibration", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: Number(stageKey), clearSec: v }),
    });
    setSecs("");
    setCalKey(null); // volta a seguir a fase atual
  }
  async function removeCal(stageKey) {
    await fetch("/api/calibration/" + stageKey, { method: "DELETE" });
  }

  return (
    <div className="model-grid">
      <section className="sec">
        <h2>{t("Calibration", "Calibração")}</h2>
        <p className="muted small">{t("Enter your run time and type the time below:", "Insira seu tempo de run e digite o tempo abaixo:")}</p>
        {calRow ? (
          <div className="cal-form">
            <div className="cal-row">
              <select
                className="ceiling-sel cal-sel"
                value={calRow.key}
                onChange={(e) => setCalKey(Number(e.target.value))}
              >
                {calOptions.map((r) => (
                  <option key={r.key} value={r.key}>
                    {r.tag} {r.label} — {r.name}
                    {r.current ? t(" (current stage)", " (fase atual)") : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="cal-stage muted small">
              {calKey == null
                ? t("following the current stage", "seguindo a fase atual")
                : t("manually chosen stage (does not change when you switch maps)", "fase escolhida à mão (não muda quando você troca de mapa)")}
              {calRow.clearTime != null &&
                t(` · predicted now ${Math.round(calRow.clearTime)}s`, ` · previsto agora ${Math.round(calRow.clearTime)}s`)}
            </div>
            <div className="cal-row">
              <input
                type="number" min="1" step="1" placeholder={t("seconds", "segundos")}
                value={secs}
                onChange={(e) => setSecs(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && saveCal(calRow.key)}
              />
              <span className="muted">s</span>
              <button onClick={() => saveCal(calRow.key)} disabled={!secs}>
                {t("Save", "Salvar")}
              </button>
            </div>
          </div>
        ) : (
          <p className="muted small">{t("waiting for the save to know the current stage…", "aguardando o save pra saber a fase atual…")}</p>
        )}
      </section>

      <section className="sec">
        <h2>{t("Predicted × measured (your calibrations)", "Previsto × medido (suas calibrações)")}</h2>
        {comparison.length === 0 ? (
          <p className="muted small">
            {t("No calibration yet. Time a run in the card above — the model extrapolates from it to all stages.", "Nenhuma calibração ainda. Cronometre uma run no card acima — o modelo extrapola dela pra todas as fases.")}
          </p>
        ) : (
          <>
            <table className="mini wide">
              <thead>
                <tr>
                  <th>{t("stage", "estágio")}</th><th>{t("timed", "cronometrado")}</th><th>{t("dps then", "dps na época")}</th>
                  <th>{t("predicted today", "previsto hoje")}{dpsNow ? ` (dps ${fmt(dpsNow)})` : ""}</th>
                  <th>Δ</th><th></th>
                </tr>
              </thead>
              <tbody>
                {visibleCmp.map((c) => (
                  <tr key={c.key}>
                    <td>{c.label} <span className="muted">{c.name}</span></td>
                    <td>{Math.round(c.observed)}s</td>
                    <td className="muted">{c.dpsThen ? fmt(c.dpsThen) : "—"}</td>
                    <td>{c.predicted != null ? Math.round(c.predicted) + "s" : "—"}</td>
                    <td className={Math.abs(c.errPct ?? 0) > 25 ? "err-bad" : "err-ok"}>
                      {c.errPct != null ? (c.errPct > 0 ? "+" : "") + c.errPct.toFixed(0) + "%" : "—"}
                    </td>
                    <td>
                      <button className="link" onClick={() => removeCal(c.key)}>
                        {t("remove", "remover")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {comparison.length > 10 && (
              <button
                className="link"
                style={{ marginTop: 8 }}
                onClick={() => setShowAll((s) => !s)}
              >
                {showAll
                  ? t("show less", "ver menos")
                  : t(`show more (+${comparison.length - 10})`, `ver mais (+${comparison.length - 10})`)}
              </button>
            )}
            <p className="muted small" style={{ marginTop: 8 }}>
              {t("The prediction uses your ", "O previsto usa seu DPS ")}<b>{t("current", "atual")}</b>{t(" DPS — if the team got stronger since the calibration, it's normal for the prediction to be lower than the time recorded back then. Recalibrate now and then to keep up.", " — se o time ficou mais forte desde a calibração, é normal o previsto ser menor que o tempo cronometrado na época. Recalibre de vez em quando pra acompanhar.")}
            </p>
          </>
        )}
      </section>

      <section className="sec">
        <h2>{t("Calibration state", "Estado da calibração")}</h2>
        <div className="model-stats">
          <div className="kv-big">
            <i>{t("active source", "fonte ativa")}</i>
            <b>{cal.source}</b>
          </div>
          <div className="kv-big">
            <i>{t("calibrations", "calibrações")}</i>
            <b>{(manualSamples || []).length}</b>
          </div>
          <div className="kv-big">
            <i>{t("overhead per wave", "overhead por wave")}</i>
            <b>{cal.tWave != null ? cal.tWave + "s" : "—"}</b>
          </div>
          <div className="kv-big">
            <i>{t("kill speed", "velocidade de kill")}</i>
            <b>{killRate ? fmt(killRate) + " HP/s" : "—"}</b>
          </div>
          <div className="kv-big">
            <i>{t("factor (kill ÷ theoretical DPS)", "fator (kill ÷ DPS teórico)")}</i>
            <b>{cal.factor ?? "—"}</b>
          </div>
        </div>
      </section>
    </div>
  );
}
