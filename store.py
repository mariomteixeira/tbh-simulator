#!/usr/bin/env python3
"""
Persistencia simples em JSON para o TBH Copilot.

Guarda em data/store.json:
  - samples: observacoes de tempo de clear, derivadas dos saves
      {ts, stage, lvl, clearSec, clears, hp, waves, partyDps}
    Sao o combustivel da calibracao por regressao: quanto mais voce joga,
    mais preciso o modelo fica.
  - history: serie temporal de gold/exp (sobrevive a restarts do servidor)

Escrita atomica (tmp + replace) para nao corromper com Ctrl+C.
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

SAMPLES_MAX = 2000
HISTORY_MAX = 5000


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = {"samples": [], "history": [], "stageStats": {}}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data["samples"] = list(loaded.get("samples") or [])
                    self.data["history"] = list(loaded.get("history") or [])
                    self.data["stageStats"] = dict(loaded.get("stageStats") or {})
            except (OSError, ValueError):
                pass  # arquivo corrompido: recomeca (os dados sao re-derivaveis)

    # -- amostras de clear ---------------------------------------------------
    def add_sample(self, sample: dict):
        with self.lock:
            self.data["samples"].append(sample)
            if len(self.data["samples"]) > SAMPLES_MAX:
                self.data["samples"] = self.data["samples"][-SAMPLES_MAX:]
            self._flush()

    def samples(self):
        with self.lock:
            return list(self.data["samples"])

    # -- kills/run empirico por estagio (aprendido dos contadores do save) ----
    def add_stage_obs(self, stage: int, kills_per_clear: float, clears: float):
        """EMA de kills por run observados; janelas maiores pesam mais."""
        with self.lock:
            key = str(stage)
            cur = self.data["stageStats"].get(key)
            alpha = min(0.5, 0.15 * max(clears, 1))
            if cur:
                cur["kpc"] = round(cur["kpc"] * (1 - alpha) + kills_per_clear * alpha, 2)
                cur["n"] = cur.get("n", 0) + 1
            else:
                self.data["stageStats"][key] = {"kpc": round(kills_per_clear, 2), "n": 1}
            self._flush()

    def stage_stats(self):
        with self.lock:
            return dict(self.data["stageStats"])

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
