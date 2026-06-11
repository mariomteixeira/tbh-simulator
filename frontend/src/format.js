export function fmt(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}

export function fmtDur(sec) {
  if (sec === null || sec === undefined) return "—";
  if (sec < 90) return Math.round(sec) + "s";
  if (sec < 5400) return Math.round(sec / 60) + "min";
  return (sec / 3600).toFixed(1) + "h";
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
  if (s < 3600) return Math.round(s / 60) + "min atrás";
  return (s / 3600).toFixed(1) + "h atrás";
}
