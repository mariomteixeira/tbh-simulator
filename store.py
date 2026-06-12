#!/usr/bin/env python3
"""
Persistencia simples em JSON para o TBH Copilot.

Guarda em data/store.json:
  - manualSamples: tempos de clear CRONOMETRADOS pelo usuario (uma por fase).
    Sao a unica fonte de tempo do modelo — o contador de clears do save conta
    varias vezes por run e a amostragem automatica baseada nele foi removida.
  - history: serie temporal de gold/exp (sobrevive a restarts do servidor)

Escrita atomica (tmp + replace) para nao corromper com Ctrl+C.
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

HISTORY_MAX = 5000


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        # NOTA: "samples" (auto) e "stageStats" foram REMOVIDOS — derivavam do
        # totalClears do save, que conta varias vezes por run; eram veneno.
        # Arquivos antigos sao migrados: essas chaves sao simplesmente dropadas.
        self.data = {"history": [], "manualSamples": {}}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data["history"] = list(loaded.get("history") or [])
                    self.data["manualSamples"] = dict(loaded.get("manualSamples") or {})
            except (OSError, ValueError):
                pass  # arquivo corrompido: recomeca (os dados sao re-derivaveis)

    # -- amostras manuais (cronometradas pelo usuario; uma por fase) ----------
    def add_manual_sample(self, sample: dict):
        """Upsert: uma amostra manual por fase (a nova sobrescreve a anterior)."""
        with self.lock:
            self.data["manualSamples"][str(sample["stage"])] = sample
            self._flush()

    def remove_manual_sample(self, stage) -> bool:
        with self.lock:
            removed = self.data["manualSamples"].pop(str(stage), None) is not None
            if removed:
                self._flush()
            return removed

    def manual_samples(self):
        with self.lock:
            return list(self.data["manualSamples"].values())

    # -- historico de sessao ---------------------------------------------------
    def add_history(self, point: dict):
        with self.lock:
            hist = self.data["history"]
            if hist and hist[-1].get("ticks") == point.get("ticks"):
                return
            hist.append(point)
            if len(hist) > HISTORY_MAX:
                self.data["history"] = hist[-HISTORY_MAX:]
            self._flush()

    def history(self, since_hours: float | None = None):
        with self.lock:
            hist = list(self.data["history"])
        if since_hours is None:
            return hist
        cutoff = time.time() - since_hours * 3600
        return [p for p in hist if p.get("ts", 0) >= cutoff]

    # -- gravacao atomica -----------------------------------------------------
    def _flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
