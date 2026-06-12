export function fmt(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  // sem decimal inutil: 220K (nao 220.0K), 1.5M, 2M
  const trim = (s) =>
    s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
  if (abs >= 1e9) return trim((n / 1e9).toFixed(2)) + "B";
  if (abs >= 1e6) return trim((n / 1e6).toFixed(2)) + "M";
  if (abs >= 1e3) return trim((n / 1e3).toFixed(1)) + "K";
  return String(Math.round(n));
}

export function fmtDur(sec) {
  if (sec === null || sec === undefined) return "—";
  sec = Math.round(sec);
  // preciso ao segundo: 200s mostra "3m20s", nunca "3min" (que esconde os 20s)
  if (sec < 90) return sec + "s";
  if (sec < 3600) {
    const m = Math.floor(sec / 60), s = sec % 60;
    return s ? `${m}m${s}s` : `${m}m`;
  }
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return m ? `${h}h${m}m` : `${h}h`;
}

export function fmtHours(h) {
  if (h === null || h === undefined) return "—";
  if (h >= 1) return h.toFixed(1) + "h";
  return Math.round(h * 60) + "min";
}

export function timeAgo(epoch) {
  const s = Math.round(Date.now() / 1000 - epoch);
  if (s < 5) return "agora";
  if (s < 60) return s + "s atrás";
  if (s < 3600) return Math.floor(s / 60) + "min atrás";  // floor, igual ao launcher
  return (s / 3600).toFixed(1) + "h atrás";
}
