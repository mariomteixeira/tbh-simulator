"use strict";

const POLL_MS = 2000;

const $ = (id) => document.getElementById(id);

function fmt(n) {
  if (n === null || n === undefined) return "—";
  n = Math.round(n);
  const abs = Math.abs(n);
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}

function fmtDur(sec) {
  if (sec === null || sec === undefined) return "—";
  if (sec < 90) return Math.round(sec) + "s";
  if (sec < 5400) return Math.round(sec / 60) + "min";
  return (sec / 3600).toFixed(1) + "h";
}

function fmtHours(h) {
  if (h >= 1) return h.toFixed(1) + "h";
  return Math.round(h * 60) + "min";
}

function timeAgo(epoch) {
  const s = Math.round(Date.now() / 1000 - epoch);
  if (s < 60) return s + "s atrás";
  if (s < 3600) return Math.round(s / 60) + "min atrás";
  return (s / 3600).toFixed(1) + "h atrás";
}

// ---------------------------------------------------------------- render

function renderSummary(d) {
  const st = d.state;
  $("gold").textContent = fmt(st.gold);
  $("stage").textContent = st.currentStage;
  $("max-stage").textContent = "máx concluído: " + st.maxStage;
  $("playtime").textContent = (st.playTime / 3600).toFixed(1) + "h";
  $("last-save").textContent = d.status.lastRead
    ? "último save lido " + timeAgo(d.status.lastRead) : "—";

  const r = d.rates;
  if (r && r.dt_hours > 0) {
    $("gold-rate").textContent = r.gold_per_hour === null
      ? "gastou gold no último intervalo"
      : fmt(r.gold_per_hour) + "/h (último intervalo)";
  } else {
    $("gold-rate").textContent = "aguardando segundo save…";
  }

  const sr = d.sessionRates;
  if (sr && sr.dt_hours > 0) {
    $("session-gold-rate").textContent =
      sr.gold_per_hour === null ? "gold gasto" : fmt(sr.gold_per_hour) + " g/h";
    $("session-span").textContent = "média em " + fmtHours(sr.dt_hours);
  } else {
    $("session-gold-rate").textContent = "—";
    $("session-span").textContent = "aguardando segundo save…";
  }

  if (d.sim) {
    $("party-dps").textContent = fmt(d.sim.party.dps);
    const c = d.sim.calibration;
    $("calib").textContent = c.source === "modelo"
      ? "modelo puro (sem calibração ainda)"
      : `calibrado por ${c.source} (×${c.factor})`;
  } else {
    $("party-dps").textContent = "—";
    $("calib").textContent = "simulador indisponível";
  }
}

function renderCoach(d) {
  const wrap = $("coach");
  wrap.innerHTML = "";
  if (!d.sim) {
    $("coach-panel").classList.add("hidden");
    return;
  }
  $("coach-panel").classList.remove("hidden");
  const f = d.sim.farm;
  const tips = [];

  if (f.current && f.bestGold && f.bestGold.key !== f.current.key) {
    const gain = f.bestGold.goldPerHour / Math.max(f.current.goldPerHour, 1);
    if (gain > 1.15) {
      tips.push({ icon: "💰", text: `Para gold: troque para ${f.bestGold.tag} ${f.bestGold.label} (${f.bestGold.name}) — ~${fmt(f.bestGold.goldPerHour)}/h, ${gain.toFixed(1)}× o estágio atual.` });
    }
  }
  if (f.current && f.bestExp && f.bestExp.key !== f.current.key) {
    const gain = f.bestExp.expPerHour / Math.max(f.current.expPerHour, 1);
    if (gain > 1.15) {
      tips.push({ icon: "📈", text: `Para exp: ${f.bestExp.tag} ${f.bestExp.label} (${f.bestExp.name}) rende ~${fmt(f.bestExp.expPerHour)} exp/h, ${gain.toFixed(1)}× o atual.` });
    }
  }
  if (f.push) {
    tips.push({ icon: f.push.rating === "arriscado" ? "⚠️" : "🚩",
      text: `Próximo avanço: ${f.push.tag} ${f.push.label} (${f.push.name}, lvl ${f.push.lvl}) — perigo ${f.push.rating}.` });
  }
  for (const h of d.state.heroes) {
    if (h.unspent > 0) {
      tips.push({ icon: "✨", text: `${h.name} tem ${h.unspent} ponto(s) de atributo sem gastar.` });
    }
  }
  for (const e of d.sim.levelEta || []) {
    if (e.etaSec !== null && e.etaSec < 3600) {
      const hero = d.sim.heroes.find((h) => h.key === e.key);
      tips.push({ icon: "⬆️", text: `${hero ? hero.name : e.key} sobe de nível em ~${fmtDur(e.etaSec)}.` });
    }
  }
  if (!tips.length) tips.push({ icon: "✅", text: "Nada urgente — você já está no farm certo." });

  for (const t of tips) {
    const div = document.createElement("div");
    div.className = "tip";
    div.innerHTML = `<span class="tip-icon">${t.icon}</span><span>${t.text}</span>`;
    wrap.appendChild(div);
  }
}

function renderFarm(d) {
  const tbody = $("farm-table").querySelector("tbody");
  tbody.innerHTML = "";
  if (!d.sim) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-msg">simulador indisponível — veja o aviso acima</td></tr>`;
    return;
  }
  const f = d.sim.farm;
  $("farm-note").textContent = `(bônus de runas: +${d.sim.goldBonusPct}% gold, +${d.sim.expBonusPct}% exp)`;

  // top 10 por gold/h + atual + melhor exp + push, sem duplicar
  const byGold = [...f.rows].filter((r) => r.type !== "ACTBOSS")
    .sort((a, b) => b.goldPerHour - a.goldPerHour).slice(0, 10);
  const extras = [f.current, f.bestExp, f.push].filter(Boolean);
  const seen = new Set();
  const rows = [];
  for (const r of [...byGold, ...extras]) {
    if (!seen.has(r.key)) { seen.add(r.key); rows.push(r); }
  }
  rows.sort((a, b) => b.goldPerHour - a.goldPerHour);

  for (const r of rows) {
    const tr = document.createElement("tr");
    const marks = [];
    if (r.current) marks.push('<span class="mark cur">atual</span>');
    if (f.bestGold && r.key === f.bestGold.key) marks.push('<span class="mark gold">melhor gold</span>');
    if (f.bestExp && r.key === f.bestExp.key) marks.push('<span class="mark exp">melhor exp</span>');
    if (f.push && r.key === f.push.key) marks.push('<span class="mark push">push</span>');
    tr.className = r.current ? "is-current" : "";
    tr.innerHTML = `
      <td><span class="diff-tag t-${r.tag}">${r.tag}</span> <b>${r.label}</b> ${r.name ?? ""} ${marks.join(" ")}</td>
      <td>${r.lvl}</td>
      <td class="num">${fmtDur(r.clearTime)}</td>
      <td class="num gold-v">${fmt(r.goldPerHour)}</td>
      <td class="num exp-v">${fmt(r.expPerHour)}</td>
      <td><span class="rating r-${r.rating}">${r.rating}</span></td>`;
    tbody.appendChild(tr);
  }
}

function renderHeroes(d) {
  const st = d.state;
  const simHeroes = {};
  for (const h of (d.sim && d.sim.heroes) || []) simHeroes[h.key] = h;
  const etas = {};
  for (const e of (d.sim && d.sim.levelEta) || []) etas[e.key] = e;
  const expRates = (d.sessionRates && d.sessionRates.exp_per_hour) ||
                   (d.rates && d.rates.exp_per_hour) || {};

  const wrap = $("heroes");
  wrap.innerHTML = "";
  for (const h of st.heroes) {
    const inTeam = st.arranged && st.arranged.includes(h.key);
    const sim = simHeroes[h.key];
    const eta = etas[h.key];
    const div = document.createElement("div");
    div.className = "hero" + (inTeam ? "" : " bench");
    div.innerHTML = `
      <div class="hero-top">
        <span class="hero-name">${h.name}${inTeam ? '<span class="in-team">no time</span>' : ""}</span>
        <span class="hero-level">Lv ${h.level}</span>
      </div>
      <div class="hero-stats">
        <span>exp <b>${fmt(h.exp)}</b></span>
        <span>${expRates[h.name] !== undefined ? fmt(expRates[h.name]) + " exp/h" : ""}</span>
      </div>
      ${sim ? `<div class="hero-stats">
        <span>dps status <b>${fmt(sim.statusDps)}</b></span>
        <span>efetivo <b>${fmt(sim.dps)}</b></span>
        <span>ehp <b>${fmt(sim.ehp)}</b></span>
      </div>` : ""}
      ${eta && eta.etaSec !== null ? `<div class="hero-stats"><span>próx. nível em ~<b>${fmtDur(eta.etaSec)}</b></span></div>` : ""}
      ${h.unspent > 0 ? `<span class="badge-unspent">${h.unspent} ponto(s) livre</span>` : ""}`;
    wrap.appendChild(div);
  }
}

function renderChart(history) {
  const svg = $("chart");
  const W = 1000, H = 120;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = "";

  if (!history || history.length < 2) {
    svg.innerHTML = `<text class="empty" x="10" y="20">aguardando mais saves para desenhar o gráfico…</text>`;
    return;
  }

  const xs = history.map((p) => p.ticks);
  const ys = history.map((p) => p.gold);
  const x0 = xs[0], x1 = xs[xs.length - 1];
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const spanX = x1 - x0 || 1;
  const spanY = yMax - yMin || 1;
  const pad = 6;

  const pts = history.map((p) => {
    const x = ((p.ticks - x0) / spanX) * (W - 2 * pad) + pad;
    const y = H - pad - ((p.gold - yMin) / spanY) * (H - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const area = `${pad},${H - pad} ${pts.join(" ")} ${W - pad},${H - pad}`;
  svg.innerHTML = `
    <polygon class="area" points="${area}"></polygon>
    <polyline class="line" points="${pts.join(" ")}"></polyline>`;
}

function renderBanner(status) {
  const banner = $("banner");
  const msgs = [];
  if (!status.saveFound) msgs.push("Save não encontrado: " + status.savePath);
  else if (status.error) msgs.push(status.error);
  if (status.gamedataError) msgs.push(status.gamedataError);
  if (status.simError) msgs.push(status.simError);
  if (msgs.length) {
    banner.textContent = msgs.join(" · ");
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }
}

// ---------------------------------------------------------------- loop

async function poll() {
  const conn = $("conn");
  try {
    const res = await fetch("/api/snapshot");
    const d = await res.json();
    conn.textContent = "● conectado";
    conn.className = "conn ok";

    renderBanner(d.status);
    if (d.state) {
      renderSummary(d);
      renderCoach(d);
      renderFarm(d);
      renderHeroes(d);
      renderChart(d.history);
    }
  } catch (e) {
    conn.textContent = "● sem conexão com o backend";
    conn.className = "conn bad";
  }
}

poll();
setInterval(poll, POLL_MS);
