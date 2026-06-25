#!/usr/bin/env python3
"""
TBH Copilot - backend local + painel web
========================================

Usa o tbh_tracker.py como biblioteca (decriptacao, parsing, taxas) e o
simulator.py como engine (DPS, EHP, economia de estagios), e expoe tudo
numa API JSON local servida com FastAPI. A interface fica no navegador
(pasta web/), atualizada por polling.

Uso:
    pip install -r requirements.txt
    python fetch_gamedata.py              # uma vez, baixa dados do jogo
    python server.py                      # http://127.0.0.1:8423
    python server.py --port 9000
    python server.py --save C:\\caminho\\SaveFile_Live.es3

Tudo continua 100% passivo: o save original nunca e aberto em escrita.
"""

import argparse
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import tbh_tracker as core
from simulator import (GameData, simulate, build_catalog, whatif_hero,
                       current_stage_ctx, rune_stats, set_lang)
from store import Store
from steam_market import SteamMarketCache, market_panel

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
DIST_DIR = ROOT / "frontend" / "dist"
GAMEDATA_DIR = ROOT / "gamedata"
STORE_PATH = ROOT / "data" / "store.json"
HISTORY_MAX = 1000  # pontos de historico devolvidos pela API


def _compute_version() -> str:
    """Versao do copilot em execucao, computada uma vez no startup.
    Prioridade:
      1. arquivo .version na raiz (escrito pelo updater.py: sha curto do deploy);
      2. version do frontend/package.json + sha curto do git (se disponivel);
      3. so a version do package.json; senao "dev".
    Nunca lanca excecao."""
    # (1) .version do deploy (updater.py)
    try:
        vf = ROOT / ".version"
        if vf.exists():
            sha = vf.read_text(encoding="utf-8").strip()
            if sha:
                return sha
    except Exception:
        pass
    # version do package.json (base para 2 e 3)
    pkg_version = None
    try:
        import json
        pkg = json.loads((ROOT / "frontend" / "package.json")
                         .read_text(encoding="utf-8"))
        pkg_version = (pkg.get("version") or "").strip() or None
    except Exception:
        pkg_version = None
    # (2) package.json + sha curto do git
    try:
        import subprocess
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(ROOT), capture_output=True, text=True,
                             timeout=5).stdout.strip()
        if sha:
            return f"{pkg_version} · {sha}" if pkg_version else sha
    except Exception:
        pass
    # (3) so a version do package.json, senao "dev"
    return pkg_version or "dev"


VERSION = _compute_version()


class CalibrationIn(BaseModel):
    stage: int          # chave do estagio (ex.: 2109)
    clearSec: float     # tempo de uma run EM SEGUNDOS (cronometrado)


class CeilingIn(BaseModel):
    stage: int          # chave da fase mais alta que voce farma com confianca


class WhatIfIn(BaseModel):
    heroKey: int        # heroi a recalcular
    loadout: list       # [{itemKey, sockets:[{stat, mod, value}]}] por slot


class SaveWatcher:
    """Thread que vigia o save e mantem o ultimo estado pronto para a API."""

    def __init__(self, save_path: Path, store: Store,
                 interval: float = 2.0, debounce: float = 1.0):
        self.save_path = save_path
        self.store = store
        self.interval = interval
        self.debounce = debounce

        self.lock = threading.Lock()
        self.state = None          # ultimo parse_state()
        self.first_state = None    # primeiro da sessao (para taxa media)
        self.rates = None          # entre os dois ultimos saves
        self.session_rates = None  # entre o primeiro e o ultimo save
        self.sim = None            # resultado do simulator.simulate()
        self.sim_error = None
        self.error = None
        self.last_read = None      # epoch da ultima leitura ok
        self._inner = None         # ultimo save decriptado (cache p/ resimulate)
        self._catalog = None       # catalogo de itens/gems (Builds), montado 1x

        self.gamedata = None
        self.gamedata_error = None
        try:
            self.gamedata = GameData(GAMEDATA_DIR)
        except FileNotFoundError as e:
            self.gamedata_error = (f"gamedata nao encontrado ({e}); "
                                   "rode: python fetch_gamedata.py")
        except Exception as e:
            self.gamedata_error = f"gamedata invalido: {e}"

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    # -- loop de vigilancia ------------------------------------------------
    def _loop(self):
        self._read()  # leitura inicial, sem esperar o save mudar
        last_mtime = self._mtime()
        while True:
            time.sleep(self.interval)
            m = self._mtime()
            if m is None or m == last_mtime:
                continue
            last_mtime = m
            time.sleep(self.debounce)  # deixa o jogo terminar de gravar
            self._read()

    def _mtime(self):
        try:
            return self.save_path.stat().st_mtime
        except OSError:
            return None

    def _measured(self):
        """Taxas medidas para calibrar o simulador (prefere a media da sessao)."""
        r = self.session_rates or self.rates
        if not r or r["dt_hours"] <= 0:
            return {}
        out = {}
        if r["gold_per_hour"] and r["gold_per_hour"] > 0:
            out["goldPerSec"] = r["gold_per_hour"] / 3600
        exp_total = sum(v for v in r["exp_per_hour"].values() if v and v > 0)
        if exp_total > 0:
            out["expPerSec"] = exp_total / 3600
        out["expPerHourByHero"] = {k: v for k, v in r["exp_per_hour"].items()
                                   if v and v > 0}
        return out

    def _read(self):
        if not self.save_path.exists():
            with self.lock:
                self.error = f"save nao encontrado: {self.save_path}"
            return
        try:
            inner = core.safe_copy_and_decrypt(self.save_path)
            state = core.parse_state(inner)
        except (ValueError, OSError) as e:
            # gravacao em andamento ou lock momentaneo: tenta no proximo ciclo
            with self.lock:
                self.error = f"leitura falhou ({e}); tentando de novo"
            return

        self._inner = inner  # cache pro resimulate (teto/calibracao na hora)
        with self.lock:
            self.error = None
            self.last_read = time.time()
            prev_state = self.state
            if prev_state and state["lastSavedTime"] != prev_state["lastSavedTime"]:
                self.rates = core.compute_rates(prev_state, state)
            if self.first_state is None:
                self.first_state = state
            elif state["lastSavedTime"] > self.first_state["lastSavedTime"]:
                self.session_rates = core.compute_rates(self.first_state, state)
            self.state = state
            measured = self._measured()

        self.store.add_history({
            "ts": time.time(),
            "ticks": state["lastSavedTime"],
            "playTime": state["playTime"],
            "gold": state["gold"],
            "heroes": {h["name"]: {"level": h["level"], "exp": h["exp"]}
                       for h in state["heroes"]},
        })

        # simulacao fora do lock (le tabelas proprias, nao o estado compartilhado)
        # NOTA: a amostragem automatica de tempo de clear foi REMOVIDA — ela
        # derivava do totalClears do save, que conta varias vezes por run e
        # gerava "medidas" ~5x menores que a realidade. A unica fonte de tempo
        # agora e a calibracao manual (cronometrada), que bate com o jogo.
        sim, sim_error = None, None
        if self.gamedata:
            try:
                sim = simulate(self.gamedata, inner, measured,
                               samples=self._all_samples(),
                               ceiling=self.store.ceiling())
            except Exception as e:
                sim_error = f"simulador falhou: {e}"

        with self.lock:
            self.sim = sim if sim else self.sim
            self.sim_error = sim_error
            self._sim_lang = {}   # invalida cache de nomes pt

    # -- amostras (so manuais) e re-simulacao sob demanda ---------------------
    def _all_samples(self):
        return self.store.manual_samples()

    def resimulate(self):
        """Re-roda a simulacao com as amostras/teto atuais, sem esperar o
        proximo save. Se o save estiver no meio de uma gravacao (ou o jogo
        fechado), usa o ultimo save decriptado em cache — senao a mudanca
        so apareceria no proximo save do jogo."""
        if not self.gamedata:
            return
        try:
            inner = core.safe_copy_and_decrypt(self.save_path)
        except (ValueError, OSError):
            inner = getattr(self, "_inner", None)
            if inner is None:
                return
        with self.lock:
            measured = self._measured()
        try:
            sim = simulate(self.gamedata, inner, measured,
                           samples=self._all_samples(),
                           ceiling=self.store.ceiling())
            with self.lock:
                self.sim, self.sim_error = sim, None
                self._sim_lang = {}
        except Exception as e:
            with self.lock:
                self.sim_error = f"simulador falhou: {e}"

    def _sim_for_lang(self, lang):
        """Sim com os nomes do datamine no idioma pedido. 'en' usa self.sim
        (computado no loop). 'pt' recomputa do save em cache (_inner) e cacheia."""
        if lang != "pt":
            return self.sim
        cache = getattr(self, "_sim_lang", None)
        if cache is None:
            cache = self._sim_lang = {}
        if "pt" in cache:
            return cache["pt"]
        inner = getattr(self, "_inner", None)
        if inner is None or not self.gamedata:
            return self.sim
        try:
            set_lang("pt")
            sim = simulate(self.gamedata, inner, self._measured(),
                           samples=self._all_samples(), ceiling=self.store.ceiling())
            cache["pt"] = sim
            return sim
        except Exception:
            return self.sim
        finally:
            set_lang("en")

    # -- snapshot para a API -------------------------------------------------
    def snapshot(self, lang="en"):
        with self.lock:
            sim = self._sim_for_lang(lang)
            return {
                "version": VERSION,
                "status": {
                    "savePath": str(self.save_path),
                    "saveFound": self.save_path.exists(),
                    "gamedataLoaded": self.gamedata is not None,
                    "gamedataError": self.gamedata_error,
                    "simError": self.sim_error,
                    "lastRead": self.last_read,
                    "error": self.error,
                },
                "state": self.state,
                "rates": self.rates,
                "sessionRates": self.session_rates,
                "sim": sim,
                "history": self.store.history()[-HISTORY_MAX:],
                "manualSamples": self.store.manual_samples(),
            }


def build_app(watcher: SaveWatcher) -> FastAPI:
    app = FastAPI(title="TBH Copilot", docs_url=None, redoc_url=None)
    market_cache = SteamMarketCache(GAMEDATA_DIR / "steam_market_cache.json")

    @app.get("/api/snapshot")
    def api_snapshot(lang: str = "en"):
        return watcher.snapshot("pt" if lang == "pt" else "en")

    @app.get("/api/market")
    def api_market(lang: str = "en"):
        gd = watcher.gamedata
        if not gd:
            return {"error": watcher.gamedata_error or "gamedata indisponivel",
                    "containers": []}
        save = getattr(watcher, "_inner", None)
        if not save:
            return {"error": "save ainda nao lido", "containers": []}
        return market_panel(gd, save, market_cache, "pt" if lang == "pt" else "en")

    @app.post("/api/calibration")
    def add_calibration(body: CalibrationIn):
        """Grava o tempo (em segundos) cronometrado pelo usuario para a fase,
        anexando o DPS/HP/waves do momento. Vira amostra manual (peso alto)."""
        econ = watcher.gamedata.stage_econ(body.stage) if watcher.gamedata else None
        with watcher.lock:
            sim = watcher.sim
        party_dps = ((sim or {}).get("party") or {}).get("dps")
        sample = {
            "ts": time.time(), "stage": body.stage,
            "clearSec": round(float(body.clearSec), 2),
            "clears": 1, "method": "manual", "source": "manual",
            "partyDps": round(party_dps, 1) if party_dps else None,
            "hp": econ["hp"] if econ else None,
            "waves": econ["waves"] if econ else None,
            "lvl": econ["lvl"] if econ else None,
        }
        watcher.store.add_manual_sample(sample)
        watcher.resimulate()
        # usable=False avisa o painel que a amostra so entra no ajuste quando
        # houver DPS lido (servidor precisa ter lido o save com o time montado)
        return {"ok": True, "usable": bool(party_dps and econ), "sample": sample}

    @app.delete("/api/calibration/{stage}")
    def del_calibration(stage: int):
        removed = watcher.store.remove_manual_sample(stage)
        watcher.resimulate()
        return {"ok": True, "removed": removed}

    @app.get("/api/catalog")
    def api_catalog(lang: str = "en"):
        """Catalogo de itens equipaveis + gems (decoracao/gravacao/inscricao).
        So depende do datamine — montado uma vez por idioma e cacheado."""
        if not watcher.gamedata:
            return {"error": watcher.gamedata_error or "gamedata indisponivel"}
        key = "pt" if lang == "pt" else "en"
        cache = watcher._catalog if isinstance(watcher._catalog, dict) else {}
        if key not in cache:
            try:
                set_lang(key)
                cache[key] = build_catalog(watcher.gamedata)
            finally:
                set_lang("en")
            watcher._catalog = cache
        return watcher._catalog[key]

    @app.post("/api/whatif")
    def api_whatif(body: WhatIfIn):
        """Recalcula dps/ehp/stats de um heroi com um loadout HIPOTETICO
        (itens + gems). 100% read-only: nada e gravado no save."""
        gd = watcher.gamedata
        inner = watcher._inner
        if not gd:
            return {"error": watcher.gamedata_error or "gamedata indisponivel"}
        if not inner:
            return {"error": "save ainda nao lido"}
        hs = next((h for h in inner.get("heroSaveDatas") or []
                   if h.get("heroKey") == body.heroKey), None)
        if not hs:
            return {"error": f"heroi {body.heroKey} nao encontrado"}
        try:
            runes = rune_stats(gd, inner)
            ctx = current_stage_ctx(gd, inner)
            return whatif_hero(gd, inner, hs, runes, body.loadout, ctx)
        except Exception as e:
            return {"error": f"falha no recalculo: {e}"}

    @app.post("/api/ceiling")
    def set_ceiling(body: CeilingIn):
        """Define o teto: a fase mais alta que voce FARMA com confianca.
        Nada acima dele entra em recomendacao."""
        watcher.store.set_ceiling(body.stage)
        watcher.resimulate()
        return {"ok": True, "ceiling": body.stage}

    @app.delete("/api/ceiling")
    def del_ceiling():
        watcher.store.set_ceiling(None)
        watcher.resimulate()
        return {"ok": True, "ceiling": None}

    # serve o frontend buildado (frontend/dist); cai para o web/ legado
    static_dir = DIST_DIR if (DIST_DIR / "index.html").exists() else WEB_DIR

    @app.get("/")
    def index():
        # index.html nunca e cacheado (os assets tem hash no nome, entao
        # cada build novo aparece no navegador sem precisar de Ctrl+F5)
        return FileResponse(static_dir / "index.html",
                            headers={"Cache-Control": "no-cache"})

    app.mount("/assets", StaticFiles(directory=static_dir / "assets")
              if (static_dir / "assets").exists()
              else StaticFiles(directory=static_dir), name="assets")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # icones das runas (baixados pela fetch_gamedata; fan-made, taskbarhero.wiki)
    rune_icons = GAMEDATA_DIR / "icons" / "runes"
    if rune_icons.exists():
        app.mount("/runeicons", StaticFiles(directory=rune_icons), name="runeicons")

    # icones de itens: baixados sob demanda do wiki e cacheados localmente.
    # (o wiki bloqueia user-agent nao-navegador; mandamos um de Chrome)
    item_icon_dir = GAMEDATA_DIR / "icons" / "items"
    hero_icon_dir = GAMEDATA_DIR / "icons" / "heroes"
    icon_ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}

    @app.get("/itemicon/{key}.png")
    def item_icon(key: int):
        dest = item_icon_dir / f"{key}.png"
        if not dest.exists():
            item = watcher.gamedata.items.get(key) if watcher.gamedata else None
            ipath = item.get("icon") if item else None
            if not ipath:
                return Response(status_code=404)
            try:
                import urllib.request
                req = urllib.request.Request("https://taskbarhero.wiki" + ipath,
                                             headers=icon_ua)
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                if not data.startswith(b"\x89PNG"):
                    return Response(status_code=404)
                item_icon_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            except Exception:
                return Response(status_code=404)
        return FileResponse(dest, media_type="image/png",
                            headers={"Cache-Control": "max-age=604800"})

    @app.get("/heroicon/{key}.png")
    def hero_icon(key: int):
        dest = hero_icon_dir / f"{key}.png"
        if not dest.exists():
            hero = watcher.gamedata.heroes.get(key) if watcher.gamedata else None
            ipath = hero.get("icon") if hero else None
            if not ipath:
                return Response(status_code=404)
            try:
                import urllib.request
                req = urllib.request.Request("https://taskbarhero.wiki" + ipath,
                                             headers=icon_ua)
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                if not data.startswith(b"\x89PNG"):
                    return Response(status_code=404)
                hero_icon_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            except Exception:
                return Response(status_code=404)
        return FileResponse(dest, media_type="image/png",
                            headers={"Cache-Control": "max-age=604800"})

    return app


def main():
    ap = argparse.ArgumentParser(description="TBH Copilot - backend + painel web")
    ap.add_argument("--save", type=Path, default=core.DEFAULT_SAVE)
    ap.add_argument("--port", type=int, default=8423)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--debounce", type=float, default=1.0)
    args = ap.parse_args()

    store = Store(STORE_PATH)
    watcher = SaveWatcher(args.save, store,
                          interval=args.interval, debounce=args.debounce)
    watcher.start()

    app = build_app(watcher)
    print(f"\n  TBH Copilot rodando em  http://127.0.0.1:{args.port}\n")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
